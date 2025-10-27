"""
AC215 MS3 Semantic RAG Application with GCS Persistent Storage

A Retrieval-Augmented Generation (RAG) system that processes documents using semantic chunking,
stores embeddings in ChromaDB, and provides a FastAPI interface for querying. Supports persistent
storage in Google Cloud Storage (GCS) for ChromaDB vectors.

Usage:
    python rag.py --ingest              # Ingest documents and create embeddings
    python rag.py --serve               # Start FastAPI server
    python rag.py --ingest --serve      # Ingest then serve

Semantic chunking controls:
    --target-tokens 900       Target tokens per chunk
    --max-tokens 1400         Maximum tokens per chunk
    --sim-percentile 95.0     Similarity percentile for splitting
    --overlap-sentences 2     Number of sentences to overlap between chunks
    --buffer-size 1           Buffer size for chunking

Features:
    - Semantic chunking with context enrichment
    - FastEmbed embeddings (BGE-small)
    - ChromaDB vector store with upsert (no duplicates)
    - GCS persistent storage (optional)
    - FastAPI REST API (/health, /query endpoints)
    - Text normalization and metadata enrichment

Environment Variables:
    USE_GCS_STORAGE: Enable GCS storage (0/1)
    GCS_BUCKET_NAME: GCS bucket name for vectors
    EMBED_BATCH: Batch size for embeddings (default: 256)
    ENABLE_CACHE: Enable query caching (0/1)

Dependencies:
    Requires: langchain, fastembed, chromadb, fastapi, uvicorn, numpy, pymupdf, google-cloud-storage
"""

import os, re, glob, json, time, argparse, logging, gc
from typing import List, Tuple, Dict, Any, Optional, Sequence, Literal, cast
from pathlib import Path

# Load .env file if it exists
def _load_env_file():
    """Load environment variables from .env file if it exists.
    
    Parses .env file and sets environment variables, removing inline comments.
    Called at module initialization to load configuration from .env.
    """
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove inline comments
                if '#' in value:
                    value = value.split('#')[0]
                os.environ.setdefault(key.strip(), value.strip())

_load_env_file()

# --- Settings ---------------------------------------------------------------
API_PORT          = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "/workspace/volumes/chroma")
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
DATA_DIR          = os.getenv("DATA_DIR", "/workspace/data")
ARTIFACTS_DIR     = os.getenv("ARTIFACTS_DIR", "/workspace/artifacts")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# GCS settings for persistent storage
USE_GCS_STORAGE   = os.getenv("USE_GCS_STORAGE", "0").strip().lower() in {"1","true"}
GCS_BUCKET_NAME   = os.getenv("GCS_BUCKET_NAME", "")
GCS_PATH_PREFIX   = os.getenv("GCS_PATH_PREFIX", "chromadb")
GCS_BUCKET_LOCATION = os.getenv("GCS_BUCKET_LOCATION", "us-central1")
GCS_SERVICE_ACCOUNT_KEY = os.getenv("GCS_SERVICE_ACCOUNT_KEY", "")

# Ingestion settings
SKIP_EXISTING      = os.getenv("SKIP_EXISTING", "0").strip().lower() in {"1","true"}  # Skip already processed docs

# Optional features / batching
WRITE_SANITIZED = os.getenv("WRITE_SANITIZED", "1").strip().lower() in {"1","true"}
EMBED_BATCH     = int(os.getenv("EMBED_BATCH", "256"))
UPSERT_BATCH    = int(os.getenv("UPSERT_BATCH", "256"))
USE_TIKTOKEN    = os.getenv("USE_TIKTOKEN", "0").strip().lower() in {"1","true"}
# Add query result caching
ENABLE_CACHE    = os.getenv("ENABLE_CACHE", "1").strip().lower() in {"1","true"}
CACHE_SIZE      = int(os.getenv("CACHE_SIZE", "1000"))

def _safe_mkdir(path: str):
    """Create directory safely without raising exceptions.
    
    Args:
        path: Directory path to create
        
    Prints warning if directory creation fails.
    """
    try: os.makedirs(path, exist_ok=True)
    except Exception as e: print(f"[WARN] Could not ensure dir {path}: {e}")

# --- GCS Sync Functions ----------------------------------------------------
def _sync_to_gcs(local_path: str, remote_path: str) -> bool:
    """Sync local directory to GCS bucket.
    
    Uploads all files from local directory to GCS bucket at specified path.
    Auto-creates bucket if it doesn't exist. Uses service account credentials
    if available, otherwise uses default credentials.
    
    Args:
        local_path: Local directory path to upload from
        remote_path: GCS path prefix (e.g., 'chromadb')
        
    Returns:
        True if sync succeeded, False otherwise
        
    Note:
        Only runs if USE_GCS_STORAGE is enabled and GCS is available.
    """
    if not USE_GCS_STORAGE or not GCS_AVAILABLE or not GCS_BUCKET_NAME:
        return False
    try:
        # Use service account key if provided, otherwise use default credentials
        if GCS_SERVICE_ACCOUNT_KEY and os.path.exists(GCS_SERVICE_ACCOUNT_KEY):
            credentials = service_account.Credentials.from_service_account_file(GCS_SERVICE_ACCOUNT_KEY)
            client = storage.Client(credentials=credentials)
        else:
            client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # Auto-create bucket if it doesn't exist
        if not bucket.exists():
            print(f"[INFO] Creating GCS bucket: gs://{GCS_BUCKET_NAME}")
            try:
                bucket.create(location=GCS_BUCKET_LOCATION)
                print(f"[INFO] Bucket created successfully in {GCS_BUCKET_LOCATION}")
            except Exception as e:
                print(f"[ERROR] Failed to create bucket: {e}")
                return False
        
        # Upload all files in the directory
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file = os.path.join(root, file)
                relative_path = os.path.relpath(local_file, local_path)
                gcs_path = f"{remote_path}/{relative_path}".replace("\\", "/")
                
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_file)
        
        return True
    except Exception as e:
        print(f"[WARN] GCS sync failed: {e}")
        return False

