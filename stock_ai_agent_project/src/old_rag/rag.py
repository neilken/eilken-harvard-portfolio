# — AC215 MS2 single-CLI for ingest + serve
#
# Usage:
#   python rag.py --ingest              # one-shot indexing
#   python rag.py --serve               # start FastAPI (/health, /query)
#   python rag.py --ingest --serve      # index then serve
#   python rag.py --dump-vector         # dump one stored vector to artifacts/sample_vector.json

import os, re, glob, json, time, argparse
from typing import List, Tuple, Dict, Any

# --- Settings (single source of truth) ---------------------------------------
API_PORT          = int(os.getenv("API_PORT", "8000"))
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "./volumes/chroma")
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
DATA_DIR          = os.getenv("DATA_DIR", "./data")
ARTIFACTS_DIR     = os.getenv("ARTIFACTS_DIR", "./artifacts")
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", "150"))
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Ensure runtime dirs exist (create parents first, tolerate read-only mounts)
def _safe_mkdir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        print(f"[WARN] Cannot create directory (permission): {path}")
    except FileExistsError:
        pass
    except Exception as e:
        print(f"[WARN] Could not ensure dir {path}: {e}")

# Create parents first, then subdirs
_safe_mkdir(ARTIFACTS_DIR)
SANITIZED_DIR = os.path.join(ARTIFACTS_DIR, "sanitized")
_safe_mkdir(SANITIZED_DIR)
_safe_mkdir(DATA_DIR)
_safe_mkdir(VECTOR_STORE_PATH)

# --- Dependencies that both ingest + serve share ----------------------------
import chromadb
from chromadb.config import Settings as ChromaSettings  # not strictly needed w/ PersistentClient
from fastembed import TextEmbedding

# --- Helpers: sanitize + load docs (txt/md/pdf) ------------------------------
BOM = "\ufeff"
UNICODE_FIX = {
    "\u2013": "-", "\u2014": "-",
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
}
WS = re.compile(r"\s+")

def _norm(text: str) -> str:
    """Remove BOM, normalize punctuation, and collapse ALL whitespace to single spaces."""
    if not text:
        return ""
    text = text.replace(BOM, "")
    for k, v in UNICODE_FIX.items():
        text = text.replace(k, v)
    return WS.sub(" ", text).strip()

def _save_sanitized(stub: str, text: str) -> None:
    out = os.path.join(SANITIZED_DIR, stub)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)

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
    doc = fitz.open(path)
    base = os.path.basename(path)
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
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext in (".txt", ".md"):
                out.extend(_load_txt_md(p))
            elif ext == ".pdf":
                out.extend(_load_pdf(p))
        except Exception as e:
            print(f"[WARN] failed to read {p}: {e}")
    return out

