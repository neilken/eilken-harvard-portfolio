# — AC215 MS2 single-CLI for ingest + serve (Semantic-Recursive Chunking, LangChain retriever required)
#
# Usage:
#   python rag.py --ingest              # one-shot indexing
#   python rag.py --serve               # start FastAPI (/health, /query)
#   python rag.py --ingest --serve      # index then serve
#   python rag.py --dump-vector         # dump one stored vector to artifacts/sample_vector.json
#   python rag.py --ingest --verbose    # print each chunk + metadata
#
# Semantic controls:
#   --sim-percentile 95.0  --buffer-size 1  --max-tokens 1400  --overlap-sentences 2  --target-tokens 900
#
# Requires:
#   pip install "langchain>=0.2" "langchain-community>=0.2" fastembed chromadb fastapi uvicorn numpy pymupdf

import os, re, glob, json, time, argparse
from typing import List, Tuple, Dict, Any

# --- Settings ---------------------------------------------------------------
API_PORT          = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "/workspace/volumes/chroma")
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
DATA_DIR          = os.getenv("DATA_DIR", "/workspace/data")
ARTIFACTS_DIR     = os.getenv("ARTIFACTS_DIR", "/workspace/artifacts")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Optional logging via env
RAG_VERBOSE_ENV       = os.getenv("RAG_VERBOSE", "0").strip() in {"1","true","True"}
RAG_PRINT_VECTORS_ENV = os.getenv("RAG_PRINT_VECTORS", "0").strip() in {"1","true","True"}
RAG_VEC_PREVIEW_ENV   = os.getenv("RAG_VEC_PREVIEW", "").strip()
try:
    RAG_VEC_PREVIEW_N = int(RAG_VEC_PREVIEW_ENV) if RAG_VEC_PREVIEW_ENV else 8
except Exception:
    RAG_VEC_PREVIEW_N = 8

def _safe_mkdir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"[WARN] Could not ensure dir {path}: {e}")

_safe_mkdir(ARTIFACTS_DIR)
SANITIZED_DIR = os.path.join(ARTIFACTS_DIR, "sanitized")
_safe_mkdir(SANITIZED_DIR)
_safe_mkdir(DATA_DIR)
_safe_mkdir(VECTOR_STORE_PATH)

# --- Silence Chroma telemetry/logs (must be BEFORE importing chromadb) -----
import logging
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"  # hard kill via env
for name in ("chromadb", "chromadb.telemetry", "posthog"):
    logging.getLogger(name).setLevel(logging.ERROR)

from chromadb.config import Settings as ChromaSettings

# --- Dependencies -----------------------------------------------------------
import numpy as np
import chromadb
from fastembed import TextEmbedding

# LangChain (required)
try:
    from langchain_chroma import Chroma as LCChroma
    from langchain_core.embeddings import Embeddings as LcEmbeddings
    from langchain_core.documents import BaseDocumentTransformer, Document
    from langchain_community.utils.math import cosine_similarity
except Exception as e:
    raise ImportError(
        "LangChain is required. Install:\n"
        "  pip install 'langchain>=0.2' 'langchain-community>=0.2'\n"
        f"Original import error: {e}"
    )

# ===========================
# Embedded Semantic Chunker
# ===========================
from typing import Literal, Optional, Sequence, cast, Any

BreakpointThresholdType = Literal["percentile","standard_deviation","interquartile","gradient"]
BREAKPOINT_DEFAULTS: Dict[BreakpointThresholdType, float] = {
    "percentile": 95, "standard_deviation": 3, "interquartile": 1.5, "gradient": 95,
}

def _combine_sentences(sentences: List[dict], buffer_size: int = 1) -> List[dict]:
    for i in range(len(sentences)):
        cs = []
        for j in range(i - buffer_size, i):
            if j >= 0: cs.append(sentences[j]["sentence"])
        cs.append(sentences[i]["sentence"])
        for j in range(i + 1, i + 1 + buffer_size):
            if j < len(sentences): cs.append(sentences[j]["sentence"])
        sentences[i]["combined_sentence"] = " ".join(cs)
    return sentences