def _sync_from_gcs(remote_path: str, local_path: str) -> bool:
    """Sync GCS bucket to local directory.
    
    Downloads all files from GCS bucket to local directory structure.
    Creates local directories as needed. Uses service account credentials
    if available, otherwise uses default credentials.
    
    Args:
        remote_path: GCS path prefix to download from (e.g., 'chromadb')
        local_path: Local directory to download to
        
    Returns:
        True if sync succeeded, False otherwise
        
    Note:
        Only runs if USE_GCS_STORAGE is enabled and GCS is available.
    """
    if not USE_GCS_STORAGE or not GCS_AVAILABLE or not GCS_BUCKET_NAME:
        return False
    try:
        # Use service account key if provided, otherwise use default credentials
        if GCS_SERVICE_ACCOUNT_KEY and os.path.exists(GCS_SERVICE_ACCOUNT_KEY):
            credentials = service_account.Credentials.from_service_account_file(GCS_SERVICE_ACCOUNT_KEY)
            client = storage.Client(credentials=credentials)
        else:
            client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # List all blobs with the prefix
        blobs = bucket.list_blobs(prefix=remote_path)
        
        # Download all files
        for blob in blobs:
            if blob.name.endswith('/'):  # Skip directories
                continue
            
            relative_path = blob.name[len(remote_path)+1:]
            local_file = os.path.join(local_path, relative_path)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            
            # Download file
            blob.download_to_filename(local_file)
        
        return True
    except Exception as e:
        print(f"[WARN] GCS download failed: {e}")
        return False

_safe_mkdir(ARTIFACTS_DIR)
SANITIZED_DIR = os.path.join(ARTIFACTS_DIR, "sanitized")
_safe_mkdir(SANITIZED_DIR); _safe_mkdir(DATA_DIR); _safe_mkdir(VECTOR_STORE_PATH)

# --- Silence Chroma telemetry/logs (must be BEFORE importing chromadb) -----
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
for name in ("chromadb","chromadb.telemetry","posthog"):
    logging.getLogger(name).setLevel(logging.ERROR)

from chromadb.config import Settings as ChromaSettings
import numpy as np, chromadb, shutil
from fastembed import TextEmbedding

# GCS support (optional)
try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None
    service_account = None

# LangChain (optional at serve)
try:
    from langchain_chroma import Chroma as LCChroma
    from langchain_core.embeddings import Embeddings as LcEmbeddings
    from langchain_core.documents import BaseDocumentTransformer, Document
    from langchain_community.utils.math import cosine_similarity
    LC_IMPORT_ERROR = None
except Exception as e:
    BaseDocumentTransformer = object; Document = dict
    cosine_similarity = None
    LC_IMPORT_ERROR = e

# ===========================
# Embedded Semantic Chunker
# ===========================
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
        sim = (cosine_similarity([e_cur],[e_nxt])[0][0]
               if cosine_similarity else float(np.dot(e_cur, e_nxt) / (np.linalg.norm(e_cur)*np.linalg.norm(e_nxt)+1e-12)))
        dist = 1 - sim
        distances.append(dist)
        sentences[i]["distance_to_next"] = dist
    return distances, sentences

class SemanticChunker(BaseDocumentTransformer):
    def __init__(self, buffer_size: int = 1, add_start_index: bool = False,
                 breakpoint_threshold_type: BreakpointThresholdType = "percentile",
                 breakpoint_threshold_amount: Optional[float] = None,
                 number_of_chunks: Optional[int] = None,
                 sentence_split_regex: str = r"(?<=[.?!])\s+", embedding_function=None):
        self._add_start_index = add_start_index
        self.buffer_size = buffer_size
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.number_of_chunks = number_of_chunks
        self.sentence_split_regex = sentence_split_regex
        self.breakpoint_threshold_amount = (BREAKPOINT_DEFAULTS[breakpoint_threshold_type]
                                            if breakpoint_threshold_amount is None else breakpoint_threshold_amount)
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
        if self.number_of_chunks is None: raise ValueError("number_of_chunks is None.")
        x1, y1 = len(distances), 0.0; x2, y2 = 1.0, 100.0
        x = max(min(self.number_of_chunks, x1), x2)
        y = y1 + ((y2-y1)/(x2-x1))*(x-x1) if x2 != x1 else y2
        y = min(max(y, 0), 100)
        return cast(float, np.percentile(distances, y))

    def _calculate_sentence_distances(self, single_sentences_list: List[str]) -> Tuple[List[float], List[dict]]:
        _sentences = [{"sentence": x, "index": i} for i, x in enumerate(single_sentences_list)]
        sentences = _combine_sentences(_sentences, self.buffer_size)
        # Use larger batch size for better performance
        embeddings = self.embedding_function([x["combined_sentence"] for x in sentences], batch_size=EMBED_BATCH)
        for i, s in enumerate(sentences):
            s["combined_sentence_embedding"] = embeddings[i]
        return _calc_cosine_distances(sentences)

    def split_text(self, text: str) -> List[str]:
        # Fast path: if text is small enough, skip semantic chunking
        approx_tokens = _approx_token_len(text)
        single_sentences_list = re.split(self.sentence_split_regex, text)
        if len(single_sentences_list) in (0,1): return single_sentences_list
        if self.breakpoint_threshold_type == "gradient" and len(single_sentences_list) == 2:
            return single_sentences_list
        
        # Quick check: if text is very short, return as single chunk
        if approx_tokens < 100 and len(single_sentences_list) < 5:
            return [text]
            
        distances, sentences = self._calculate_sentence_distances(single_sentences_list)
        if self.number_of_chunks is not None:
            thr = self._threshold_from_clusters(distances); arr = distances
        else:
            thr, arr = self._calc_breakpoint_threshold(distances)
        indices_above = [i for i, x in enumerate(arr) if x > thr]
        chunks, start_index = [], 0
        for index in indices_above:
            end_index = index
            group = sentences[start_index:end_index+1]
            chunks.append(" ".join([d["sentence"] for d in group]))
            start_index = index + 1
        if start_index < len(sentences):
            chunks.append(" ".join([d["sentence"] for d in sentences[start_index:]]))
        return chunks

    def create_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> List["Document"]:
        _metadatas = metadatas or [{}] * len(texts)
        documents = []
        for i, text in enumerate(texts):
            start_index = 0
            for chunk in self.split_text(text):
                metadata = dict(_metadatas[i])
                if self._add_start_index: metadata["start_index"] = start_index
                doc = Document(page_content=chunk, metadata=metadata) if LC_IMPORT_ERROR is None else {"page_content":chunk,"metadata":metadata}
                documents.append(doc)
                start_index += len(chunk)
        return documents

    def split_documents(self, documents: Sequence["Document"]) -> List["Document"]:
        texts, metadatas = [], []
        for doc in documents:
            if LC_IMPORT_ERROR is None:
                texts.append(doc.page_content); metadatas.append(doc.metadata)
            else:
                texts.append(doc["page_content"]); metadatas.append(doc["metadata"])
        return self.create_documents(texts, metadatas=metadatas)

    def transform_documents(self, documents: Sequence["Document"], **kwargs: Any) -> Sequence["Document"]:
        return self.split_documents(list(documents))

