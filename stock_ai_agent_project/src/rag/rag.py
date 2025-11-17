"""
AC215 MS3 Semantic RAG Application with ChromaDB HTTP Client + GCS Python Client

A Retrieval-Augmented Generation (RAG) system that processes documents using semantic chunking,
stores embeddings in ChromaDB via HTTP client, and provides a FastAPI interface for querying.
Requires ChromaDB server to be running separately. Uses GCS Python client to sync ChromaDB data to/from GCS.

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
    - ChromaDB HTTP client (queries remote server)
    - ChromaDB vector store with upsert (no duplicates)
    - GCS Python client sync for data persistence (required)
    - FastAPI REST API (/health, /query endpoints)
    - Text normalization and metadata enrichment

Environment Variables:
    CHROMADB_HOST: ChromaDB server hostname (default: localhost)
    CHROMADB_PORT: ChromaDB server port (default: 8000)
    CHROMADB_AUTH_TOKEN: Optional authentication token
    GCS_BUCKET_NAME: GCS bucket name (required - ChromaDB data will be synced to/from this bucket)
    EMBED_BATCH: Batch size for embeddings (default: 256)
    ENABLE_CACHE: Enable query caching (0/1)
    ENABLE_SECTION_FILTER: Enable chapter-aware filtering - includes all pages from first chapter to last chapter, excluding front/back matter (0/1, default: 1)

Dependencies:
    Requires: fastembed, chromadb, fastapi, uvicorn, numpy, pymupdf, google-cloud-storage

Prerequisites:
    ChromaDB server must be running (see CHROMADB_HTTP_SETUP.md)
    Start server: docker run -d --name chromadb-server -p 8000:8000 chromadb/chroma:latest
"""

import os, re, glob, json, time, argparse, logging, gc, subprocess, stat, csv
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
API_HOST          = os.getenv("API_HOST", "0.0.0.0")
API_PORT          = int(os.getenv("PORT", os.getenv("API_PORT", "9000")))
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
DATA_DIR          = os.getenv("DATA_DIR", "/workspace/data")
ARTIFACTS_DIR     = os.getenv("ARTIFACTS_DIR", "/workspace/artifacts")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# ChromaDB HTTP client configuration
CHROMADB_HOST    = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT    = int(os.getenv("CHROMADB_PORT", "8000"))
CHROMADB_AUTH_TOKEN = os.getenv("CHROMADB_AUTH_TOKEN", "")
# ChromaDB server data path (local directory, synced with GCS)
CHROMADB_SERVER_DATA_PATH = os.getenv("CHROMADB_SERVER_DATA_PATH", "/chroma")

# GCS settings for Python client sync (required - no fallback)
GCS_BUCKET_NAME   = os.getenv("GCS_BUCKET_NAME", "")
GCS_BUCKET_LOCATION = os.getenv("GCS_BUCKET_LOCATION", "us-central1")
# GCP Project Number (optional, for bucket creation)
GCP_PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "")

# Ingestion settings
SKIP_EXISTING      = os.getenv("SKIP_EXISTING", "0").strip().lower() in {"1","true"}  # Skip already processed docs

# Section filtering settings
ENABLE_SECTION_FILTER = os.getenv("ENABLE_SECTION_FILTER", "1").strip().lower() in {"1","true"}  # Enable section filtering (only include pages with Part/Chapter headers)

# Optional features / batching
EMBED_BATCH     = int(os.getenv("EMBED_BATCH", "256"))
UPSERT_BATCH    = int(os.getenv("UPSERT_BATCH", "256"))
USE_TIKTOKEN    = os.getenv("USE_TIKTOKEN", "0").strip().lower() in {"1","true"}
# Add query result caching
ENABLE_CACHE    = os.getenv("ENABLE_CACHE", "1").strip().lower() in {"1","true"}
CACHE_SIZE      = int(os.getenv("CACHE_SIZE", "1000"))

# Create directories safely
try: os.makedirs(ARTIFACTS_DIR, exist_ok=True)
except Exception as e: print(f"[WARN] Could not ensure dir {ARTIFACTS_DIR}: {e}")
try: os.makedirs(DATA_DIR, exist_ok=True)
except Exception as e: print(f"[WARN] Could not ensure dir {DATA_DIR}: {e}")

# --- ChromaDB Server Management ------------------------------------------------
# Note: These functions use CHROMADB_PORT which is defined in settings section above
_chromadb_server_process = None
_gcs_synced = False  # Track if we've synced with GCS

def _get_gcs_client():
    """Get GCS storage client with proper credentials.
    
    Returns:
        storage.Client instance configured with service account or default credentials
    """
    if not GCS_AVAILABLE:
        raise Exception("GCS Python client not available. Install google-cloud-storage.")
    
    gcs_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/workspace/gcs-key.json")
    
    try:
        if os.path.exists(gcs_key_path):
            credentials = service_account.Credentials.from_service_account_file(gcs_key_path)
            return storage.Client(credentials=credentials)
        else:
            # Try default credentials (works in Cloud Run, GCE, etc.)
            return storage.Client()
    except Exception as e:
        raise Exception(f"Failed to initialize GCS client: {e}")


def _download_chromadb_from_gcs(bucket_name: str, local_path: str):
    """Download ChromaDB files from GCS to local filesystem.
    
    Args:
        bucket_name: GCS bucket name
        local_path: Local directory path to download files to
    """
    if not GCS_AVAILABLE:
        raise Exception("GCS Python client not available")
    
    print(f"[INFO] Downloading ChromaDB files from GCS bucket: {bucket_name}")
    
    try:
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)
        
        # Check if bucket exists
        if not bucket.exists():
            print(f"[INFO] Bucket {bucket_name} does not exist yet (this is a new database)")
            # Create local directory for new database
            os.makedirs(local_path, exist_ok=True)
            return
        
        # Create local directory
        os.makedirs(local_path, exist_ok=True)
        
        # List all blobs with prefix "chromadb/"
        blobs = list(bucket.list_blobs(prefix="chromadb/"))
        
        # Filter out directory markers (objects that end with "/" and have size 0)
        blobs = [b for b in blobs if not (b.name.endswith("/") and b.size == 0)]
        
        if not blobs:
            print(f"[INFO] No existing ChromaDB files found in bucket (this is a new database)")
            return
        
        downloaded_count = 0
        for blob in blobs:
            try:
                # Remove "chromadb/" prefix if present to get relative path
                if blob.name.startswith("chromadb/"):
                    relative_path = blob.name[len("chromadb/"):]
                else:
                    relative_path = blob.name
                
                # Skip if empty name after removing prefix
                if not relative_path:
                    continue
                
                # Create local file path
                local_file = os.path.join(local_path, relative_path)
                
                # Create parent directories
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                
                # Download file
                blob.download_to_filename(local_file)
                downloaded_count += 1
                
                if downloaded_count % 10 == 0:
                    print(f"[INFO] Downloaded {downloaded_count} files...")
                    
            except Exception as e:
                print(f"[WARN] Failed to download {blob.name}: {e}")
                continue
        
        print(f"[INFO] Successfully downloaded {downloaded_count} files from GCS")
        
        # Touch all downloaded files to ensure proper timestamps
        _touch_chromadb_files(local_path)
        
    except Exception as e:
        print(f"[ERROR] Failed to download ChromaDB files from GCS: {e}")
        import traceback
        traceback.print_exc()
        raise