def _calc_cosine_distances(sentences: List[dict]) -> Tuple[List[float], List[dict]]:
    distances = []
    for i in range(len(sentences) - 1):
        e_cur = sentences[i]["combined_sentence_embedding"]
        e_nxt = sentences[i + 1]["combined_sentence_embedding"]
        sim = cosine_similarity([e_cur], [e_nxt])[0][0]
        dist = 1 - sim
        distances.append(dist)
        sentences[i]["distance_to_next"] = dist
    return distances, sentences

class SemanticChunker(BaseDocumentTransformer):
    def __init__(
        self,
        buffer_size: int = 1,
        add_start_index: bool = False,
        breakpoint_threshold_type: BreakpointThresholdType = "percentile",
        breakpoint_threshold_amount: Optional[float] = None,
        number_of_chunks: Optional[int] = None,
        sentence_split_regex: str = r"(?<=[.?!])\s+",
        embedding_function = None,
    ):
        self._add_start_index = add_start_index
        self.buffer_size = buffer_size
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.number_of_chunks = number_of_chunks
        self.sentence_split_regex = sentence_split_regex
        self.breakpoint_threshold_amount = (
            BREAKPOINT_DEFAULTS[breakpoint_threshold_type]
            if breakpoint_threshold_amount is None
            else breakpoint_threshold_amount
        )
        self.embedding_function = embedding_function

    def _calc_breakpoint_threshold(self, distances: List[float]) -> Tuple[float, List[float]]:
        if self.breakpoint_threshold_type == "percentile":
            return cast(float, np.percentile(distances, self.breakpoint_threshold_amount)), distances
        elif self.breakpoint_threshold_type == "standard_deviation":
            return cast(float, np.mean(distances) + self.breakpoint_threshold_amount * np.std(distances)), distances
        elif self.breakpoint_threshold_type == "interquartile":
            q1, q3 = np.percentile(distances, [25, 75]); iqr = q3 - q1
            return np.mean(distances) + self.breakpoint_threshold_amount * iqr, distances
        elif self.breakpoint_threshold_type == "gradient":
            grad = np.gradient(distances, range(0, len(distances)))
            return cast(float, np.percentile(grad, self.breakpoint_threshold_amount)), grad
        else:
            raise ValueError(f"Unexpected breakpoint_threshold_type: {self.breakpoint_threshold_type}")

    def _threshold_from_clusters(self, distances: List[float]) -> float:
        if self.number_of_chunks is None:
            raise ValueError("number_of_chunks is None.")
        x1, y1 = len(distances), 0.0
        x2, y2 = 1.0, 100.0
        x = max(min(self.number_of_chunks, x1), x2)
        y = y1 + ((y2 - y1) / (x2 - x1)) * (x - x1) if x2 != x1 else y2
        y = min(max(y, 0), 100)
        return cast(float, np.percentile(distances, y))

    def _calculate_sentence_distances(self, single_sentences_list: List[str]) -> Tuple[List[float], List[dict]]:
        _sentences = [{"sentence": x, "index": i} for i, x in enumerate(single_sentences_list)]
        sentences = _combine_sentences(_sentences, self.buffer_size)
        embeddings = self.embedding_function([x["combined_sentence"] for x in sentences], batch_size=50)
        for i, s in enumerate(sentences):
            s["combined_sentence_embedding"] = embeddings[i]
        return _calc_cosine_distances(sentences)

    def split_text(self, text: str) -> List[str]:
        single_sentences_list = re.split(self.sentence_split_regex, text)
        if len(single_sentences_list) == 1:
            return single_sentences_list
        if self.breakpoint_threshold_type == "gradient" and len(single_sentences_list) == 2:
            return single_sentences_list
        distances, sentences = self._calculate_sentence_distances(single_sentences_list)
        if self.number_of_chunks is not None:
            breakpoint_distance_threshold = self._threshold_from_clusters(distances)
            breakpoint_array = distances
        else:
            breakpoint_distance_threshold, breakpoint_array = self._calc_breakpoint_threshold(distances)
        indices_above = [i for i, x in enumerate(breakpoint_array) if x > breakpoint_distance_threshold]
        chunks, start_index = [], 0
        for index in indices_above:
            end_index = index
            group = sentences[start_index : end_index + 1]
            combined_text = " ".join([d["sentence"] for d in group])
            chunks.append(combined_text)
            start_index = index + 1
        if start_index < len(sentences):
            combined_text = " ".join([d["sentence"] for d in sentences[start_index:]])
            chunks.append(combined_text)
        return chunks

    def create_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> List[Document]:
        _metadatas = metadatas or [{}] * len(texts)
        documents = []
        for i, text in enumerate(texts):
            start_index = 0
            for chunk in self.split_text(text):
                metadata = dict(_metadatas[i])
                if self._add_start_index:
                    metadata["start_index"] = start_index
                documents.append(Document(page_content=chunk, metadata=metadata))
                start_index += len(chunk)
        return documents

    def split_documents(self, documents: Sequence[Document]) -> List[Document]:
        texts, metadatas = [], []
        for doc in documents:
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)
        return self.create_documents(texts, metadatas=metadatas)

    def transform_documents(self, documents: Sequence[Document], **kwargs: Any) -> Sequence[Document]:
        return self.split_documents(list(documents))