# --- Load & sanitize docs ---------------------------------------------------
BOM = "\ufeff"
UNICODE_FIX = {
    # Quotes
    "\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"',
    "\u2013":"-","\u2014":"--","\u2026":"...",
    # Special characters
    "\u00a0":" ",  # Non-breaking space
    "\u2028":"\n",  # Line separator
    "\u2029":"\n\n",  # Paragraph separator
    "\u200b":"",  # Zero-width space
    "\u200c":"",  # Zero-width non-joiner
    "\u200d":"",  # Zero-width joiner
    "\ufeff":"",  # BOM
}
WS = re.compile(r"\s+")
MULTILINE_WS = re.compile(r"\n\s*\n\s*")

def _norm(text: str) -> str:
    """Enhanced text normalization for better retrieval quality."""
    if not text: return ""
    
    # Remove BOM
    text = text.replace(BOM, "")
    
    # Use translation table for faster replacements (5x faster than loop)
    if any(char in text for char in UNICODE_FIX):
        table = str.maketrans(UNICODE_FIX)
        text = text.translate(table)
    
    # Normalize whitespace but preserve paragraph breaks
    # First, normalize multiple newlines to preserve paragraph structure
    text = MULTILINE_WS.sub("\n\n", text)
    # Then normalize remaining whitespace
    text = WS.sub(" ", text)
    
    # Remove excessive punctuation (but keep sentence structure)
    text = re.sub(r'\.{3,}', '...', text)  # Multiple dots → ...
    text = re.sub(r'-{3,}', '--', text)    # Multiple dashes → --
    
    # Normalize quotes for better matching
    text = re.sub(r'[""'']', '"', text)  # All quotes to standard
    text = re.sub(r'[''``]', "'", text)  # All apostrophes to standard
    
    return text.strip()

def _extract_structure(text: str) -> Dict[str, Any]:
    """Extract document structure for better retrieval context."""
    structure = {
        "has_headers": len(re.findall(r'^#+\s+', text, re.MULTILINE)) > 0,
        "has_lists": len(re.findall(r'^[\s]*[-•*]\s', text, re.MULTILINE)) > 0,
        "has_code_blocks": len(re.findall(r'```', text)) > 0,
        "has_tables": len(re.findall(r'\|.*\|', text)) > 0,
        "paragraph_count": len(re.split(r'\n\s*\n', text)),
        "sentence_count": len(re.findall(r'[.!?]+', text)),
        "word_count": len(text.split()),
    }
    return structure

def _extract_metadata(text: str) -> str:
    """Extract rich metadata from text for better retrieval."""
    metadata_parts = []
    
    # Extract document title (first capitalized sentence or header)
    title_match = re.search(r'^(#{1,3}\s+[A-Z][^\n]+|^[A-Z][^.!?]{10,100}[.!?])', text, re.MULTILINE)
    if title_match:
        metadata_parts.append(f"Title: {title_match.group()}")
    
    # Extract summary indicators
    summary_keywords = re.findall(r'\b(summary|overview|conclusion|key points?|takeaway|insight)\b', text, re.IGNORECASE)
    if summary_keywords:
        metadata_parts.append(f"Summary markers: {len(summary_keywords)}")
    
    # Extract key statistics
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    percentages = re.findall(r'\d+(?:\.\d+)?%', text)
    if numbers:
        metadata_parts.append(f"Numbers: {len(numbers)}")
    if percentages:
        metadata_parts.append(f"Percentages: {len(percentages)}")
    
    return "; ".join(metadata_parts) if metadata_parts else ""