def _upload_chromadb_to_gcs(bucket_name: str, local_path: str):
    """Upload ChromaDB files from local filesystem to GCS.
    
    Args:
        bucket_name: GCS bucket name
        local_path: Local directory path to upload files from
    """
    if not GCS_AVAILABLE:
        raise Exception("GCS Python client not available")
    
    if not os.path.exists(local_path):
        print(f"[WARN] Local path does not exist: {local_path}")
        return
    
    print(f"[INFO] Uploading ChromaDB files to GCS bucket: {bucket_name}")
    
    try:
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)
        
        # Ensure bucket exists
        if not bucket.exists():
            print(f"[INFO] Creating GCS bucket: {bucket_name}")
            bucket.create(location=GCS_BUCKET_LOCATION)
            print(f"[INFO] Bucket created successfully")
        
        uploaded_count = 0
        total_size = 0
        
        # Walk through local directory and upload all files
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file = os.path.join(root, file)
                
                # Skip if file doesn't exist
                if not os.path.exists(local_file):
                    continue
                
                try:
                    # Get relative path from local_path
                    rel_path = os.path.relpath(local_file, local_path)
                    
                    # Create GCS blob path with "chromadb/" prefix
                    gcs_path = f"chromadb/{rel_path}".replace("\\", "/")  # Normalize path separators
                    
                    # Upload file
                    blob = bucket.blob(gcs_path)
                    blob.upload_from_filename(local_file)
                    
                    uploaded_count += 1
                    file_size = os.path.getsize(local_file)
                    total_size += file_size
                    
                    if uploaded_count % 10 == 0:
                        print(f"[INFO] Uploaded {uploaded_count} files ({total_size / 1024 / 1024:.2f} MB)...")
                        
                except Exception as e:
                    print(f"[WARN] Failed to upload {local_file}: {e}")
                    continue
        
        print(f"[INFO] Successfully uploaded {uploaded_count} files to GCS ({total_size / 1024 / 1024:.2f} MB)")
        
    except Exception as e:
        print(f"[ERROR] Failed to upload ChromaDB files to GCS: {e}")
        import traceback
        traceback.print_exc()
        raise


def _touch_chromadb_files(chroma_path: str):
    """Touch all ChromaDB files to refresh their timestamps.
    
    This ensures ChromaDB can discover and load existing database files.
    
    Args:
        chroma_path: Path to ChromaDB data directory
    """
    if not os.path.exists(chroma_path):
        return
    
    print(f"[INFO] Touching ChromaDB files in {chroma_path}...")
    current_time = time.time()
    touched_count = 0
    
    try:
        # Touch chroma.sqlite3 if it exists
        sqlite_file = os.path.join(chroma_path, "chroma.sqlite3")
        if os.path.exists(sqlite_file):
            try:
                os.utime(sqlite_file, (current_time, current_time))
                touched_count += 1
                file_size = os.path.getsize(sqlite_file)
                print(f"[INFO] ✓ Touched chroma.sqlite3 ({file_size} bytes)")
            except (OSError, PermissionError) as e:
                print(f"[WARN] Failed to touch chroma.sqlite3: {e}")
        
        # Touch all files in collection directories
        if os.path.exists(chroma_path):
            for item in os.listdir(chroma_path):
                item_path = os.path.join(chroma_path, item)
                if os.path.isdir(item_path):
                    collection_file_count = 0
                    for root, dirs, files in os.walk(item_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                if os.path.exists(file_path):
                                    os.utime(file_path, (current_time, current_time))
                                    collection_file_count += 1
                                    touched_count += 1
                            except (OSError, PermissionError):
                                pass
                    if collection_file_count > 0:
                        print(f"[INFO] ✓ Touched {collection_file_count} files in collection: {item}")
        
        print(f"[INFO] Successfully touched {touched_count} files")
        
    except Exception as e:
        print(f"[WARN] Error while touching files: {e}")


def _start_chromadb_server():
    """Start ChromaDB server with GCS Python client sync.
    
    Downloads ChromaDB files from GCS at startup, starts ChromaDB server,
    and will upload files back to GCS on shutdown.
    
    Requires GCS_BUCKET_NAME to be set.
    
    Raises:
        Exception: If GCS_BUCKET_NAME is not set or if sync fails.
    """
    global _chromadb_server_process, _gcs_synced
    
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if not gcs_bucket:
        raise Exception("GCS_BUCKET_NAME must be set. GCS Python client sync is required.")
    
    print(f"[INFO] Starting ChromaDB server with GCS Python client sync...")
    print(f"[INFO] Bucket: {gcs_bucket}")
    
    # Check if ChromaDB server is already running
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', CHROMADB_PORT))
        sock.close()
        if result == 0:
            print("[INFO] ChromaDB server already running")
            return
    except Exception:
        pass
    
    # Create local ChromaDB data directory
    chroma_path = CHROMADB_SERVER_DATA_PATH
    os.makedirs(chroma_path, exist_ok=True)
    
    # Download ChromaDB files from GCS
    if GCS_AVAILABLE and gcs_bucket:
        try:
            _download_chromadb_from_gcs(gcs_bucket, chroma_path)
            _gcs_synced = True
        except Exception as e:
            print(f"[WARN] Failed to download from GCS: {e}")
            print(f"[INFO] Continuing with local directory (may be empty)")
            _gcs_synced = False
    
    # Start ChromaDB server pointing to local path
    # ChromaDB will load existing database from the path if it exists
    print(f"[INFO] Starting ChromaDB server on port {CHROMADB_PORT}...")
    print(f"[INFO] ChromaDB data path: {chroma_path}")
    
    # Set minimal environment variables
    chromadb_env = os.environ.copy()
    chromadb_env["CHROMA_TELEMETRY_DISABLED"] = "1"
    chromadb_env["ANONYMIZED_TELEMETRY"] = "False"
    
    try:
        chromadb_cmd = [
            "chroma", "run",
            "--host", "0.0.0.0",
            "--port", str(CHROMADB_PORT),
            "--path", chroma_path
        ]
        _chromadb_server_process = subprocess.Popen(
            chromadb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            env=chromadb_env,
            text=True,
            bufsize=1
        )
        
        # Log initial server output for debugging
        import threading
        import queue
        output_queue = queue.Queue()
        
        def log_server_output():
            for line in iter(_chromadb_server_process.stdout.readline, ''):
                if line:
                    output_queue.put(('stdout', line.strip()))
                    print(f"[ChromaDB] {line.strip()}")
        
        def check_server_errors():
            """Check if server process has exited with error"""
            # Give server a moment to start
            time.sleep(2)
            if _chromadb_server_process.poll() is not None:
                # Process exited
                return_code = _chromadb_server_process.returncode
                if return_code != 0:
                    print(f"[ERROR] ChromaDB server exited with code {return_code}")
                    # Try to read any remaining output
                    try:
                        remaining = _chromadb_server_process.stdout.read()
                        if remaining:
                            print(f"[ERROR] Server output: {remaining[:500]}")
                    except (IOError, OSError):
                        pass
        
        log_thread = threading.Thread(target=log_server_output, daemon=True)
        log_thread.start()
        
        error_check_thread = threading.Thread(target=check_server_errors, daemon=True)
        error_check_thread.start()
        
        # Wait for server to be ready
        import urllib.request
        time.sleep(3)
        for i in range(90):
            try:
                urllib.request.urlopen(f"http://localhost:{CHROMADB_PORT}/api/v1/heartbeat", timeout=1)
                print("[INFO] ChromaDB server ready")
                
                # Additional wait to ensure server has fully initialized and loaded data
                time.sleep(5)
                
                return
            except Exception:
                time.sleep(1)
    except Exception as e:
        print(f"[ERROR] Failed to start ChromaDB server: {e}")
        print("[ERROR] Make sure ChromaDB is installed")
        raise

def _cleanup_chromadb_server():
    """Cleanup ChromaDB server and upload data to GCS on exit.
    
    Stops ChromaDB server and uploads ChromaDB files to GCS before shutdown.
    """
    global _chromadb_server_process, _gcs_synced
    
    # Stop ChromaDB server first
    if _chromadb_server_process:
        try:
            _chromadb_server_process.terminate()
            _chromadb_server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                _chromadb_server_process.kill()
            except Exception:
                pass
        except Exception:
            try:
                _chromadb_server_process.kill()
            except Exception:
                pass
        finally:
            _chromadb_server_process = None
    
    # Upload ChromaDB files to GCS if we downloaded from GCS or made changes
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if GCS_AVAILABLE and gcs_bucket and _gcs_synced:
        try:
            print("[INFO] Uploading ChromaDB files to GCS before shutdown...")
            _upload_chromadb_to_gcs(gcs_bucket, CHROMADB_SERVER_DATA_PATH)
            print("[INFO] Successfully synced ChromaDB to GCS")
        except Exception as e:
            print(f"[ERROR] Failed to upload ChromaDB to GCS: {e}")
            import traceback
            traceback.print_exc()

# Register cleanup on exit and signals
import atexit
import signal

def _signal_handler(signum, frame):
    """Handle signals for graceful shutdown."""
    print(f"\n[INFO] Received signal {signum}, cleaning up...")
    _cleanup_chromadb_server()
    import sys
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# Register cleanup on exit
atexit.register(_cleanup_chromadb_server)

# --- ChromaDB HTTP Client Factory ----------------------------------------------
def get_chromadb_client():
    """Get ChromaDB HTTP client to connect to remote server.
    
    Returns:
        ChromaDB HttpClient instance
        
    Configuration:
        CHROMADB_HOST: Server hostname (default: localhost)
        CHROMADB_PORT: Server port (default: 8000)
        CHROMADB_AUTH_TOKEN: Optional authentication token
    """
    try:
        if CHROMADB_AUTH_TOKEN:
            # Use authenticated client
            settings = ChromaSettings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=CHROMADB_AUTH_TOKEN
            )
            return HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT, settings=settings)
        else:
            # Use unauthenticated client
            return HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    except Exception as e:
        print(f"[ERROR] Failed to connect to ChromaDB server at {CHROMADB_HOST}:{CHROMADB_PORT}: {e}")
        print(f"[ERROR] Make sure ChromaDB server is running: docker run -d --name chromadb-server -p 8000:8000 chromadb/chroma:latest")
        raise