# --- Load & sanitize docs ---------------------------------------------------
BOM = "\ufeff"
UNICODE_FIX = {"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
WS = re.compile(r"\s+")

def _norm(text: str) -> str:
    if not text: return ""
    text = text.replace(BOM, "")
    for k, v in UNICODE_FIX.items(): text = text.replace(k, v)
    return WS.sub(" ", text).strip()

def _save_sanitized(stub: str, text: str) -> None:
    out = os.path.join(SANITIZED_DIR, stub)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: f.write(text)

def _preview(s: str, n: int = 200) -> str:
    if not s: return ""
    s = s.replace("\n"," ").replace("\r"," ")
    return s[:n] + ("…" if len(s) > n else "")

def _load_txt_md(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        txt = _norm(f.read())
    _save_sanitized(os.path.basename(path) + ".san.txt", txt)
    return [(path, txt)]

def _load_pdf(path: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    try:
        import fitz  # PyMuPDF
    except Exception:
        print(f"[WARN] PyMuPDF not installed; skipping PDF: {path}")
        return items
    doc = fitz.open(path); base = os.path.basename(path)
    for i, page in enumerate(doc, start=1):
        txt = _norm(page.get_text("text"))
        if not txt:
            continue
        _save_sanitized(f"{base}.page_{i:04}.txt", txt)
        items.append((f"{path}#page={i}", txt))
    return items

def load_all(data_dir: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for p in sorted(glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)):
        if not os.path.isfile(p): continue
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext in (".txt", ".md"): out.extend(_load_txt_md(p))
            elif ext == ".pdf": out.extend(_load_pdf(p))
        except Exception as e:
            print(f"[WARN] failed to read {p}: {e}")
    return out

# --- Token helpers ----------------------------------------------------------
def _approx_token_len(s: str) -> int:
    return max(1, len(s) // 4)


def _apply_sentence_overlap(chunks: List[str], overlap_sentences: int = 2) -> List[str]:
    # Duplicate the HEAD of each next chunk onto the END of the previous chunk,
    # so every chunk still starts at a full sentence.
    if overlap_sentences <= 0 or len(chunks) < 2:
        return chunks
    sent_re = re.compile(r'(?<=[.!?])["”\')\]]*\s+')

    out: List[str] = [chunks[0].strip()]
    for i in range(1, len(chunks)):
        cur = chunks[i].strip()
        head_sents = sent_re.split(cur)
        head = head_sents[:overlap_sentences] if len(head_sents) >= overlap_sentences else head_sents
        # add head of current chunk to tail of previous
        out[-1] = (out[-1].rstrip() + " " + " ".join(head)).strip()
        # current chunk remains unchanged (starts at full sentence)
        out.append(cur)
    return out


# Sentence packer: keeps whole sentences, even if one exceeds max_tokens (it becomes its own chunk)
_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])["”\')\]]*\s+')

def _pack_sentences_to_token_cap(text: str, max_tokens: int, sentence_split_regex: str = r'(?<=[.?!])\s+') -> List[str]:
    sents = [s.strip() for s in re.split(sentence_split_regex, text) if s.strip()]
    if not sents:
        return []
    chunks, buf, t = [], [], 0
    for s in sents:
        ts = _approx_token_len(s)
        if not buf:
            # start a new chunk with this sentence
            buf, t = [s], ts
            if ts > max_tokens:
                # single very long sentence: keep as its own chunk
                chunks.append(" ".join(buf))
                buf, t = [], 0
            continue
        if t + ts <= max_tokens:
            buf.append(s); t += ts
        else:
            chunks.append(" ".join(buf))
            buf, t = [s], ts
            if ts > max_tokens:
                chunks.append(" ".join(buf))
                buf, t = [], 0
    if buf:
        chunks.append(" ".join(buf))
    return chunks

# --- Semantic chunking wrapper ----------------------------------------------
_semantic_embedder = None
def _get_embedder():
    global _semantic_embedder
    if _semantic_embedder is None:
        _semantic_embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _semantic_embedder

def _semantic_embed(texts, **kwargs):
    model = _get_embedder()
    return [list(v) for v in model.embed(list(texts))]

def recursive_semantic_chunks(
    text: str,
    sim_percentile: float = 95.0,
    buffer_size: int = 1,
    max_tokens: int = 1400,
    overlap_sentences: int = 2,
    max_depth: int = 3,
) -> List[str]:
    """
    Recursively re-split only oversized chunks using the same semantic logic.
    Overlap is applied once at the end. 
    """
    splitter = SemanticChunker(
        embedding_function=_semantic_embed,
        buffer_size=buffer_size,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=sim_percentile,
    )

    def _recur(t: str, depth: int) -> List[str]:
        docs = splitter.create_documents([t])
        parts = [d.page_content.strip() for d in docs if d.page_content and d.page_content.strip()]
        out: List[str] = []
        for c in parts:
            toklen = _approx_token_len(c)
            if toklen > max_tokens:
                if depth < max_depth:
                    sub = _recur(c, depth + 1)
                    
                    if len(sub) == 1 and sub[0] == c:
                        out.extend(_pack_sentences_to_token_cap(c, max_tokens))
                    else:
                        out.extend(sub)
                else:
                    out.extend(_pack_sentences_to_token_cap(c, max_tokens))
            else:
                out.append(c)
        return out

    base = _recur(text, 0)
    return _apply_sentence_overlap(base, overlap_sentences=overlap_sentences)


# --- Ingest: load → chunk → embed → Chroma ----------------------------------
def run_ingest(
    verbose: bool = False,
    print_vectors: bool = False,
    vec_preview_n: int = 8,
    *,
    target_tokens: int = 900,
    max_tokens: int = 1400,
    overlap_sentences: int = 2,
    buffer_size: int = 1,
    sim_percentile: float = 95.0,
    max_depth: int = 3
) -> Dict[str, Any]:
    t0 = time.time()
    docs = load_all(DATA_DIR)
    if not docs: print(f"[WARN] No documents found under {DATA_DIR}")
    total_docs = len(docs)

    items: List[Tuple[str, str, Dict[str, Any]]] = []
    for src, txt in docs:
        chs = recursive_semantic_chunks(txt, sim_percentile, buffer_size, max_tokens, overlap_sentences, max_depth=max_depth,)
        for idx, ch in enumerate(chs):
            cid = f"{src}::chunk_{idx}"
            meta = {
                "source": src, "chunker": "recursive-semantic", "target_tokens": target_tokens,
                "max_tokens": max_tokens, "overlap_sentences": overlap_sentences,
                "buffer_size": buffer_size, "sim_percentile": sim_percentile, "max_depth": max_depth,
            }
            items.append((cid, ch, meta))
            if verbose:
                print(json.dumps({
                    "event": "chunk_created", "id": cid, "source": src,
                    "len_chars": len(ch), "approx_tokens": _approx_token_len(ch),
                    "preview": _preview(ch, 200), "metadata": meta
                }, ensure_ascii=False))

    if not items:
        summary = {
        "num_input_docs": total_docs, "num_chunks": 0,
        "collection": VECTOR_COLLECTION, "embedding_model": EMBEDDING_MODEL,
        "chunker": "recursive-semantic",
        "target_tokens": target_tokens, "max_tokens": max_tokens,
        "overlap_sentences": overlap_sentences, "buffer_size": buffer_size,
        "sim_percentile": sim_percentile, "max_depth": max_depth,
        "elapsed_sec": round(time.time()-t0, 2),
        }
        with open(os.path.join(ARTIFACTS_DIR, "ingest_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print("[WARN] No chunks produced; nothing to upsert.")
        return {"added": 0, **summary}

    client = chromadb.PersistentClient(
    path=VECTOR_STORE_PATH,
    settings=ChromaSettings(anonymized_telemetry=False)
    )
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

    ids, docs_list, metas = [], [], []
    for cid, ch, meta in items:
        ids.append(cid); docs_list.append(ch); metas.append(meta)

    B, added = 256, 0
    for i in range(0, len(ids), B):
        j = i + B
        batch_ids, batch_docs, batch_metas = ids[i:j], docs_list[i:j], metas[i:j]
        embs = []
        for k, e in enumerate(embedder.passage_embed(batch_docs)):
            v = e.tolist() if hasattr(e, "tolist") else e
            embs.append(v)
            if print_vectors:
                preview = list(v[:max(0, int(vec_preview_n))])
                print(json.dumps({
                    "event": "vector_created", "id": batch_ids[k],
                    "vector_dim": len(v), "vector_preview": preview,
                    "chunk_approx_tokens": _approx_token_len(batch_docs[k]),
                }, ensure_ascii=False))
        coll.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas, embeddings=embs)
        added += len(batch_ids)
        if verbose:
            print(json.dumps({"event": "batch_upserted", "batch_size": len(batch_ids)}, ensure_ascii=False))

    lens = [_approx_token_len(c) for c in docs_list]
    chunk_stats = {
        "chunker": "recursive-semantic", "n_chunks": len(docs_list),
        "avg_tokens": round(sum(lens)/len(lens), 1) if lens else 0,
        "min_tokens": min(lens) if lens else 0, "max_tokens": max(lens) if lens else 0,
        "target_tokens": target_tokens, "max_tokens_cap": max_tokens,
        "overlap_sentences": overlap_sentences, "buffer_size": buffer_size,
        "sim_percentile": sim_percentile,
        "max_depth": max_depth, 
    }
    summary = {
        **chunk_stats, "collection": VECTOR_COLLECTION, "embedding_model": EMBEDDING_MODEL,
        "num_input_docs": total_docs, "elapsed_sec": round(time.time()-t0, 2),
    }
    with open(os.path.join(ARTIFACTS_DIR, "ingest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(ARTIFACTS_DIR, "chunk_stats.json"), "w", encoding="utf-8") as f:
        json.dump(chunk_stats, f, indent=2)

    print(f"Indexed {added} chunks into collection '{VECTOR_COLLECTION}'")
    return {"added": added, **summary}

# --- LangChain embeddings adapter -------------------------------------------
class FastEmbedEmbeddings(LcEmbeddings):
    def __init__(self, model_name: str):
        self._model = TextEmbedding(model_name=model_name)

    @staticmethod
    def _to_py_floats(vec):
        # vec can be numpy array or iterable of np.float32
        return [float(x) for x in (vec.tolist() if hasattr(vec, "tolist") else vec)]

    def embed_documents(self, texts):
        return [self._to_py_floats(v) for v in self._model.passage_embed(list(texts))]

    def embed_query(self, text: str):
        try:
            v = next(self._model.query_embed(text))
        except Exception:
            v = next(self._model.passage_embed([text]))
        return self._to_py_floats(v)

# --- Retriever & API (LangChain + Chroma distances) -------------------------
class Retriever:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=VECTOR_STORE_PATH,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # Default metric = cosine. To use L2, re-create collection with metadata below and re-ingest.
        self.collection = self.client.get_or_create_collection(name=VECTOR_COLLECTION)
        # self.collection = self.client.get_or_create_collection(
        #     name=VECTOR_COLLECTION,
        #     metadata={"hnsw:space": "l2"}  # "cosine" (default) or "l2"
        # )

        self.lc_emb = FastEmbedEmbeddings(EMBEDDING_MODEL)

        self.lc_vs = LCChroma(
            client=self.client,
            collection_name=VECTOR_COLLECTION,
            embedding_function=self.lc_emb,
        )
        self.retriever = self.lc_vs.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5},
        )
        self.mode = "chroma-dist"

    def stats(self):
        try:
            cnt = self.collection.count()
        except Exception:
            cnt = None
        meta = getattr(self.collection, "metadata", {}) or {}
        return {
            "collection": VECTOR_COLLECTION,
            "emb_model": EMBEDDING_MODEL,
            "retriever_mode": self.mode,
            "metric": meta.get("hnsw:space", "cosine"),
            "count": cnt,
        }

    def query(self, q: str, k: int = 4):
        if not isinstance(q, str) or not q.strip():
            return []
        k = max(1, min(int(k), 50))
        q_vec = self.lc_emb.embed_query(q)

        res = self.collection.query(
            query_embeddings=[q_vec],
            n_results=k,
            include=["documents", "metadatas", "distances"],  # ids come automatically
        )

        ids   = res.get("ids", [[]])[0]
        docs  = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        out = []
        for i, (doc_id, text, md, dist) in enumerate(zip(ids, docs, metas, dists), start=1):
            out.append({
                "rank": i,
                "id": doc_id,
                "text": text,
                "metadata": md if isinstance(md, dict) else {},
                "distance": float(dist),
            })
        return out


# --- Dump one vector --------------------------------------------------------
def dump_one_vector(out_path: str) -> Dict[str, Any]:
    client = chromadb.PersistentClient(
    path=VECTOR_STORE_PATH,
    settings=ChromaSettings(anonymized_telemetry=False)
    )
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    got = coll.get(limit=1, include=["documents", "metadatas", "embeddings"])
    if not got.get("embeddings"): return {"ok": False, "reason": "no vectors found"}
    vec, doc, meta = got["embeddings"][0], got["documents"][0], got["metadatas"][0]
    payload = {"collection": VECTOR_COLLECTION, "vector_dim": len(vec), "vector": vec, "document": doc, "metadata": meta}
    with open(out_path, "w", encoding="utf-8") as f: json.dump(payload, f, indent=2)
    return {"ok": True, "out": out_path}

# --- FastAPI server ---------------------------------------------------------
def make_app():
    from fastapi import FastAPI
    from pydantic import BaseModel
    app = FastAPI(title="AC215 MS2 RAG API (Semantic + LangChain)")
    retr = Retriever()
    class QueryReq(BaseModel):
        q: str
        k: int = 4
    @app.get("/health")
    def health():
        return {"status": "ok", **retr.stats()}
    @app.post("/query")
    def query(req: QueryReq):
        return {"query": req.q, "results": retr.query(req.q, req.k)}
    return app

def serve():
    import uvicorn
    app = make_app()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, reload=False)

# --- CLI -------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="AC215-MS2 RAG CLI (Semantic + LangChain-only)")
    p.add_argument("--ingest", action="store_true", help="Run ingestion")
    p.add_argument("--serve",  action="store_true", help="Run FastAPI server")
    p.add_argument("--dump-vector", action="store_true", help="Dump one stored embedding")
    p.add_argument("--verbose", action="store_true", help="Verbose chunk logging")
    p.add_argument("--print-vectors", action="store_true", help="Print vectors during embedding")
    p.add_argument("--vec-preview", type=int, default=None, help="Number of vector dims to preview")
    p.add_argument("--target-tokens", type=int, default=900)
    p.add_argument("--max-tokens", type=int, default=1400)
    p.add_argument("--overlap-sentences", type=int, default=2)
    p.add_argument("--buffer-size", type=int, default=1)
    p.add_argument("--sim-percentile", type=float, default=95.0)
    p.add_argument("--max-depth", type=int, default=3, help="Max recursion depth for semantic re-splitting")
    args = p.parse_args()
    if not (args.ingest or args.serve or args.dump_vector): args.ingest = True
    if args.vec_preview is None: args.vec_preview = 8
    args.print_vectors = True
    if args.ingest:
        stats = run_ingest(verbose=(args.verbose or RAG_VERBOSE_ENV),
                           print_vectors=True, vec_preview_n=args.vec_preview,
                           target_tokens=args.target_tokens, max_tokens=args.max_tokens,
                           overlap_sentences=args.overlap_sentences, buffer_size=args.buffer_size,
                           sim_percentile=args.sim_percentile,
                           max_depth=args.max_depth)
        print(json.dumps({"ingest_done": True, **stats}, indent=2))
    if args.dump_vector:
        out_path = os.path.join(ARTIFACTS_DIR, "sample_vector.json")
        res = dump_one_vector(out_path)
        print(json.dumps({"dump_vector": res}, indent=2))
    if args.serve:
        serve()

if __name__ == "__main__":
    main()