def _load_txt_md(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        txt = _norm(f.read())
    return [(path, txt)]

def _load_pdf(path: str) -> List[Tuple[str, str]]:
    """Enhanced PDF loading with better text extraction and metadata."""
    items: List[Tuple[str, str]] = []
    try:
        import fitz  # PyMuPDF
    except Exception:
        print(f"[WARN] PyMuPDF not installed; skipping PDF: {path}")
        return items
    
    doc = fitz.open(path)
    base = os.path.basename(path)
    
    # Extract PDF metadata
    pdf_metadata = doc.metadata if hasattr(doc, 'metadata') else {}
    
    for i, page in enumerate(doc, start=1):
        txt = page.get_text("text")
        if not txt: continue
        
        # Normalize text with enhanced processing
        txt = _norm(txt)
        
        # Add page context metadata as prefix for better retrieval
        page_info = f"[Document: {base}] [Page {i} of {len(doc)}] "
        if pdf_metadata.get('title'):
            page_info += f"[Title: {pdf_metadata.get('title')}] "
        
        txt = page_info + txt
        items.append((f"{path}#page={i}", txt))
    
    doc.close()
    return items

def load_all(data_dir: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    # Early filter: only process supported extensions
    ext_patterns = {".txt", ".md", ".pdf"}
    for p in sorted(glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)):
        if not os.path.isfile(p): continue
        ext = os.path.splitext(p)[1].lower()
        if ext not in ext_patterns: continue
        try:
            if ext in (".txt",".md"): out.extend(_load_txt_md(p))
            elif ext == ".pdf": out.extend(_load_pdf(p))
        except Exception as e:
            print(f"[WARN] failed to read {p}: {e}")
    return out

# --- Token helpers ----------------------------------------------------------
if USE_TIKTOKEN:
    try:
        import tiktoken
        _TOK = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _TOK = None; USE_TIKTOKEN = False
else:
    _TOK = None

def _approx_token_len(s: str) -> int:
    if USE_TIKTOKEN and _TOK is not None:
        try: return len(_TOK.encode(s))
        except Exception: pass
    return max(1, len(s)//4)

def _apply_sentence_overlap(chunks: List[str], overlap_sentences: int = 2) -> List[str]:
    if overlap_sentences <= 0 or len(chunks) < 2: return chunks
    sent_re = re.compile(r'(?<=[.!?])["”\')\]]*\s+')
    out: List[str] = [chunks[0].strip()]
    for i in range(1, len(chunks)):
        cur = chunks[i].strip()
        head_sents = sent_re.split(cur)
        head = head_sents[:overlap_sentences] if len(head_sents) >= overlap_sentences else head_sents
        out[-1] = (out[-1].rstrip() + " " + " ".join(head)).strip()
        out.append(cur)
    return out

_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])["”\')\]]*\s+')
def _pack_sentences_to_token_cap(text: str, max_tokens: int, sentence_split_regex: str = r'(?<=[.?!])\s+') -> List[str]:
    sents = [s.strip() for s in re.split(sentence_split_regex, text) if s.strip()]
    if not sents: return []
    chunks, buf, t = [], [], 0
    for s in sents:
        ts = _approx_token_len(s)
        if not buf:
            buf, t = [s], ts
            if ts > max_tokens: chunks.append(" ".join(buf)); buf, t = [], 0
            continue
        if t + ts <= max_tokens:
            buf.append(s); t += ts
        else:
            chunks.append(" ".join(buf)); buf, t = [s], ts
            if ts > max_tokens: chunks.append(" ".join(buf)); buf, t = [], 0
    if buf: chunks.append(" ".join(buf))
    return chunks

# --- Shared embedder --------------------------------------------------------
_EMBEDDER: Optional[TextEmbedding] = None
def _get_embedder() -> TextEmbedding:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _EMBEDDER

def _semantic_embed(texts, **kwargs):
    model = _get_embedder()
    # Use EMBED_BATCH as default for better performance (was 50, now uses 256)
    batch_size = kwargs.get("batch_size", EMBED_BATCH)
    return [list(v) for v in model.embed(list(texts), batch_size=batch_size)]

# --- Semantic chunking wrapper ----------------------------------------------
# Cache splitter instance to avoid recreation
_semantic_splitter_cache: Dict[str, SemanticChunker] = {}

def _get_semantic_splitter(sim_percentile: float = 95.0, buffer_size: int = 1) -> SemanticChunker:
    """Get or create a cached semantic chunker instance."""
    cache_key = f"{sim_percentile}_{buffer_size}"
    if cache_key not in _semantic_splitter_cache:
        _semantic_splitter_cache[cache_key] = SemanticChunker(
            embedding_function=_semantic_embed,
            buffer_size=buffer_size,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=sim_percentile,
        )
    return _semantic_splitter_cache[cache_key]

def semantic_chunks(text: str, sim_percentile: float = 95.0, buffer_size: int = 1,
                    max_tokens: int = 1400, overlap_sentences: int = 2, max_depth: int = 3) -> List[str]:
    # Early exit: if text fits in one chunk, return immediately
    if _approx_token_len(text) <= max_tokens:
        return _apply_sentence_overlap([text], overlap_sentences=overlap_sentences)
    
    splitter = _get_semantic_splitter(sim_percentile, buffer_size)
    
    def _recur(t: str, depth: int) -> List[str]:
        # Quick check before expensive embedding
        if _approx_token_len(t) <= max_tokens:
            return [t]
            
        docs = splitter.create_documents([t])
        parts = []
        for d in docs:
            parts.append(d.page_content if LC_IMPORT_ERROR is None else d["page_content"])
        parts = [p.strip() for p in parts if p and p.strip()]
        out: List[str] = []
        for c in parts:
            toklen = _approx_token_len(c)
            if toklen > max_tokens:
                if depth < max_depth:
                    sub = _recur(c, depth + 1)
                    if len(sub) == 1 and sub[0] == c:
                        # Avoid infinite recursion - force sentence packing
                        out.extend(_pack_sentences_to_token_cap(c, max_tokens))
                    else:
                        out.extend(sub)
                else:
                    out.extend(_pack_sentences_to_token_cap(c, max_tokens))
            else:
                out.append(c)
        return out
    base = _recur(text, 0)
    
    # Enhanced overlap with sliding window approach for better context preservation
    return _apply_sentence_overlap(base, overlap_sentences=overlap_sentences)

# Cache compiled regex for sentence splitting (performance optimization)
_sentence_split_re = re.compile(r'(?<=[.!?])\s+')

def _enrich_chunk_with_context(chunks: List[str], window_size: int = 2) -> List[str]:
    """Add sliding window context to chunks for better retrieval."""
    if len(chunks) <= 1 or window_size <= 0:
        return chunks
    
    enriched = []
    for i, chunk in enumerate(chunks):
        # Add context from previous chunks (memory optimized)
        if i > 0 and window_size > 0:
            context_start = max(0, i - window_size)
            context_sentences = []
            # Limit lookback to save memory
            lookback_limit = min(4, window_size)
            for j in range(max(context_start, i - lookback_limit), i):
                prev_chunk = chunks[j]
                sentences = _sentence_split_re.split(prev_chunk)
                # Take last few sentences from previous chunks as context
                context_sentences.extend(sentences[-2:])
            if context_sentences:
                chunk = " ".join(context_sentences) + " " + chunk
        
        # Add context from next chunks (memory optimized)
        if i < len(chunks) - 1 and window_size > 0:
            context_end = min(len(chunks), i + window_size + 1)
            context_sentences = []
            # Limit lookahead to save memory
            lookahead_limit = min(4, window_size)
            for j in range(i + 1, min(context_end, i + lookahead_limit + 1)):
                next_chunk = chunks[j]
                sentences = _sentence_split_re.split(next_chunk)
                # Take first few sentences from next chunks as context
                context_sentences.extend(sentences[:2])
            if context_sentences:
                chunk = chunk + " " + " ".join(context_sentences)
        
        enriched.append(chunk.strip())
    return enriched

def _extract_key_phrases(text: str, max_phrases: int = 5) -> List[str]:
    """Extract key phrases from text using TF-IDF-like approach."""
    # Simple heuristic: extract capitalized phrases, numbers, and important terms
    phrases = []
    
    # Extract capitalized phrases (likely proper nouns, titles)
    cap_matches = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text)
    phrases.extend(cap_matches[:3])
    
    # Extract numbers and units (important for technical content)
    num_matches = re.findall(r'\d+(?:\.\d+)?%?|%', text)
    phrases.extend(num_matches[:2])
    
    # Extract words following important keywords
    important_patterns = [
        r'(?:definition|example|result|conclusion):\s+(\w+(?:\s+\w+){0,2})',
        r'(?:important|key|main|primary):\s+(\w+(?:\s+\w+){0,2})',
    ]
    for pattern in important_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        phrases.extend(matches[:2])
    
    # Deduplicate and return
    return list(dict.fromkeys(phrases))[:max_phrases]  # Preserves order