# --- Silence Chroma telemetry/logs (must be BEFORE importing chromadb) -----
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
for name in ("chromadb","chromadb.telemetry","posthog"):
    logging.getLogger(name).setLevel(logging.ERROR)

from chromadb.config import Settings as ChromaSettings
import numpy as np, chromadb
from chromadb import HttpClient
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

# LangChain removed - using ChromaDB and FastEmbed directly
# Simple document type for semantic chunking
Document = dict
BaseDocumentTransformer = object

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

class SemanticChunker:
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
                doc = {"page_content": chunk, "metadata": metadata}
                documents.append(doc)
                start_index += len(chunk)
        return documents

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

def normalize_query(q: str) -> str:
    """Normalize query text for better caching and consistency.
    
    Args:
        q: Raw query string
        
    Returns:
        Normalized query string (lowercased, stripped, whitespace normalized)
    """
    if not isinstance(q, str):
        return ""
    
    # Strip and lowercase
    q = q.strip().lower()
    
    # Normalize whitespace (multiple spaces to single space)
    q = re.sub(r'\s+', ' ', q)
    
    return q

def _extract_structure(text: str) -> Dict[str, Any]:
    """Extract document structure for better retrieval context."""
    patterns = _EXTRACT_PATTERNS['structure']
    structure = {
        "has_headers": len(patterns['headers'].findall(text)) > 0,
        "has_lists": len(patterns['lists'].findall(text)) > 0,
        "has_code_blocks": len(patterns['code_blocks'].findall(text)) > 0,
        "has_tables": len(patterns['tables'].findall(text)) > 0,
        "paragraph_count": len(patterns['paragraphs'].split(text)),
        "sentence_count": len(patterns['sentences'].findall(text)),
        "word_count": len(text.split()),
    }
    return structure

def _extract_metadata(text: str) -> str:
    """Extract rich metadata from text for better retrieval."""
    metadata_parts = []
    patterns = _EXTRACT_PATTERNS['metadata']
    
    # Extract document title (first capitalized sentence or header)
    title_match = patterns['title'].search(text)
    if title_match:
        metadata_parts.append(f"Title: {title_match.group()}")
    
    # Extract summary indicators
    summary_keywords = patterns['summary_keywords'].findall(text)
    if summary_keywords:
        metadata_parts.append(f"Summary markers: {len(summary_keywords)}")
    
    # Extract key statistics
    numbers = patterns['numbers'].findall(text)
    percentages = patterns['percentages'].findall(text)
    if numbers:
        metadata_parts.append(f"Numbers: {len(numbers)}")
    if percentages:
        metadata_parts.append(f"Percentages: {len(percentages)}")
    
    return "; ".join(metadata_parts) if metadata_parts else ""