# --- Chunking (size/overlap) -------------------------------------------------
def split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Safe splitter: clamps overlap to [0, chunk_size-1] and walks text once."""
    text = text or ""
    chunk_size = max(1, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 1))
    chunks: List[str] = []
    i, L = 0, len(text)
    while i < L:
        j = min(i + chunk_size, L)
        chunks.append(text[i:j])
        if j == L:
            break
        i = j - overlap
    return chunks

# --- Ingestion: load → chunk → embed → chroma upsert -------------------------
def run_ingest() -> Dict[str, Any]:
    t0 = time.time()
    docs = load_all(DATA_DIR)
    if not docs:
        print(f"[WARN] No documents found under {DATA_DIR}")
    total_docs = len(docs)

    items: List[Tuple[str, str, Dict[str, Any]]] = []
    for src, txt in docs:
        for idx, ch in enumerate(split_text(txt, CHUNK_SIZE, CHUNK_OVERLAP)):
            cid = f"{src}::chunk_{idx}"
            items.append((cid, ch, {"source": src}))

    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

    ids, docs_list, metas = [], [], []
    for cid, ch, meta in items:
        ids.append(cid)
        docs_list.append(ch)
        metas.append(meta)

    B = 256
    added = 0
    for i in range(0, len(ids), B):
        j = i + B
        batch_ids   = ids[i:j]
        batch_docs  = docs_list[i:j]
        batch_metas = metas[i:j]

        embs = []
        for e in embedder.passage_embed(batch_docs):
            embs.append(e.tolist() if hasattr(e, "tolist") else e)

        coll.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas, embeddings=embs)
        added += len(batch_ids)

    # artifacts
    summary = {
        "num_input_docs": total_docs,
        "num_chunks": len(items),
        "collection": VECTOR_COLLECTION,
        "data_dir": DATA_DIR,
        "vector_store_path": VECTOR_STORE_PATH,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    with open(os.path.join(ARTIFACTS_DIR, "ingest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # retrieval sanity check
    try:
        q = "What is P/E ratio?"
        q_emb = next(TextEmbedding(model_name=EMBEDDING_MODEL).query_embed(q))
        if hasattr(q_emb, "tolist"):
            q_emb = q_emb.tolist()
        res = coll.query(query_embeddings=[q_emb], n_results=2, include=["documents","metadatas","distances"])
        with open(os.path.join(ARTIFACTS_DIR, "retrieval_sample.json"), "w", encoding="utf-8") as f:
            json.dump({"query": q, "results": res}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        with open(os.path.join(ARTIFACTS_DIR, "retrieval_sample.json"), "w", encoding="utf-8") as f:
            json.dump({"query": "What is P/E ratio?", "error": str(e)}, f, ensure_ascii=False, indent=2)

    with open(os.path.join(ARTIFACTS_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "collection": VECTOR_COLLECTION,
            "num_chunks": len(items),
            "embedding_model": EMBEDDING_MODEL,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP
        }, f, ensure_ascii=False, indent=2)

    print(f"Indexed {added} chunks into collection '{VECTOR_COLLECTION}'")
    return {"added": added, **summary}

# --- Retriever (shared by API and CLI) --------------------------------------
class Retriever:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
        self.collection = self.client.get_or_create_collection(name=VECTOR_COLLECTION)
        self.model = TextEmbedding(model_name=EMBEDDING_MODEL)

    def stats(self):
        try:
            cnt = self.collection.count()
        except Exception:
            cnt = None
        return {
            "collection": VECTOR_COLLECTION,
            "emb_model": EMBEDDING_MODEL,
            "count": cnt
        }

    def _embed_query(self, q: str):
        if not isinstance(q, str) or not q.strip():
            return None
        # Prefer query encoder, fallback to passage encoder (fastembed API)
        try:
            e = next(self.model.query_embed(q))
            return e.tolist() if hasattr(e, "tolist") else e
        except Exception:
            e = next(self.model.passage_embed([q]))
            return e.tolist() if hasattr(e, "tolist") else e

    def query(self, q: str, k: int = 4):
        if not isinstance(q, str) or not q.strip():
            return []
        try:
            k = max(1, min(int(k), 50))
        except Exception:
            k = 4
        q_emb = self._embed_query(q)
        if q_emb is None:
            return []
        try:
            res = self.collection.query(
                query_embeddings=[q_emb],
                n_results=k,
                include=["documents","metadatas","distances"],
            )
        except Exception:
            return []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out = []
        for i in range(min(k, len(docs))):
            out.append({
                "rank": i + 1,
                "text": docs[i],
                "metadata": metas[i] if i < len(metas) and isinstance(metas[i], dict) else {},
                "distance": dists[i] if i < len(dists) else None,
            })
        return out

# --- Utility: dump a stored vector ------------------------------------------
def dump_one_vector(out_path: str) -> Dict[str, Any]:
    """
    Fetch a single stored embedding vector from the Chroma collection and save
    it to out_path as JSON. Returns a compact summary for stdout.
    """
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)

    try:
        count = coll.count()
    except Exception:
        count = None
    if not count:
        return {"ok": False, "reason": "collection is empty", "collection": VECTOR_COLLECTION}

    # Do NOT include "ids" (Chroma returns ids automatically)
    got = coll.get(limit=1, include=["documents", "metadatas", "embeddings"])
    ids   = (got.get("ids") or [])
    embs  = (got.get("embeddings") or [])
    docs  = (got.get("documents") or [])
    metas = (got.get("metadatas") or [])

    if not ids or not embs:
        return {"ok": False, "reason": "no embeddings returned", "collection": VECTOR_COLLECTION}

    vec = embs[0]
    payload = {
        "collection": VECTOR_COLLECTION,
        "id": ids[0],
        "vector_dim": len(vec) if hasattr(vec, "__len__") else None,
        "vector": vec,
        "document": docs[0] if docs else None,
        "metadata": metas[0] if metas else None,
    }

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "collection": VECTOR_COLLECTION,
        "id": payload["id"],
        "vector_dim": payload["vector_dim"],
        "out": out_path,
    }


# --- Optional FastAPI server -------------------------------------------------
# Only import FastAPI/uvicorn when serving, so 'python rag.py --ingest' stays light.
def make_app():
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="AC215 MS2 RAG API")
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

# --- CLI --------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="AC215-MS2 RAG CLI")
    p.add_argument("--ingest", action="store_true", help="Run ingestion (load→chunk→embed→store)")
    p.add_argument("--serve",  action="store_true", help="Run FastAPI server (/health, /query)")
    p.add_argument("--dump-vector", action="store_true",
                   help="Dump a sample stored embedding to artifacts/sample_vector.json")
    args = p.parse_args()

    # If no main actions, still allow dump-vector as a standalone utility.
    if not (args.ingest or args.serve or args.dump_vector):
        p.print_help()
        return

    if args.ingest:
        stats = run_ingest()
        # print compact summary to stdout
        print(json.dumps({"ingest_done": True, **stats}, indent=2))

    if args.serve:
        serve()

    if args.dump_vector:
        out_path = os.path.join(ARTIFACTS_DIR, "sample_vector.json")
        res = dump_one_vector(out_path)
        print(json.dumps({"dump_vector": res}, indent=2))

if __name__ == "__main__":
    main()