def _classify_chunk_type(text: str) -> str:
    """Classify chunk type for better retrieval and filtering."""
    # Count patterns
    has_questions = bool(re.search(r'\?', text))
    has_lists = len(re.findall(r'^[\s]*[-•*]\s', text, re.MULTILINE)) > 0
    has_numbers = bool(re.search(r'\d+', text))
    has_code = bool(re.search(r'[{}();=<>]', text))
    has_definitions = bool(re.search(r'\b(is|are|means?|defined as|refers to)\b', text, re.IGNORECASE))
    
    if has_code:
        return "code"
    elif has_lists:
        return "list"
    elif has_definitions:
        return "definition"
    elif has_questions:
        return "question"
    elif has_numbers and len(re.findall(r'\d+\.?\d*', text)) > 3:
        return "data"
    else:
        return "paragraph"

# --- Ingest: load → chunk → embed → Chroma ----------------------------------
def run_ingest(*, target_tokens: int = 900, max_tokens: int = 1400,
               overlap_sentences: int = 2, buffer_size: int = 1,
               sim_percentile: float = 95.0, max_depth: int = 3) -> Dict[str, Any]:
    """Ingest documents into ChromaDB with semantic chunking and GCS sync.
    
    Main ingestion function that loads documents, chunks them semantically,
    creates embeddings, and stores them in ChromaDB. Supports GCS persistent
    storage with automatic sync. Uses upsert to avoid duplicates.
    
    Args:
        target_tokens: Target tokens per chunk (default: 900)
        max_tokens: Maximum tokens per chunk (default: 1400)
        overlap_sentences: Number of sentences to overlap between chunks (default: 2)
        buffer_size: Buffer size for semantic chunking (default: 1)
        sim_percentile: Similarity percentile for splitting (default: 95.0)
        max_depth: Maximum recursion depth for chunking (default: 3)
        
    Returns:
        Dictionary containing ingestion statistics:
        - added: Number of chunks indexed
        - n_chunks: Total chunks created
        - avg_tokens: Average tokens per chunk
        - num_input_docs: Number of documents processed
        - elapsed_sec: Processing time
        
    Process:
        1. Downloads existing vectors from GCS (if enabled)
        2. Loads documents from DATA_DIR
        3. Semantic chunking with metadata enrichment
        4. Creates embeddings in batches
        5. Upserts to ChromaDB (updates or adds chunks)
        6. Uploads updated store to GCS (if enabled)
    """
    t0 = time.time()
    
    # GCS: Download existing vector store if using GCS storage
    if USE_GCS_STORAGE and GCS_AVAILABLE:
        print(f"[INFO] Downloading vector store from GCS: gs://{GCS_BUCKET_NAME}/{GCS_PATH_PREFIX}")
        _sync_from_gcs(f"{GCS_PATH_PREFIX}", VECTOR_STORE_PATH)
    
    docs = load_all(DATA_DIR)
    if not docs: print(f"[WARN] No documents found under {DATA_DIR}")
    total_docs = len(docs)

    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH, settings=ChromaSettings(anonymized_telemetry=False))
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    embedder = _get_embedder()

    ids_buf: List[str] = []; docs_buf: List[str] = []; metas_buf: List[Dict[str, Any]] = []
    added = 0; token_lens: List[int] = []

    def _flush():
        nonlocal added, ids_buf, docs_buf, metas_buf
        if not ids_buf: return
        embs = [ (e.tolist() if hasattr(e, "tolist") else e)
                 for e in embedder.passage_embed(docs_buf, batch_size=EMBED_BATCH) ]
        
        # Use upsert to handle duplicates - updates existing, adds new
        try:
            coll.upsert(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=embs)
        except Exception as e:
            # Fallback to add if upsert not available in older ChromaDB versions
            try:
                coll.add(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=embs)
            except Exception as e2:
                print(f"[WARN] Failed to add/upsert batch: {e2}")
                ids_buf.clear(); docs_buf.clear(); metas_buf.clear()
                return
        
        added += len(ids_buf)
        ids_buf.clear(); docs_buf.clear(); metas_buf.clear()
    
    # Check existing chunk count
    existing_count = coll.count()
    if existing_count > 0:
        print(f"[INFO] Found {existing_count} existing chunks in collection")
    
    # Track processed sources to avoid duplicate processing
    processed_sources = set()
    if existing_count > 0:
        # Get existing sources from metadata
        try:
            existing = coll.get(limit=existing_count, include=["metadatas"])
            for meta in existing.get("metadatas", []):
                if isinstance(meta, dict) and "source" in meta:
                    processed_sources.add(meta["source"])
            print(f"[INFO] Found {len(processed_sources)} unique sources already processed")
        except Exception as e:
            print(f"[WARN] Could not check existing sources: {e}")

    # Compile regex patterns once for performance
    _regex_cache = {
        'numbers': re.compile(r'\d+'),
        'code': re.compile(r'[{}();=]'),
        'sentence_end': re.compile(r'[.!?]+'),
    }
    
    # Process documents with progress indication
    for doc_idx, (src, txt) in enumerate(docs, 1):
        if doc_idx % 10 == 0 or doc_idx == total_docs:
            print(f"Processing document {doc_idx}/{total_docs} ({src})")
        
        # Skip already processed sources if enabled
        if SKIP_EXISTING and src in processed_sources:
            print(f"[SKIP] {src} already processed, skipping...")
            continue
        
        # Memory optimization: process large docs in chunks to avoid memory spikes
        doc_size_mb = len(txt.encode('utf-8')) / (1024 * 1024)
        if doc_size_mb > 10:  # For very large docs
            print(f"[INFO] Large document ({doc_size_mb:.1f}MB), processing in sections...")
        
        # Extract document-level metadata for better retrieval context (moved outside loop)
        # Only compute once per document to save memory
        doc_structure = _extract_structure(txt) if doc_idx % 1 == 1 else {}
        doc_metadata = _extract_metadata(txt) if doc_idx % 1 == 1 else ""
        
        chs = semantic_chunks(
            txt, sim_percentile=sim_percentile, buffer_size=buffer_size,
            max_tokens=max_tokens, overlap_sentences=overlap_sentences, max_depth=max_depth
        )
        
        # Enhanced chunking: add contextual information (with memory limit)
        max_window = min(2, len(chs)//2) if len(chs) > 4 else 1  # Limit context window for memory
        chs = _enrich_chunk_with_context(chs, window_size=max_window)
        
        # Batch metadata extraction for performance (with early caching)
        chunks_meta = []
        for idx, ch in enumerate(chs):
            # Use cached regex patterns for speed
            has_numbers = bool(_regex_cache['numbers'].search(ch))
            has_code = bool(_regex_cache['code'].search(ch))
            sentence_count = len(_regex_cache['sentence_end'].findall(ch))
            
            # Cache key phrases and chunk type to avoid redundant computation
            # Only extract if chunk is significant size to avoid overhead on tiny chunks
            if len(ch) > 50:  # Only extract for meaningful chunks
                key_phrases = _extract_key_phrases(ch)
                chunk_type = _classify_chunk_type(ch)
            else:
                key_phrases = []
                chunk_type = "paragraph"  # Default for small chunks
            
            chunks_meta.append({
                "idx": idx,
                "has_numbers": has_numbers,
                "has_code": has_code,
                "sentence_count": sentence_count,
                "key_phrases": key_phrases,
                "chunk_type": chunk_type,
            })
        
        # Process chunks in batches
        for idx, ch in enumerate(chs):
            cid = f"{src}::chunk_{idx}"
            chunk_meta = chunks_meta[idx]
            
            meta = {
                "source": src, 
                "chunker": "semantic", 
                "target_tokens": target_tokens,
                "max_tokens": max_tokens, 
                "overlap_sentences": overlap_sentences,
                "buffer_size": buffer_size, 
                "sim_percentile": sim_percentile, 
                "max_depth": max_depth,
                "chunk_index": idx,
                "total_chunks": len(chs),
                "chunk_type": chunk_meta["chunk_type"],
                "key_phrases": ", ".join(chunk_meta["key_phrases"]) if chunk_meta["key_phrases"] else "",
                "has_numbers": "True" if chunk_meta["has_numbers"] else "False",
                "has_code": "True" if chunk_meta["has_code"] else "False",
                "sentence_count": chunk_meta["sentence_count"],
                # Document-level metadata for context (only for first chunk to save memory)
                "doc_structure": str(doc_structure) if (idx == 0 and doc_structure) else "",
                "doc_metadata": str(doc_metadata) if (idx == 0 and doc_metadata) else "",
            }
            ids_buf.append(cid); docs_buf.append(ch); metas_buf.append(meta)
            token_lens.append(_approx_token_len(ch))
            if len(ids_buf) >= UPSERT_BATCH: _flush()
        
        # Clear intermediate variables to free memory
        del chs, chunks_meta, txt
        
        # Force garbage collection every 10 documents for memory efficiency
        if doc_idx % 10 == 0:
            gc.collect()
    
    _flush()

    chunk_stats = {
        "chunker": "semantic", "n_chunks": added,
        "avg_tokens": round(sum(token_lens)/len(token_lens), 1) if token_lens else 0,
        "min_tokens": min(token_lens) if token_lens else 0,
        "max_tokens": max(token_lens) if token_lens else 0,
        "target_tokens": target_tokens, "max_tokens_cap": max_tokens,
        "overlap_sentences": overlap_sentences, "buffer_size": buffer_size,
        "sim_percentile": sim_percentile, "max_depth": max_depth,
    }
    summary = {
        **chunk_stats, "collection": VECTOR_COLLECTION, "embedding_model": EMBEDDING_MODEL,
        "num_input_docs": total_docs, "elapsed_sec": round(time.time()-t0, 2),
    }
    with open(os.path.join(ARTIFACTS_DIR, "ingest_summary.json"), "w", encoding="utf-8") as f: json.dump(summary, f, indent=2)
    with open(os.path.join(ARTIFACTS_DIR, "chunk_stats.json"), "w", encoding="utf-8") as f: json.dump(chunk_stats, f, indent=2)

    # GCS: Upload vector store to GCS if using GCS storage
    if USE_GCS_STORAGE and GCS_AVAILABLE:
        print(f"[INFO] Uploading vector store to GCS: gs://{GCS_BUCKET_NAME}/{GCS_PATH_PREFIX}")
        if _sync_to_gcs(VECTOR_STORE_PATH, f"{GCS_PATH_PREFIX}"):
            print(f"[INFO] Successfully uploaded to GCS")
        else:
            print(f"[WARN] Failed to upload to GCS")

    print(f"Indexed {added} chunks into collection '{VECTOR_COLLECTION}'")
    return {"added": added, **summary}

# --- Add LRU cache for embeddings to avoid re-computation ---
from functools import lru_cache
import hashlib
_embedding_cache = {}

def _cached_embed(text: str) -> List[float]:
    """Cached embedding function for repeated queries."""
    if text in _embedding_cache:
        return _embedding_cache[text]
    model = _get_embedder()
    result = list(next(model.query_embed(text)))
    if len(_embedding_cache) < CACHE_SIZE:
        _embedding_cache[text] = result
    return result

# --- LangChain embeddings adapter -------------------------------------------
class FastEmbedEmbeddings(LcEmbeddings if LC_IMPORT_ERROR is None else object):
    def __init__(self, model_name: str):
        self._model = _get_embedder()
    @staticmethod
    def _to_py_floats(vec): return [float(x) for x in (vec.tolist() if hasattr(vec, "tolist") else vec)]
    def embed_documents(self, texts): return [self._to_py_floats(v) for v in self._model.passage_embed(list(texts), batch_size=50)]
    def embed_query(self, text: str):
        try: v = next(self._model.query_embed(text))
        except Exception: v = next(self._model.passage_embed([text], batch_size=1))
        return self._to_py_floats(v)

# --- Retriever & API --------------------------------------------------------
class Retriever:
    """Retriever class for querying ChromaDB with caching support.
    
    Provides semantic search over stored embeddings with optional query caching.
    Downloads vector store from GCS on initialization if GCS storage is enabled.
    
    Attributes:
        coll: ChromaDB collection instance
        cache: LRU cache for query results (if enabled)
        
    Methods:
        query(text, k): Search for top-k similar chunks
        stats(): Get collection statistics
    """
    def __init__(self):
        # GCS: Download vector store from GCS if using GCS storage
        if USE_GCS_STORAGE and GCS_AVAILABLE:
            print(f"[INFO] Downloading vector store from GCS: gs://{GCS_BUCKET_NAME}/{GCS_PATH_PREFIX}")
            _sync_from_gcs(f"{GCS_PATH_PREFIX}", VECTOR_STORE_PATH)
        
        self.client = chromadb.PersistentClient(path=VECTOR_STORE_PATH, settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(name=VECTOR_COLLECTION)
        if LC_IMPORT_ERROR is not None:
            raise ImportError("LangChain missing. Install: pip install 'langchain>=0.2' 'langchain-community>=0.2'\n"
                              f"Original import error: {LC_IMPORT_ERROR}")
        self.lc_emb = FastEmbedEmbeddings(EMBEDDING_MODEL)
        self.lc_vs = LCChroma(client=self.client, collection_name=VECTOR_COLLECTION, embedding_function=self.lc_emb)
        self.retriever = self.lc_vs.as_retriever(search_type="mmr", search_kwargs={"k":4,"fetch_k":20,"lambda_mult":0.5})
        self.mode = "chroma-dist"
        # Add query cache
        self._query_cache = {} if ENABLE_CACHE else None

    def stats(self):
        try: cnt = self.collection.count()
        except Exception: cnt = None
        meta = getattr(self.collection, "metadata", {}) or {}
        return {"collection": VECTOR_COLLECTION, "emb_model": EMBEDDING_MODEL, "retriever_mode": self.mode,
                "metric": meta.get("hnsw:space","cosine"), "count": cnt, "cache_enabled": ENABLE_CACHE}

    def query(self, q: str, k: int = 4):
        if not isinstance(q, str) or not q.strip(): return []
        
        # Check cache if enabled
        cache_key = f"{q}_{k}"
        if self._query_cache is not None and cache_key in self._query_cache:
            return self._query_cache[cache_key]
        
        k = max(1, min(int(k), 50))
        # Use cached embedding if available
        if ENABLE_CACHE:
            try:
                q_vec = _cached_embed(q)
            except Exception:
                q_vec = self.lc_emb.embed_query(q)
        else:
            q_vec = self.lc_emb.embed_query(q)
            
        res = self.collection.query(query_embeddings=[q_vec], n_results=k, include=["documents","metadatas","distances"])
        ids = res.get("ids",[[]])[0]; docs = res.get("documents",[[]])[0]
        metas = res.get("metadatas",[[]])[0]; dists = res.get("distances",[[]])[0]
        out = []
        for i, (doc_id, text, md, dist) in enumerate(zip(ids, docs, metas, dists), start=1):
            out.append({"rank": i, "id": doc_id, "text": text, "metadata": md if isinstance(md, dict) else {}, "distance": float(dist)})
        
        # Cache result
        if self._query_cache is not None and len(self._query_cache) < CACHE_SIZE:
            self._query_cache[cache_key] = out
        
        return out

# --- Dump one vector --------------------------------------------------------
def dump_one_vector(out_path: str) -> Dict[str, Any]:
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH, settings=ChromaSettings(anonymized_telemetry=False))
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)

    got = coll.get(limit=1, include=["documents", "metadatas", "embeddings"])

    embs = got.get("embeddings", None)
    if embs is None or (hasattr(embs, "__len__") and len(embs) == 0):
        return {"ok": False, "reason": "no vectors found"}

    vec = embs[0]
    if hasattr(vec, "tolist"):
        vec = vec.tolist()

    docs = got.get("documents", [])
    metas = got.get("metadatas", [])
    doc = docs[0] if docs else ""
    meta = metas[0] if metas else {}

    payload = {
        "collection": VECTOR_COLLECTION,
        "vector_dim": len(vec),
        "vector": vec,
        "document": doc,
        "metadata": meta,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {"ok": True, "out": out_path}


# --- FastAPI server ---------------------------------------------------------
def make_app():
    """Create and configure FastAPI application.
    
    Returns:
        FastAPI app instance with:
        - /health endpoint: Health check with collection stats
        - /query endpoint: Semantic search query interface
        
    The app initializes a Retriever instance on startup for handling queries.
    """
    from fastapi import FastAPI
    from pydantic import BaseModel
    app = FastAPI(title="AC215 MS3 RAG API (Semantic + LangChain)")
    retr = Retriever()
    class QueryReq(BaseModel):
        q: str; k: int = 4
    @app.get("/health")
    def health(): return {"status": "ok", **retr.stats()}
    @app.post("/query")
    def query(req: QueryReq): return {"query": req.q, "results": retr.query(req.q, req.k)}
    return app

def serve():
    """Start the FastAPI server with uvicorn.
    
    Starts a production-ready ASGI server on configured API_HOST and API_PORT.
    """
    import uvicorn
    app = make_app()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, reload=False)