def _load_txt_md(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        txt = _norm(f.read())
    return [(path, txt)]

def _has_chapter_or_part(text: str) -> bool:
    """Check if page contains Part or Chapter header.
    
    Args:
        text: Raw text from PDF page
        
    Returns:
        True if page has Part or Chapter header, False otherwise
    """
    # Patterns to match:
    # - "Part I", "Part 1", "Part One"
    # - "Chapter 1", "Chapter 1:", "Chapter 1A"
    # - "1.1", "1.2.3" (numbered sections within chapters)
    
    patterns = [
        r'\bPart\s+[IVX\d]+\b',           # "Part I", "Part 1", "Part IV"
        r'\bPart\s+[Oo]ne\b',             # "Part One"
        r'\bChapter\s+\d+[A-Z]?[:.\s]',  # "Chapter 1:", "Chapter 1 ", "Chapter 1A"
        r'\bChapter\s+\d+[A-Z]?\b',      # "Chapter 1", "Chapter 1A" (standalone)
        r'^\d+\.\d+',                     # "1.1", "1.2.3" (numbered sections at start of line)
    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return True
    
    return False

def _is_non_chapter_section(text: str) -> bool:
    """Check if page is a non-chapter section (back matter, front matter).
    
    Detects sections like Index, Bibliography, Table of Contents, Appendices, etc.
    that should be filtered out.
    
    Args:
        text: Raw text from PDF page
        
    Returns:
        True if page is a non-chapter section, False otherwise
    """
    # Normalize text for pattern matching
    text_lower = text.lower()
    
    # Non-chapter section markers (typically found at start of page or in headers)
    non_chapter_patterns = [
        r'\b(?:table\s+of\s+contents|contents)\b',
        r'\b(?:list\s+of\s+)?(?:figures|tables)\b',
        r'\b(?:references|bibliography|works\s+cited)\b',
        r'\b(?:index|indices)\b',
        r'\b(?:appendix\s+[a-z]|appendices)\b',
        r'\b(?:glossary)\b',
        r'\b(?:preface|foreword|acknowledgements?)\b',
        r'\b(?:about\s+the\s+author|contributors)\b',
    ]
    
    # Check if any pattern matches (especially at start of text or on its own line)
    for pattern in non_chapter_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            # Additional check: if it's a strong match (appears near start or as header)
            # This helps avoid false positives when these terms appear in chapter content
            lines = text_lower.split('\n')[:5]  # Check first 5 lines
            for line in lines:
                if re.search(pattern, line, re.IGNORECASE):
                    # If the line is relatively short (< 100 chars), it's likely a section header
                    if len(line.strip()) < 100:
                        return True
    
    return False

def _extract_chapter_section_info(text: str) -> Dict[str, str]:
    """Extract chapter/section information from text before header removal.
    
    Args:
        text: Raw text from PDF page
        
    Returns:
        Dictionary with chapter/section information if found
    """
    info = {}
    
    # Look for chapter patterns (e.g., "Chapter 1: Introduction" or "Chapter 1 Introduction")
    chapter_patterns = [
        r'^Chapter\s+(\d+[A-Z]?)[:.\s]+(.+?)(?:\n|$)',  # "Chapter 1: Title"
        r'^Chapter\s+(\d+[A-Z]?)\s+(.+?)(?:\n|$)',      # "Chapter 1 Title"
    ]
    
    for pattern in chapter_patterns:
        chapter_match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if chapter_match:
            info['chapter_number'] = chapter_match.group(1)
            info['chapter_title'] = chapter_match.group(2).strip()
            # Only keep first 100 chars of title to avoid noise
            if len(info['chapter_title']) > 100:
                info['chapter_title'] = info['chapter_title'][:100] + "..."
            break
    
    # Look for section patterns (e.g., "1.1 Introduction" or "1.1: Introduction")
    section_patterns = [
        r'^(\d+\.\d+(?:\.\d+)?)[:.\s]+(.+?)(?:\n|$)',  # "1.1: Title" or "1.1.1 Title"
        r'^(\d+\.\d+(?:\.\d+)?)\s+(.+?)(?:\n|$)',      # "1.1 Title"
    ]
    
    for pattern in section_patterns:
        section_match = re.search(pattern, text, re.MULTILINE)
        if section_match:
            info['section_number'] = section_match.group(1)
            info['section_title'] = section_match.group(2).strip()
            # Only keep first 100 chars of title to avoid noise
            if len(info['section_title']) > 100:
                info['section_title'] = info['section_title'][:100] + "..."
            break
    
    return info

def _remove_headers_footers(text: str, page_num: int = None) -> str:
    """Remove repeating headers, footers, and page numbers from textbook pages.
    
    Args:
        text: Raw text from PDF page
        page_num: Current page number (optional, for removing page numbers)
        
    Returns:
        Text with headers/footers removed
    """
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned = []
    
    # Common header/footer patterns
    header_footer_patterns = [
        r'^Chapter\s+\d+',  # "Chapter 1"
        r'^\d+\.\d+\s+[A-Z]',  # "1.1 Section Title" (at start of line)
        r'^Page\s+\d+',  # "Page 5"
        r'^\d+$',  # Standalone page numbers
        r'^[A-Z][a-z]+\s+\d+$',  # "Chapter 5" (short lines)
    ]
    
    # Track lines we've seen (for detecting repeating headers/footers)
    seen_lines = {}
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip empty lines
        if not line_stripped:
            cleaned.append(line)
            continue
        
        # Skip if it's just a page number
        if page_num and line_stripped == str(page_num):
            continue
        
        # Check if line matches header/footer patterns
        is_header_footer = False
        for pattern in header_footer_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                # Only skip if it's a short line (likely header/footer, not content)
                if len(line_stripped) < 60:
                    is_header_footer = True
                    break
        
        # Detect repeating lines (likely headers/footers)
        if not is_header_footer and len(line_stripped) < 80:
            line_lower = line_stripped.lower()
            if line_lower in seen_lines:
                seen_lines[line_lower] += 1
                # If we've seen this line many times, it's likely a header/footer
                if seen_lines[line_lower] > 3:
                    is_header_footer = True
            else:
                seen_lines[line_lower] = 1
        
        if not is_header_footer:
            cleaned.append(line)
    
    return '\n'.join(cleaned)

def _extract_page_text(page, page_num: int, base: str) -> str:
    """Extract text from a PDF page using layout-aware extraction.
    
    Args:
        page: PyMuPDF page object
        page_num: Page number (for error messages)
        base: Document base name (for error messages)
        
    Returns:
        Extracted text, or None if extraction fails
    """
    try:
        # Get text blocks with position info for better layout handling
        blocks = page.get_text("dict")["blocks"]
        text_parts = []
        
        for block in blocks:
            if "lines" in block:  # Text block (not image)
                block_text = ""
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"] + " "
                    # Add newline after each line in block
                    if line_text.strip():
                        block_text += line_text.strip() + "\n"
                if block_text.strip():
                    text_parts.append(block_text.strip())
        
        if text_parts:
            # Join blocks with paragraph breaks
            return "\n\n".join(text_parts)
    except Exception:
        try:
            return page.get_text("text")
        except Exception:
            return None
    
    return None

def _load_pdf(path: str) -> List[Tuple[str, str]]:
    """Enhanced PDF loading with layout-aware extraction, header/footer removal, and chapter-aware filtering.
    
    Uses a two-pass approach:
    1. First pass: Identify chapter boundaries and non-chapter sections
    2. Second pass: Include all pages from first chapter through last chapter,
       excluding non-chapter sections (Index, Bibliography, TOC, etc.)
    
    This ensures all pages within chapters are included, not just pages with chapter headers.
    """
    items: List[Tuple[str, str]] = []
    filtered_count = 0
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return items
    
    doc = fitz.open(path)
    base = os.path.basename(path)
    
    # Extract PDF metadata
    pdf_metadata = doc.metadata if hasattr(doc, 'metadata') else {}
    total_pages = len(doc)
    
    if not ENABLE_SECTION_FILTER:
        # No filtering - process all pages
        for i, page in enumerate(doc, start=1):
            txt = _extract_page_text(page, i, base)
            if not txt or not txt.strip():
                continue
            
            # Extract chapter/section info BEFORE removing headers
            chapter_section_info = _extract_chapter_section_info(txt)
            
            # Remove headers, footers, and page numbers
            txt = _remove_headers_footers(txt, page_num=i)
            
            if not txt or not txt.strip():
                continue
            
            # Normalize text
            txt = _norm(txt)
            
            # Add page context metadata
            page_info = f"[Document: {base}] [Page {i} of {total_pages}] "
            if pdf_metadata.get('title'):
                page_info += f"[Title: {pdf_metadata.get('title')}] "
            
            if chapter_section_info.get('chapter_number'):
                chapter_str = f"Chapter {chapter_section_info['chapter_number']}"
                if chapter_section_info.get('chapter_title'):
                    chapter_str += f": {chapter_section_info['chapter_title']}"
                page_info += f"[{chapter_str}] "
            
            if chapter_section_info.get('section_number'):
                section_str = f"Section {chapter_section_info['section_number']}"
                if chapter_section_info.get('section_title'):
                    section_str += f": {chapter_section_info['section_title']}"
                page_info += f"[{section_str}] "
            
            txt = page_info + txt
            items.append((f"{path}#page={i}", txt))
    else:
        # Two-pass approach for chapter-aware filtering
        # Pass 1: Identify chapter boundaries and non-chapter sections
        page_texts = {}  # page_num -> extracted text
        page_states = {}  # page_num -> "chapter", "non_chapter", or "unknown"
        first_chapter_page = None
        last_chapter_page = None
        pages_with_text = 0
        
        for i, page in enumerate(doc, start=1):
            txt = _extract_page_text(page, i, base)
            if not txt or not txt.strip():
                continue
            
            pages_with_text += 1
            page_texts[i] = txt
            
            # Check for chapter markers
            has_chapter = _has_chapter_or_part(txt)
            # Check for non-chapter markers (Index, Bibliography, etc.)
            is_non_chapter = _is_non_chapter_section(txt)
            
            if has_chapter:
                page_states[i] = "chapter"
                if first_chapter_page is None:
                    first_chapter_page = i
                last_chapter_page = i
            elif is_non_chapter:
                page_states[i] = "non_chapter"
            else:
                page_states[i] = "unknown"
        
        if first_chapter_page is None:
            first_chapter_page = 1
            last_chapter_page = total_pages
        
        # Pass 2: Process pages based on state
        # Include all pages from first_chapter_page to last_chapter_page,
        # excluding non-chapter sections
        for i, page in enumerate(doc, start=1):
            txt = page_texts.get(i)
            if not txt or not txt.strip():
                continue
            
            state = page_states.get(i, "unknown")
            
            # Include page if:
            # 1. Page is within chapter range (first_chapter_page to last_chapter_page)
            # 2. AND it's not a non-chapter section (Index, Bibliography, etc.)
            should_include = (
                i >= first_chapter_page and
                i <= last_chapter_page and
                state != "non_chapter"
            )
            
            if not should_include:
                filtered_count += 1
                continue
            
            # Extract chapter/section info BEFORE removing headers
            chapter_section_info = _extract_chapter_section_info(txt)
            
            # Remove headers, footers, and page numbers
            txt = _remove_headers_footers(txt, page_num=i)
            
            if not txt or not txt.strip():
                filtered_count += 1
                continue
            
            # Normalize text
            txt = _norm(txt)
            
            # Add page context metadata
            page_info = f"[Document: {base}] [Page {i} of {total_pages}] "
            if pdf_metadata.get('title'):
                page_info += f"[Title: {pdf_metadata.get('title')}] "
            
            if chapter_section_info.get('chapter_number'):
                chapter_str = f"Chapter {chapter_section_info['chapter_number']}"
                if chapter_section_info.get('chapter_title'):
                    chapter_str += f": {chapter_section_info['chapter_title']}"
                page_info += f"[{chapter_str}] "
            
            if chapter_section_info.get('section_number'):
                section_str = f"Section {chapter_section_info['section_number']}"
                if chapter_section_info.get('section_title'):
                    section_str += f": {chapter_section_info['section_title']}"
                page_info += f"[{section_str}] "
            
            txt = page_info + txt
            items.append((f"{path}#page={i}", txt))
        
        if filtered_count > 0:
            print(f"[INFO] Filtered {filtered_count} pages from {base} (pages {first_chapter_page}-{last_chapter_page} included)")
    
    doc.close()
    return items

def _load_csv(path: str) -> List[Tuple[str, str]]:
    """Load Output_explanation.csv with special handling for feature explanations.
    
    Creates structured knowledge base format for queryable feature definitions.
    Each feature becomes a self-contained chunk (no semantic splitting needed).
    
    Args:
        path: Path to CSV file
        
    Returns:
        List of (source_path, text_content) tuples
    """
    items: List[Tuple[str, str]] = []
    base = os.path.basename(path)
    
    # Only process Output_explanation.csv files
    if "Output_explanation" not in base and "output_explanation" not in base.lower():
        return items
    
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            # utf-8-sig automatically strips BOM if present
            reader = csv.DictReader(f)
            rows = list(reader)
            
        if not rows:
            return items
        
        # Process each feature definition
        for row in rows:
            # Handle BOM in column name (utf-8-sig should fix this, but be defensive)
            feature = row.get("Feature", "").strip() or row.get("\ufeffFeature", "").strip()
            if not feature:
                continue
            
            # Build structured feature definition
            parts = []
            parts.append(f"Feature: {feature}")
            
            full_name = row.get("Full_Name_or_Formula", "").strip()
            if full_name:
                parts.append(f"Full Name or Formula: {full_name}")
            
            meaning = row.get("Meaning", "").strip()
            if meaning:
                parts.append(f"Meaning: {meaning}")
            
            interpretation = row.get("Interpretation_or_Signal", "").strip()
            if interpretation:
                parts.append(f"Interpretation or Signal: {interpretation}")
                # Extract thresholds (e.g., ">15%", "<30", ">2")
                thresholds = re.findall(r'([<>]=?)\s*(\d+(?:\.\d+)?)', interpretation)
                if thresholds:
                    threshold_text = ", ".join([f"{op} {val}" for op, val in thresholds])
                    parts.append(f"Thresholds: {threshold_text}")
            
            use_case = row.get("Use_Case", "").strip()
            if use_case:
                parts.append(f"Use Case: {use_case}")
            
            # Create well-formatted chunk (already complete, no splitting needed)
            text = "\n".join(parts)
            text = _norm(text)
            items.append((f"{path}#feature={feature}", text))
    
    except Exception:
        pass
    
    return items

def load_all(data_dir: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    # Early filter: only process supported extensions
    ext_patterns = {".txt", ".md", ".pdf", ".csv"}
    for p in sorted(glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)):
        if not os.path.isfile(p): continue
        ext = os.path.splitext(p)[1].lower()
        if ext not in ext_patterns: continue
        try:
            if ext in (".txt",".md"): out.extend(_load_txt_md(p))
            elif ext == ".pdf": out.extend(_load_pdf(p))
            elif ext == ".csv":
                # Only process Output_explanation.csv files
                base = os.path.basename(p)
                if "Output_explanation" in base or "output_explanation" in base.lower():
                    csv_items = _load_csv(p)
                    if csv_items:
                        print(f"[INFO] Loaded {len(csv_items)} features from {base}")
                    out.extend(csv_items)
                # Skip other CSV files silently
        except Exception:
            pass
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
def get_embedder() -> TextEmbedding:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _EMBEDDER

def semantic_embed(texts, **kwargs):
    model = get_embedder()
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
            embedding_function=semantic_embed,
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
            parts.append(d["page_content"])
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

# Cache compiled regex patterns for metadata extraction (performance optimization)
_EXTRACT_PATTERNS = {
    'key_phrases': {
        'capitalized': re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'),
        'numbers': re.compile(r'\d+(?:\.\d+)?%?|%'),
        'important_def': re.compile(r'(?:definition|example|result|conclusion):\s+(\w+(?:\s+\w+){0,2})', re.IGNORECASE),
        'important_key': re.compile(r'(?:important|key|main|primary):\s+(\w+(?:\s+\w+){0,2})', re.IGNORECASE),
    },
    'chunk_type': {
        'questions': re.compile(r'\?'),
        'lists': re.compile(r'^[\s]*[-•*]\s', re.MULTILINE),
        'numbers': re.compile(r'\d+'),
        'code': re.compile(r'[{}();=<>]'),
        'definitions': re.compile(r'\b(is|are|means?|defined as|refers to)\b', re.IGNORECASE),
        'numbers_detailed': re.compile(r'\d+\.?\d*'),
    },
    'structure': {
        'headers': re.compile(r'^#+\s+', re.MULTILINE),
        'lists': re.compile(r'^[\s]*[-•*]\s', re.MULTILINE),
        'code_blocks': re.compile(r'```'),
        'tables': re.compile(r'\|.*\|'),
        'paragraphs': re.compile(r'\n\s*\n'),
        'sentences': re.compile(r'[.!?]+'),
    },
    'metadata': {
        'title': re.compile(r'^(#{1,3}\s+[A-Z][^\n]+|^[A-Z][^.!?]{10,100}[.!?])', re.MULTILINE),
        'summary_keywords': re.compile(r'\b(summary|overview|conclusion|key points?|takeaway|insight)\b', re.IGNORECASE),
        'numbers': re.compile(r'\d+(?:\.\d+)?'),
        'percentages': re.compile(r'\d+(?:\.\d+)?%'),
    },
}

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
    patterns = _EXTRACT_PATTERNS['key_phrases']
    
    # Extract capitalized phrases (likely proper nouns, titles)
    cap_matches = patterns['capitalized'].findall(text)
    phrases.extend(cap_matches[:3])
    
    # Extract numbers and units (important for technical content)
    num_matches = patterns['numbers'].findall(text)
    phrases.extend(num_matches[:2])
    
    # Extract words following important keywords
    def_matches = patterns['important_def'].findall(text)
    phrases.extend(def_matches[:2])
    key_matches = patterns['important_key'].findall(text)
    phrases.extend(key_matches[:2])
    
    # Deduplicate and return
    return list(dict.fromkeys(phrases))[:max_phrases]  # Preserves order

def _classify_chunk_type(text: str) -> str:
    """Classify chunk type for better retrieval and filtering."""
    # Count patterns using cached regex
    patterns = _EXTRACT_PATTERNS['chunk_type']
    has_questions = bool(patterns['questions'].search(text))
    has_lists = len(patterns['lists'].findall(text)) > 0
    has_numbers = bool(patterns['numbers'].search(text))
    has_code = bool(patterns['code'].search(text))
    has_definitions = bool(patterns['definitions'].search(text))
    
    if has_code:
        return "code"
    elif has_lists:
        return "list"
    elif has_definitions:
        return "definition"
    elif has_questions:
        return "question"
    elif has_numbers and len(patterns['numbers_detailed'].findall(text)) > 3:
        return "data"
    else:
        return "paragraph"

# --- Ingest: load → chunk → embed → Chroma ----------------------------------
def run_ingest(*, target_tokens: int = 900, max_tokens: int = 1400,
               overlap_sentences: int = 2, buffer_size: int = 1,
               sim_percentile: float = 95.0, max_depth: int = 3) -> Dict[str, Any]:
    """Ingest documents into ChromaDB with semantic chunking.
    
    Main ingestion function that loads documents, chunks them semantically,
    creates embeddings, and stores them in ChromaDB. Data is synced to GCS
    using Python client after ingestion (requires GCS_BUCKET_NAME to be set). Uses upsert to avoid duplicates.
    
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
        1. Loads documents from DATA_DIR
        2. Semantic chunking with metadata enrichment
        3. Creates embeddings in batches
        4. Upserts to ChromaDB server via HTTP (updates or adds chunks)
        5. Backs up server data to GCS (if enabled)
    """
    t0 = time.time()
    
    # Note: Using HTTP client mode - data is persisted on ChromaDB server, no download needed
    
    docs = load_all(DATA_DIR)
    total_docs = len(docs)

    client = get_chromadb_client()
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    embedder = get_embedder()

    ids_buf: List[str] = []; docs_buf: List[str] = []; metas_buf: List[Dict[str, Any]] = []
    added = 0; token_lens: List[int] = []
    skipped_embeddings = 0  # Track how many embeddings we skipped

    def _flush():
        nonlocal added, ids_buf, docs_buf, metas_buf, skipped_embeddings
        if not ids_buf: return
        
        # Check which chunks already exist and compare content hashes
        existing_chunks = {}
        try:
            # Batch get existing chunks - only load metadatas and embeddings (not documents)
            # We don't need documents since we only compare content_hash and reuse embeddings
            existing = coll.get(ids=ids_buf, include=["metadatas", "embeddings"])
            # Map results by ID since ChromaDB may return in different order
            for i, chunk_id in enumerate(existing.get("ids", [])):
                existing_chunks[chunk_id] = {
                    "content_hash": existing["metadatas"][i].get("content_hash") if existing.get("metadatas") and i < len(existing["metadatas"]) else None,
                    "embedding": existing["embeddings"][i] if existing.get("embeddings") and i < len(existing["embeddings"]) else None,
                }
        except Exception as e:
            # If get fails, assume all chunks are new
            existing_chunks = {}
        
        # Separate chunks into: need_embedding vs skip_embedding
        need_embedding_ids = []
        need_embedding_docs = []
        need_embedding_indices = []
        skip_embedding_indices = []
        
        for i, chunk_id in enumerate(ids_buf):
            current_hash = metas_buf[i].get("content_hash")
            existing_info = existing_chunks.get(chunk_id)
            
            if existing_info and existing_info["content_hash"] == current_hash:
                # Chunk exists and content unchanged - skip embedding computation
                skip_embedding_indices.append(i)
            else:
                # Chunk is new or content changed - need to compute embedding
                need_embedding_ids.append(chunk_id)
                need_embedding_docs.append(docs_buf[i])
                need_embedding_indices.append(i)
        
        # Compute embeddings only for chunks that need it
        if need_embedding_docs:
            new_embs = [ (e.tolist() if hasattr(e, "tolist") else e)
                        for e in embedder.passage_embed(need_embedding_docs, batch_size=EMBED_BATCH) ]
        else:
            new_embs = []
        
        # Build complete embeddings list (new + existing)
        all_embs = [None] * len(ids_buf)
        for i, idx in enumerate(need_embedding_indices):
            all_embs[idx] = new_embs[i]
        for i in skip_embedding_indices:
            chunk_id = ids_buf[i]
            existing_info = existing_chunks.get(chunk_id)
            if existing_info and existing_info["embedding"]:
                all_embs[i] = existing_info["embedding"]
            else:
                try:
                    fallback_emb = next(embedder.passage_embed([docs_buf[i]], batch_size=1))
                    all_embs[i] = fallback_emb.tolist() if hasattr(fallback_emb, "tolist") else list(fallback_emb)
                except Exception:
                    all_embs[i] = [0.0] * 384
        
        skipped_embeddings += len(skip_embedding_indices)
        
        try:
            coll.upsert(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=all_embs)
        except Exception:
            try:
                coll.add(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=all_embs)
            except Exception:
                ids_buf.clear(); docs_buf.clear(); metas_buf.clear()
                return
        
        added += len(ids_buf)
        ids_buf.clear(); docs_buf.clear(); metas_buf.clear()
    
    # Check existing chunk count
    existing_count = coll.count()
    if existing_count > 0:
        print(f"[INFO] Found {existing_count} existing chunks in collection")

    # Batch check document sources if SKIP_EXISTING is enabled
    processed_sources = set()
    if SKIP_EXISTING and existing_count > 0 and len(docs) > 0:
        try:
            # Collect all first chunk IDs for batch checking
            # Since chunk IDs are deterministic (f"{src}::chunk_{idx}"), we check if
            # the first chunk ID for each source exists
            first_chunk_ids = [f"{src}::chunk_0" for src, _ in docs]
            print(f"[INFO] Batch checking {len(first_chunk_ids)} document sources...")
            
            # Single batch query to check all documents at once
            existing_chunks = coll.get(ids=first_chunk_ids, include=["metadatas"])
            
            # Map results back to sources
            # ChromaDB may return results in different order, so map by chunk_id
            if existing_chunks.get("ids") and existing_chunks.get("metadatas"):
                for i, chunk_id in enumerate(existing_chunks["ids"]):
                    if i < len(existing_chunks["metadatas"]):
                        meta = existing_chunks["metadatas"][i]
                        if isinstance(meta, dict) and "source" in meta:
                            # Verify chunk_id matches expected pattern to avoid false positives
                            expected_source = chunk_id.rsplit("::chunk_0", 1)[0]
                            if meta["source"] == expected_source:
                                processed_sources.add(meta["source"])
            
        except Exception:
            processed_sources = None
    
    # Process documents with progress indication
    for doc_idx, (src, txt) in enumerate(docs, 1):
        if doc_idx % 10 == 0 or doc_idx == total_docs:
            print(f"Processing document {doc_idx}/{total_docs} ({src})")
        
        # Skip already processed sources if enabled
        if SKIP_EXISTING and existing_count > 0:
            if processed_sources is not None:
                # Use batch-checked results (fast set lookup)
                if src in processed_sources:
                    print(f"[SKIP] {src} already processed, skipping...")
                    continue
            else:
                # Fallback: individual check if batch failed
                try:
                    first_chunk_id = f"{src}::chunk_0"
                    existing_chunks = coll.get(ids=[first_chunk_id], include=["metadatas"])
                    if existing_chunks.get("ids") and len(existing_chunks["ids"]) > 0:
                        if existing_chunks.get("metadatas") and len(existing_chunks["metadatas"]) > 0:
                            existing_meta = existing_chunks["metadatas"][0]
                            if isinstance(existing_meta, dict) and existing_meta.get("source") == src:
                                print(f"[SKIP] {src} already processed, skipping...")
                                continue
                except Exception:
                    pass
        
        # Check if this is a CSV file (already chunked, skip semantic chunking)
        is_csv_chunk = src.endswith(".csv") or "#feature=" in src or "#stats" in src
        
        if is_csv_chunk:
            # CSV chunks are already complete - use as-is (no semantic chunking)
            chs = [txt]  # Single chunk, already formatted
            # Skip context enrichment for CSV (not needed for structured data)
        else:
            # Regular documents: apply semantic chunking
            chs = semantic_chunks(
                txt, sim_percentile=sim_percentile, buffer_size=buffer_size,
                max_tokens=max_tokens, overlap_sentences=overlap_sentences, max_depth=max_depth
            )
            # Enhanced chunking: add contextual information (with memory limit)
            max_window = min(2, len(chs)//2) if len(chs) > 4 else 1  # Limit context window for memory
            chs = _enrich_chunk_with_context(chs, window_size=max_window)
        
        # Process chunks in batches - minimal metadata for performance
        for idx, ch in enumerate(chs):
            cid = f"{src}::chunk_{idx}"
            
            # Compute content hash for duplicate detection
            content_hash = hashlib.md5(ch.encode('utf-8')).hexdigest()
            
            # Minimal metadata: only essential fields for retrieval and duplicate detection
            meta = {
                "source": src,  # Required for source attribution
                "content_hash": content_hash,  # Required for duplicate detection
                "chunk_index": idx,  # Useful for ordering within document
                "total_chunks": len(chs),  # Useful context
            }
            ids_buf.append(cid); docs_buf.append(ch); metas_buf.append(meta)
            token_lens.append(_approx_token_len(ch))
            if len(ids_buf) >= UPSERT_BATCH: _flush()
        
        # Clear intermediate variables to free memory
        del chs, txt
        
        # Adaptive garbage collection: run more frequently if buffer is large or every 20 documents
        # This helps manage memory better without excessive GC overhead
        if len(ids_buf) > UPSERT_BATCH * 2 or doc_idx % 20 == 0:
            gc.collect()
    
    _flush()
    
    # Upload ChromaDB files to GCS after ingestion
    global _gcs_synced
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if GCS_AVAILABLE and gcs_bucket:
        try:
            print("[INFO] Uploading ChromaDB files to GCS after ingestion...")
            _upload_chromadb_to_gcs(gcs_bucket, CHROMADB_SERVER_DATA_PATH)
            print("[INFO] Successfully uploaded ChromaDB to GCS")
            _gcs_synced = True
        except Exception as e:
            print(f"[ERROR] Failed to upload ChromaDB to GCS: {e}")
            import traceback
            traceback.print_exc()
            raise Exception("Failed to persist ChromaDB to GCS. Data may be lost.")
    else:
        if not gcs_bucket:
            print("[WARN] GCS_BUCKET_NAME not set - ChromaDB data will not be persisted to GCS")
        elif not GCS_AVAILABLE:
            print("[WARN] GCS Python client not available - ChromaDB data will not be persisted to GCS")

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

    print(f"Indexed {added} chunks into collection '{VECTOR_COLLECTION}'")
    return {"added": added, "skipped_embeddings": skipped_embeddings, **summary}

# --- Add LRU cache for embeddings to avoid re-computation ---
from functools import lru_cache
import hashlib
_embedding_cache = {}

def cached_embed(text: str) -> List[float]:
    """Cached embedding function for repeated queries."""
    if text in _embedding_cache:
        return _embedding_cache[text]
    model = get_embedder()
    result = list(next(model.query_embed(text)))
    if len(_embedding_cache) < CACHE_SIZE:
        _embedding_cache[text] = result
    return result

# LangChain removed - using FastEmbed directly

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
        # Using HTTP client - data is on ChromaDB server, no download needed
        self.client = get_chromadb_client()
        self.collection = self.client.get_or_create_collection(name=VECTOR_COLLECTION)
        # Using FastEmbed directly (LangChain removed)
        self.mode = "chroma-dist"
        # Add query cache
        self._query_cache = {} if ENABLE_CACHE else None

    def stats(self):
        cnt = self.collection.count()
        meta = getattr(self.collection, "metadata", {}) or {}
        return {"collection": VECTOR_COLLECTION, "emb_model": EMBEDDING_MODEL, "retriever_mode": self.mode,
                "metric": meta.get("hnsw:space","cosine"), "count": cnt, "cache_enabled": ENABLE_CACHE}

    def query(self, q: str, k: int = 4):
        if not isinstance(q, str) or not q.strip(): return []
        
        # Normalize query for better cache hits
        q_normalized = normalize_query(q)
        if not q_normalized:
            return []
        
        # Check cache if enabled (use normalized query)
        cache_key = f"{q_normalized}_{k}"
        if self._query_cache is not None and cache_key in self._query_cache:
            return self._query_cache[cache_key]
        
        k = max(1, min(int(k), 50))
        # Use FastEmbed directly for query embedding (use normalized query)
        if ENABLE_CACHE:
            try:
                q_vec = cached_embed(q_normalized)
            except Exception:
                embedder = get_embedder()
                q_vec = next(embedder.query_embed(q_normalized))
        else:
            embedder = get_embedder()
            q_vec = next(embedder.query_embed(q_normalized))
        
        # Ensure q_vec is a flat list of floats (not nested)
        # Convert numpy array to list if needed
        if hasattr(q_vec, "tolist"):
            q_vec = q_vec.tolist()
        elif not isinstance(q_vec, list):
            q_vec = list(q_vec)
        
        # Check if q_vec is nested and flatten if needed
        if isinstance(q_vec, list) and len(q_vec) > 0:
            if isinstance(q_vec[0], list):
                # If it's nested, flatten it
                q_vec = q_vec[0] if len(q_vec) == 1 else [item for sublist in q_vec for item in sublist]
        
        # Final check: ensure q_vec is a flat list of numbers
        if isinstance(q_vec, list) and len(q_vec) > 0:
            if not isinstance(q_vec[0], (int, float)) and isinstance(q_vec[0], (list, np.ndarray)):
                q_vec = q_vec[0]
                if hasattr(q_vec, "tolist"):
                    q_vec = q_vec.tolist()
        
        # Convert to numpy array for ChromaDB (it handles numpy arrays better)
        # ChromaDB expects query_embeddings to be a list of embeddings (one per query)
        # Each embedding should be a list of floats or a numpy array
        if isinstance(q_vec, list):
            q_vec = np.array(q_vec, dtype=np.float32)
        
        # Pass as list containing the numpy array (one query, one embedding)
        res = self.collection.query(query_embeddings=[q_vec], n_results=k, include=["documents","metadatas","distances"])
        # Handle empty results gracefully - ChromaDB returns empty lists when no results
        ids_list = res.get("ids", [[]])
        docs_list = res.get("documents", [[]])
        metas_list = res.get("metadatas", [[]])
        dists_list = res.get("distances", [[]])
        
        # Extract first (and only) result list, or use empty list if no results
        ids = ids_list[0] if isinstance(ids_list, list) and len(ids_list) > 0 else []
        docs = docs_list[0] if isinstance(docs_list, list) and len(docs_list) > 0 else []
        metas = metas_list[0] if isinstance(metas_list, list) and len(metas_list) > 0 else []
        dists = dists_list[0] if isinstance(dists_list, list) and len(dists_list) > 0 else []
        
        out = []
        for i, (doc_id, text, md, dist) in enumerate(zip(ids, docs, metas, dists), start=1):
            # Safely convert distance to float (handle None or invalid values)
            try:
                distance = float(dist) if dist is not None else 0.0
            except (ValueError, TypeError):
                distance = 0.0
            out.append({"rank": i, "id": doc_id, "text": text, "metadata": md if isinstance(md, dict) else {}, "distance": distance})
        
        # Cache result
        if self._query_cache is not None and len(self._query_cache) < CACHE_SIZE:
            self._query_cache[cache_key] = out
        
        return out

# --- FastAPI server ---------------------------------------------------------
def make_app():
    """Create and configure FastAPI application.
    
    Returns:
        FastAPI app instance with:
        - /health endpoint: Enhanced health check with collection stats
        - /query endpoint: Semantic search query interface with full metadata
        - /query/text endpoint: Simplified query interface for orchestrator/tool integration
        
    The app initializes a Retriever instance on startup for handling queries.
    Includes CORS middleware for cross-origin requests (orchestrator integration).
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    
    app = FastAPI(title="AC215 MS3 RAG API (Semantic + LangChain)")
    
    # Add CORS middleware for orchestrator integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Restrict in production to specific origins
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    
    retr = Retriever()
    
    class QueryReq(BaseModel):
        q: str
        k: int = 4
    
    class QueryTextReq(BaseModel):
        q: str
        k: int = 3
        format: str = "text"  # "text" or "detailed"
    
    @app.get("/health")
    def health():
        """Enhanced health check endpoint for orchestrator monitoring.
        
        Returns:
            JSON with status, service info, and ChromaDB connectivity status.
        """
        try:
            stats = retr.stats()
            return {
                "status": "ok",
                "service": "rag-api",
                "chromadb": "connected",
                **stats
            }
        except Exception as e:
            return {
                "status": "degraded",
                "service": "rag-api",
                "chromadb": "error",
                "error": str(e)
            }
    
    @app.post("/query")
    def query(req: QueryReq):
        """Main query endpoint with full metadata.
        
        Args:
            req: Query request with query string and result count
            
        Returns:
            JSON with query, results (full metadata), and result count
        """
        try:
            results = retr.query(req.q, req.k)
            return {
                "query": req.q,
                "results": results,
                "found": len(results) > 0,
                "count": len(results)
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": str(e),
                    "query": req.q
                }
            )
    
    @app.post("/query/text")
    def query_text(req: QueryTextReq):
        """Simplified query endpoint for orchestrator/tool integration.
        
        Returns clean text suitable for LLM consumption. This endpoint is designed
        for integration with conversational agents and LLM tools.
        
        Args:
            req: Query request with query string, result count, and format preference
            
        Returns:
            JSON with:
            - query: The original query
            - answer: Concatenated text from top results (for "text" format) or full results (for "detailed")
            - found: Boolean indicating if results were found
            - source_count: Number of sources retrieved
        """
        try:
            results = retr.query(req.q, req.k)
            
            if not results:
                return {
                    "query": req.q,
                    "answer": "No relevant information found in the knowledge base.",
                    "found": False,
                    "source_count": 0
                }
            
            if req.format == "text":
                # Concatenate top results for LLM consumption (limit each to 500 chars for brevity)
                texts = [r.get("text", "") for r in results[:3]]  # Top 3 results
                answer = "\n\n".join([
                    f"Information {i+1}: {text[:500]}"  # Limit each to 500 chars
                    for i, text in enumerate(texts) if text
                ])
                
                return {
                    "query": req.q,
                    "answer": answer,
                    "found": True,
                    "source_count": len(results)
                }
            else:
                # Detailed format - return full results
                return {
                    "query": req.q,
                    "results": results,
                    "found": True,
                    "count": len(results)
                }
                
        except Exception as e:
            return {
                "query": req.q,
                "answer": f"Error accessing knowledge base: {str(e)}",
                "found": False,
                "error": str(e)
            }
    
    return app

def serve():
    """Start the FastAPI server with uvicorn.
    
    Starts a production-ready ASGI server on configured API_HOST and API_PORT.
    """
    import uvicorn
    app = make_app()
    uvicorn.run(app, host=API_HOST, port=API_PORT, reload=False)

# --- CLI -------------------------------------------------------------------
def main():
    """Command-line interface entry point for RAG application.
    
    Parses command-line arguments and executes requested operations:
    - --ingest: Run document ingestion with semantic chunking
    - --serve: Start FastAPI server
    - Semantic chunking parameters (--target-tokens, --max-tokens, etc.)
    
    Environment variables from .env are loaded automatically.
    
    Requires GCS_BUCKET_NAME to be set. Automatically starts ChromaDB server with GCS Python client sync.
    GCS Python client sync is required - downloads from GCS at startup, uploads on shutdown.
    """
    # Start ChromaDB server with GCS Python client sync (required if GCS_BUCKET_NAME is set)
    # Only auto-start if GCS_BUCKET_NAME is set and AUTO_START_CHROMADB is not disabled
    if os.getenv("GCS_BUCKET_NAME") and os.getenv("AUTO_START_CHROMADB", "1") != "0":
        try:
            _start_chromadb_server()
        except Exception as e:
            print(f"[ERROR] Failed to start ChromaDB server with GCS sync: {e}")
            print("[ERROR] GCS Python client sync is required. Cannot continue without it.")
            raise
    
    p = argparse.ArgumentParser(description="AC215-MS3 RAG CLI (Semantic + optional LangChain)")
    p.add_argument("--ingest", action="store_true", help="Run ingestion")
    p.add_argument("--serve",  action="store_true", help="Run FastAPI server")
    p.add_argument("--target-tokens", type=int, default=900)
    p.add_argument("--max-tokens", type=int, default=1400)
    p.add_argument("--overlap-sentences", type=int, default=2)
    p.add_argument("--buffer-size", type=int, default=1)
    p.add_argument("--sim-percentile", type=float, default=95.0)
    p.add_argument("--max-depth", type=int, default=3, help="Max recursion depth for semantic re-splitting")
    args = p.parse_args()

    if not (args.ingest or args.serve): args.ingest = True

    if args.ingest:
        stats = run_ingest(
            target_tokens=args.target_tokens, max_tokens=args.max_tokens,
            overlap_sentences=args.overlap_sentences, buffer_size=args.buffer_size,
            sim_percentile=args.sim_percentile, max_depth=args.max_depth
        )
        print(json.dumps({"ingest_done": True, **stats}, indent=2))
        if args.serve:
            time.sleep(2)
    if args.serve:
        serve()

if __name__ == "__main__":
    main()