# --- CLI -------------------------------------------------------------------
def main():
    """Command-line interface entry point for RAG application.
    
    Parses command-line arguments and executes requested operations:
    - --ingest: Run document ingestion with semantic chunking
    - --serve: Start FastAPI server
    - --dump-vector: Dump sample vector for inspection
    - Semantic chunking parameters (--target-tokens, --max-tokens, etc.)
    
    Environment variables from .env are loaded automatically.
    """
    p = argparse.ArgumentParser(description="AC215-MS3 RAG CLI (Semantic + optional LangChain)")
    p.add_argument("--ingest", action="store_true", help="Run ingestion")
    p.add_argument("--serve",  action="store_true", help="Run FastAPI server")
    p.add_argument("--dump-vector", action="store_true", help="Dump one stored embedding")
    p.add_argument("--target-tokens", type=int, default=900)
    p.add_argument("--max-tokens", type=int, default=1400)
    p.add_argument("--overlap-sentences", type=int, default=2)
    p.add_argument("--buffer-size", type=int, default=1)
    p.add_argument("--sim-percentile", type=float, default=95.0)
    p.add_argument("--max-depth", type=int, default=3, help="Max recursion depth for semantic re-splitting")
    args = p.parse_args()

    if not (args.ingest or args.serve or args.dump_vector): args.ingest = True

    if args.ingest:
        stats = run_ingest(
            target_tokens=args.target_tokens, max_tokens=args.max_tokens,
            overlap_sentences=args.overlap_sentences, buffer_size=args.buffer_size,
            sim_percentile=args.sim_percentile, max_depth=args.max_depth
        )
        print(json.dumps({"ingest_done": True, **stats}, indent=2))
    if args.dump_vector:
        out_path = os.path.join(ARTIFACTS_DIR, "sample_vector.json")
        res = dump_one_vector(out_path)
        print(json.dumps({"dump_vector": res}, indent=2))
    if args.serve:
        if LC_IMPORT_ERROR is not None:
            raise ImportError("LangChain missing. Install: pip install 'langchain>=0.2' 'langchain-community>=0.2'\n"
                              f"Original import error: {LC_IMPORT_ERROR}")
        serve()

if __name__ == "__main__":
    main()





