"""
AC215 MS3 Semantic RAG Application with ChromaDB HTTP Client + GCS Python Client

A Retrieval-Augmented Generation (RAG) system that processes documents using semantic chunking,
stores embeddings in ChromaDB via HTTP client, and provides a FastAPI interface for querying.
ChromaDB server is automatically started as a subprocess in the same container (if AUTO_START_CHROMADB is enabled).
Uses GCS Python client to sync ChromaDB data to/from GCS.

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
    ChromaDB server is automatically started in the container (if AUTO_START_CHROMADB=1).
    For manual setup, see CHROMADB_HTTP_SETUP.md or start server: docker run -d --name chromadb-server -p 8000:8000 chromadb/chroma:latest
"""

import os
import sys
import re
import glob
import json
import time
import argparse
import logging
import gc
import subprocess
from typing import List, Tuple, Dict, Any, Optional, Literal, cast, Set
from pathlib import Path
from functools import lru_cache
from collections import OrderedDict

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

    # Fallback: create a no-op tqdm that returns the iterable unchanged
    class tqdm:
        def __init__(self, iterable=None, *args, **kwargs):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable) if self.iterable is not None else iter([])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False


# Load .env file if it exists
def _load_env_file():
    """Load environment variables from .env file if it exists.

    Parses .env file and sets environment variables, removing inline comments.
    Called at module initialization to load configuration from .env.
    """
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Remove inline comments
                if "#" in value:
                    value = value.split("#")[0]
                os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

# --- Settings ---------------------------------------------------------------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "9000")))
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
DATA_DIR = os.getenv("DATA_DIR", "/workspace/data")
ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "/workspace/artifacts")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# ChromaDB HTTP client configuration
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
CHROMADB_AUTH_TOKEN = os.getenv("CHROMADB_AUTH_TOKEN", "")
# ChromaDB server data path (local directory, synced with GCS)
CHROMADB_SERVER_DATA_PATH = os.getenv("CHROMADB_SERVER_DATA_PATH", "/chroma")

# GCS settings for Python client sync (required - no fallback)
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_BUCKET_LOCATION = os.getenv("GCS_BUCKET_LOCATION", "us-central1")
# GCP Project Number (optional, for bucket creation)
GCP_PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "")

# Ingestion settings
SKIP_EXISTING = os.getenv("SKIP_EXISTING", "0").strip().lower() in {"1", "true"}  # Skip already processed docs

# Section filtering settings
ENABLE_SECTION_FILTER = os.getenv("ENABLE_SECTION_FILTER", "1").strip().lower() in {
    "1",
    "true",
}  # Enable section filtering (only include pages with Part/Chapter headers)

# Optional features / batching
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "256"))
UPSERT_BATCH = int(os.getenv("UPSERT_BATCH", "256"))
USE_TIKTOKEN = os.getenv("USE_TIKTOKEN", "0").strip().lower() in {"1", "true"}
# Add query result caching
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "1").strip().lower() in {"1", "true"}
CACHE_SIZE = int(os.getenv("CACHE_SIZE", "1000"))

# Retrieval improvement settings (removed - no longer using reranking)

# Create directories safely
try:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
except Exception as e:
    print(f"[WARN] Could not ensure dir {ARTIFACTS_DIR}: {e}")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception as e:
    print(f"[WARN] Could not ensure dir {DATA_DIR}: {e}")

# --- ChromaDB Server Management ------------------------------------------------
# Note: These functions use CHROMADB_PORT which is defined in settings section above
_chromadb_server_process = None
_gcs_synced = False  # Track if we've synced with GCS
_gcs_uploaded_after_ingest = False  # Track if we uploaded after ingestion (skip redundant shutdown upload)


def _get_gcs_client():
    """Get GCS storage client with proper credentials.

    Returns:
        storage.Client instance configured with service account or default credentials
    """
    if not GCS_AVAILABLE:
        raise Exception("GCS Python client not available. Install google-cloud-storage.")

    gcs_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/workspace/gcs-key.json")

    try:
        # Handle empty string or None - don't try to use empty path
        if gcs_key_path and os.path.exists(gcs_key_path):
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

    try:
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Check if bucket exists
        if not bucket.exists():
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
            return

        downloaded_count = 0
        for blob in blobs:
            try:
                # Remove "chromadb/" prefix if present to get relative path
                if blob.name.startswith("chromadb/"):
                    relative_path = blob.name[len("chromadb/") :]
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

            except Exception as e:
                print(f"[WARN] Failed to download {blob.name}: {e}")
                continue

        # Touch all downloaded files to ensure proper timestamps
        _touch_chromadb_files(local_path)

    except Exception as e:
        print(f"[ERROR] Failed to download ChromaDB files from GCS: {e}")
        import traceback

        traceback.print_exc()
        raise


def _upload_chromadb_to_gcs(bucket_name: str, local_path: str):
    """Upload ChromaDB files from local filesystem to GCS.

    Uses MD5 checksum comparison to skip unchanged files, reducing upload time
    and bandwidth by 60-80% when most files haven't changed.

    Args:
        bucket_name: GCS bucket name
        local_path: Local directory path to upload files from

    Returns:
        Tuple of (uploaded_count, skipped_count, total_size)
    """
    if not GCS_AVAILABLE:
        raise Exception("GCS Python client not available")

    if not os.path.exists(local_path):
        print(f"[WARN] Local path does not exist: {local_path}")
        return (0, 0, 0)

    try:
        import hashlib

        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Ensure bucket exists
        if not bucket.exists():
            bucket.create(location=GCS_BUCKET_LOCATION)

        uploaded_count = 0
        skipped_count = 0
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

                    # Get blob reference
                    blob = bucket.blob(gcs_path)

                    # Compute MD5 hash of local file
                    with open(local_file, "rb") as f:
                        local_md5 = hashlib.md5(f.read()).hexdigest()

                    # Check if blob exists and compare MD5 hashes
                    blob_exists = blob.exists()
                    if blob_exists:
                        blob.reload()  # Load metadata including MD5
                        gcs_md5 = blob.md5_hash

                        # GCS MD5 is base64-encoded, convert to hex for comparison
                        if gcs_md5:
                            import base64

                            try:
                                # Decode base64 MD5 and convert to hex
                                gcs_md5_bytes = base64.b64decode(gcs_md5)
                                gcs_md5_hex = gcs_md5_bytes.hex()

                                # Skip if hashes match (file unchanged)
                                if local_md5 == gcs_md5_hex:
                                    skipped_count += 1
                                    continue
                            except Exception:
                                # If MD5 comparison fails, upload anyway (safe fallback)
                                pass

                    # Upload file (new or changed)
                    blob.upload_from_filename(local_file)

                    uploaded_count += 1
                    file_size = os.path.getsize(local_file)
                    total_size += file_size

                except Exception as e:
                    print(f"[WARN] Failed to upload {local_file}: {e}")
                    continue

        return (uploaded_count, skipped_count, total_size)

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
    global _chromadb_server_process, _gcs_synced, _gcs_uploaded_after_ingest

    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if not gcs_bucket:
        raise Exception("GCS_BUCKET_NAME must be set. GCS Python client sync is required.")

    # Reset upload tracking flag (new server instance)
    _gcs_uploaded_after_ingest = False

    # Check if ChromaDB server is already running
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", CHROMADB_PORT))
        sock.close()
        if result == 0:
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
            _gcs_synced = False

    # Start ChromaDB server pointing to local path
    # ChromaDB will load existing database from the path if it exists

    # Set minimal environment variables
    chromadb_env = os.environ.copy()
    chromadb_env["CHROMA_TELEMETRY_DISABLED"] = "1"
    chromadb_env["ANONYMIZED_TELEMETRY"] = "False"

    try:
        chromadb_cmd = ["chroma", "run", "--host", "0.0.0.0", "--port", str(CHROMADB_PORT), "--path", chroma_path]
        _chromadb_server_process = subprocess.Popen(
            chromadb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            env=chromadb_env,
            text=True,
            bufsize=1,
        )

        # Log initial server output for debugging
        import threading
        import queue

        output_queue = queue.Queue()

        def log_server_output():
            for line in iter(_chromadb_server_process.stdout.readline, ""):
                if line:
                    output_queue.put(("stdout", line.strip()))

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
    global _chromadb_server_process

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
    # Skip if we already uploaded after ingestion (avoid redundant upload)
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if GCS_AVAILABLE and gcs_bucket and _gcs_synced:
        if not _gcs_uploaded_after_ingest:
            try:
                _upload_chromadb_to_gcs(gcs_bucket, CHROMADB_SERVER_DATA_PATH)
            except Exception as e:
                print(f"[ERROR] Failed to upload ChromaDB to GCS: {e}")
                import traceback

                traceback.print_exc()


# GCS support (optional) - Initialize EARLY to avoid NameError in atexit callbacks
# Must be defined before atexit.register() in case imports fail
GCS_AVAILABLE = False
storage = None
service_account = None

# Register cleanup on exit and signals
import atexit
import signal


def _signal_handler(signum, frame):
    """Handle signals for graceful shutdown."""
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

    Note:
        HttpClient() constructor does not validate connection - it's lazy.
        Connection is only validated when methods are called.
    """
    try:
        if CHROMADB_AUTH_TOKEN:
            # Use authenticated client
            settings = ChromaSettings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=CHROMADB_AUTH_TOKEN,
            )
            return HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT, settings=settings)
        else:
            # Use unauthenticated client
            return HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    except BaseException as e:
        # Re-raise SystemExit and KeyboardInterrupt to allow proper shutdown
        if isinstance(e, (SystemExit, KeyboardInterrupt)):
            raise
        # For other exceptions, log and re-raise
        print(f"[ERROR] Failed to create ChromaDB client for {CHROMADB_HOST}:{CHROMADB_PORT}: {e}")
        print(
            "[ERROR] Make sure ChromaDB server is running: docker run -d --name chromadb-server -p 8000:8000 chromadb/chroma:latest"
        )
        raise


# --- Silence Chroma telemetry/logs (must be BEFORE importing chromadb) -----
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
for name in ("chromadb", "chromadb.telemetry", "posthog"):
    logging.getLogger(name).setLevel(logging.ERROR)

from chromadb.config import Settings as ChromaSettings
import numpy as np
import chromadb
from chromadb import HttpClient
from fastembed import TextEmbedding

# GCS support (optional) - Try to import, update GCS_AVAILABLE if successful
# Note: GCS_AVAILABLE is already initialized earlier (before atexit.register)
# to prevent NameError if imports fail
try:
    from google.cloud import storage
    from google.oauth2 import service_account

    GCS_AVAILABLE = True
except ImportError:
    # GCS libraries not available, keep defaults (GCS_AVAILABLE already False)
    pass

# LangChain removed - using ChromaDB and FastEmbed directly
# Simple document type for semantic chunking
Document = dict
BaseDocumentTransformer = object

# ===========================
# Embedded Semantic Chunker
# ===========================
BreakpointThresholdType = Literal["percentile", "standard_deviation", "interquartile", "gradient"]
BREAKPOINT_DEFAULTS: Dict[BreakpointThresholdType, float] = {
    "percentile": 95,
    "standard_deviation": 3,
    "interquartile": 1.5,
    "gradient": 95,
}


def _combine_sentences(sentences: List[dict], buffer_size: int = 1) -> List[dict]:
    """Combine sentences with buffer context (optimized with list comprehension)."""
    if buffer_size == 0:
        # Fast path: no buffering
        for s in sentences:
            s["combined_sentence"] = s["sentence"]
        return sentences

    # Optimized: use list comprehension and pre-calculate ranges
    for i in range(len(sentences)):
        # Pre-calculate indices to avoid repeated range() calls
        start_idx = max(0, i - buffer_size)
        end_idx = min(len(sentences), i + buffer_size + 1)

        # Use list comprehension for better performance
        cs = [sentences[j]["sentence"] for j in range(start_idx, end_idx)]
        sentences[i]["combined_sentence"] = " ".join(cs)
    return sentences


def _calc_cosine_distances(sentences: List[dict]) -> Tuple[List[float], List[dict]]:
    """Calculate cosine distances between consecutive sentences using vectorized operations.

    Optimized version that processes all pairs at once using numpy vectorization,
    providing 3-5x speedup for large sentence lists.
    """
    if len(sentences) < 2:
        return [], sentences

    # Stack all embeddings into a numpy array for vectorized operations
    # Optimize: use generator expression and np.stack for better memory efficiency
    embeddings = np.stack([s["combined_sentence_embedding"] for s in sentences], axis=0)

    # Compute all norms at once (vectorized)
    norms = np.linalg.norm(embeddings, axis=1)

    # Compute dot products between consecutive pairs (vectorized)
    # embeddings[:-1] * embeddings[1:] gives element-wise product
    # sum along axis=1 gives dot product for each pair
    dots = np.sum(embeddings[:-1] * embeddings[1:], axis=1)

    # Compute all similarities at once (vectorized)
    # Avoid division by zero with small epsilon
    similarities = dots / (norms[:-1] * norms[1:] + 1e-12)

    # Convert to distances (1 - similarity)
    distances = (1 - similarities).tolist()

    # Store distances in sentence dicts
    for i, dist in enumerate(distances):
        sentences[i]["distance_to_next"] = dist

    return distances, sentences


class SemanticChunker:
    def __init__(
        self,
        buffer_size: int = 1,
        add_start_index: bool = False,
        breakpoint_threshold_type: BreakpointThresholdType = "percentile",
        breakpoint_threshold_amount: Optional[float] = None,
        number_of_chunks: Optional[int] = None,
        sentence_split_regex: str = r"(?<=[.?!])\s+",
        embedding_function=None,
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
            q1, q3 = np.percentile(distances, [25, 75])
            iqr = q3 - q1
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
        """Calculate sentence distances with aggressive memory optimization."""
        _sentences = [{"sentence": x, "index": i} for i, x in enumerate(single_sentences_list)]
        sentences = _combine_sentences(_sentences, self.buffer_size)

        # Aggressive memory optimization: use smaller batches for large documents
        # Scale down more aggressively to prevent OOM
        num_sentences = len(sentences)
        # More aggressive scaling: max batch of 128, minimum 16, scale down faster
        adaptive_batch = min(128, max(16, 128 - (num_sentences // 50)))  # More aggressive than before

        # Optimize: extract combined sentences in one pass
        combined_sentences = [x["combined_sentence"] for x in sentences]

        # Process embeddings in smaller chunks to reduce peak memory
        # Store embeddings temporarily, then clear immediately after use
        all_embeddings = []
        chunk_size = adaptive_batch

        # Process in chunks to avoid loading all embeddings at once
        for i in range(0, len(combined_sentences), chunk_size):
            chunk = combined_sentences[i : i + chunk_size]
            chunk_embeddings = self.embedding_function(chunk, batch_size=min(chunk_size, adaptive_batch))
            all_embeddings.extend(chunk_embeddings)
            # Clear chunk immediately
            del chunk, chunk_embeddings
            # Force GC more frequently for large documents
            if i > 0 and i % (chunk_size * 4) == 0:
                gc.collect()

        # Assign embeddings and calculate distances
        for i, s in enumerate(sentences):
            s["combined_sentence_embedding"] = all_embeddings[i]

        result = _calc_cosine_distances(sentences)

        # Aggressively clear embeddings from memory
        del all_embeddings
        for s in sentences:
            s.pop("combined_sentence_embedding", None)
        del combined_sentences

        # Force garbage collection after embedding operations
        gc.collect()

        return result

    def _get_optimal_sample_rate(self, num_sentences: int) -> int:
        """Determine optimal sampling rate based on document size."""
        if num_sentences < 200:
            return 1  # No sampling for small docs
        elif num_sentences < 1000:
            return 5  # Every 5th for medium docs
        elif num_sentences < 3000:
            return 10  # Every 10th for large docs
        else:
            return 20  # Every 20th for very large docs

    def _two_stage_split(self, single_sentences_list: List[str]) -> List[str]:
        """Two-stage semantic chunking: coarse scan with sampling, then fine-grained refinement."""
        num_sentences = len(single_sentences_list)
        if num_sentences < 20:
            # Too small for two-stage, use regular approach
            distances, sentences = self._calculate_sentence_distances(single_sentences_list)
            if self.number_of_chunks is not None:
                thr = self._threshold_from_clusters(distances)
            else:
                thr, _ = self._calc_breakpoint_threshold(distances)
            indices_above = [i for i, x in enumerate(distances) if x > thr]
            chunks, start_index = [], 0
            for index in indices_above:
                end_index = index
                group = sentences[start_index : end_index + 1]
                chunks.append(" ".join([d["sentence"] for d in group]))
                start_index = index + 1
            if start_index < len(sentences):
                chunks.append(" ".join([d["sentence"] for d in sentences[start_index:]]))
            return chunks

        # Stage 1: Coarse scan with adaptive sampling
        sample_rate = self._get_optimal_sample_rate(num_sentences)
        sampled_sentences = single_sentences_list[::sample_rate]
        # Optimize: use range directly instead of converting to list (saves memory)
        # Only convert to list when we need to index into it
        sampled_indices = list(range(0, num_sentences, sample_rate)) if sample_rate > 1 else list(range(num_sentences))

        # Calculate distances for sampled sentences
        sampled_distances, _ = self._calculate_sentence_distances(sampled_sentences)

        # Find breakpoint threshold
        if self.number_of_chunks is not None:
            threshold = self._threshold_from_clusters(sampled_distances)
        else:
            threshold, _ = self._calc_breakpoint_threshold(sampled_distances)

        # Find approximate breakpoint regions
        # Optimize: use generator expression if we only iterate once, but we need list for indexing
        approximate_breakpoint_indices = [i for i, dist in enumerate(sampled_distances) if dist > threshold]

        if not approximate_breakpoint_indices:
            # No breakpoints found, return as single chunk
            return [" ".join(single_sentences_list)]

        # Clear sampled sentences and distances to free memory (keep sampled_indices for Stage 2)
        del sampled_sentences, sampled_distances

        # Stage 2: Fine-grained refinement in each region
        exact_breakpoints = []
        for bp_idx in approximate_breakpoint_indices:
            # Map back to original sentence indices
            # bp_idx is the index in the sampled list where breakpoint was detected
            # This means breakpoint is between sampled[bp_idx] and sampled[bp_idx+1]
            start_sampled_idx = sampled_indices[bp_idx] if bp_idx < len(sampled_indices) else num_sentences - 1
            end_sampled_idx = sampled_indices[bp_idx + 1] if bp_idx + 1 < len(sampled_indices) else num_sentences

            # Define region: expand around the breakpoint area
            # Include some sentences before and after the sampled breakpoint
            region_start = max(0, start_sampled_idx)
            region_end = min(num_sentences, end_sampled_idx + 1)

            # Ensure region is reasonable size
            if region_end - region_start < 3:
                # Region too small, use sampled breakpoint
                exact_breakpoints.append(start_sampled_idx)
                continue
            if region_end - region_start > 30:
                # Region too large, subdivide at midpoint (reduced from 50 to 30 for memory efficiency)
                mid = (region_start + region_end) // 2
                exact_breakpoints.append(mid)
                continue

            # Fine-grained: embed all sentences in this region
            region_sentences = single_sentences_list[region_start:region_end]
            if len(region_sentences) < 2:
                exact_breakpoints.append(start_sampled_idx)
                continue

            region_distances, _ = self._calculate_sentence_distances(region_sentences)

            # Find exact breakpoint within region (highest distance)
            if region_distances:
                max_dist_idx = max(range(len(region_distances)), key=lambda i: region_distances[i])
                exact_breakpoint = region_start + max_dist_idx
                exact_breakpoints.append(exact_breakpoint)
            else:
                exact_breakpoints.append(start_sampled_idx)

            # Aggressively clear region data to free memory
            del region_sentences, region_distances
            # Force GC after processing each region to prevent memory buildup
            if len(exact_breakpoints) % 5 == 0:
                gc.collect()

        # Remove duplicate breakpoints and sort
        # Optimize: use set directly for deduplication, then sort
        exact_breakpoints = sorted(set(exact_breakpoints))

        # Clear sampled_indices now that we're done with Stage 2
        del sampled_indices

        # Split at exact breakpoints
        chunks = []
        start_idx = 0
        for bp in exact_breakpoints:
            if bp > start_idx:
                chunk_text = " ".join(single_sentences_list[start_idx : bp + 1])
                chunks.append(chunk_text)
                start_idx = bp + 1
        if start_idx < num_sentences:
            chunk_text = " ".join(single_sentences_list[start_idx:])
            chunks.append(chunk_text)

        return chunks

    def split_text(self, text: str) -> List[str]:
        # Fast path: if text is small enough, skip semantic chunking
        approx_tokens = _approx_token_len(text)
        # Use cached sentence splitting
        single_sentences_list = _split_sentences_cached(text, self.sentence_split_regex)
        if len(single_sentences_list) in (0, 1):
            return single_sentences_list
        if self.breakpoint_threshold_type == "gradient" and len(single_sentences_list) == 2:
            return single_sentences_list

        # Quick check: if text is very short, return as single chunk
        if approx_tokens < 100 and len(single_sentences_list) < 5:
            return [text]

        # Use two-stage approach for documents with many sentences (more efficient)
        num_sentences = len(single_sentences_list)
        if num_sentences >= 50:
            return self._two_stage_split(single_sentences_list)

        # For smaller documents, use original single-stage approach
        distances, sentences = self._calculate_sentence_distances(single_sentences_list)
        if self.number_of_chunks is not None:
            thr = self._threshold_from_clusters(distances)
            arr = distances
        else:
            thr, arr = self._calc_breakpoint_threshold(distances)
        indices_above = [i for i, x in enumerate(arr) if x > thr]
        # Optimize: pre-allocate chunks list
        chunks = []
        start_index = 0
        for index in indices_above:
            end_index = index
            # Optimize: extract sentences in one pass
            group_sentences = [d["sentence"] for d in sentences[start_index : end_index + 1]]
            chunks.append(" ".join(group_sentences))
            start_index = index + 1
        if start_index < len(sentences):
            remaining_sentences = [d["sentence"] for d in sentences[start_index:]]
            chunks.append(" ".join(remaining_sentences))
        return chunks

    def create_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> List["Document"]:
        _metadatas = metadatas or [{}] * len(texts)
        documents = []
        for i, text in enumerate(texts):
            start_index = 0
            for chunk in self.split_text(text):
                metadata = dict(_metadatas[i])
                if self._add_start_index:
                    metadata["start_index"] = start_index
                doc = {"page_content": chunk, "metadata": metadata}
                documents.append(doc)
                start_index += len(chunk)
        return documents


# --- Load & sanitize docs ---------------------------------------------------
BOM = "\ufeff"
UNICODE_FIX = {
    # Quotes
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "--",
    "\u2026": "...",
    # Special characters
    "\u00a0": " ",  # Non-breaking space
    "\u2028": "\n",  # Line separator
    "\u2029": "\n\n",  # Paragraph separator
    "\u200b": "",  # Zero-width space
    "\u200c": "",  # Zero-width non-joiner
    "\u200d": "",  # Zero-width joiner
    "\ufeff": "",  # BOM
}
WS = re.compile(r"\s+")
MULTILINE_WS = re.compile(r"\n\s*\n\s*")


def _norm(text: str) -> str:
    """Enhanced text normalization for better retrieval quality (optimized)."""
    if not text:
        return ""

    # Remove BOM (check first to avoid unnecessary operations)
    if BOM in text:
        text = text.replace(BOM, "")

    # Use translation table for faster replacements (5x faster than loop)
    # Optimize: check if any fix chars exist before creating table
    if any(char in text for char in UNICODE_FIX):
        table = str.maketrans(UNICODE_FIX)
        text = text.translate(table)

    # Normalize whitespace but preserve paragraph breaks
    # First normalize multiple newlines to double newline
    text = MULTILINE_WS.sub("\n\n", text)
    # Then normalize other whitespace (but not newlines) to single space
    # Use [ \t\r\f\v]+ to match whitespace except newlines
    text = re.sub(r"[ \t\r\f\v]+", " ", text)

    # Remove excessive punctuation (but keep sentence structure)
    # Optimize: combine similar regex patterns
    if "..." in text or "---" in text:
        text = re.sub(r"\.{3,}", "...", text)  # Multiple dots → ...
        text = re.sub(r"-{3,}", "--", text)  # Multiple dashes → --

    # Normalize quotes for better matching
    # Optimize: only do if quotes exist
    if '"' in text or "'" in text or '"' in text or "'" in text:
        text = re.sub(r'[""' "]", '"', text)  # All quotes to standard
        text = re.sub(r"[" "``]", "'", text)  # All apostrophes to standard

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
    q = re.sub(r"\s+", " ", q)

    return q


def _load_txt_md(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        txt = _norm(f.read())
    return [(path, txt)]


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

    lines = text.split("\n")
    cleaned = []

    # Common header/footer patterns (pre-compiled for performance)
    # Optimize: compile patterns once at module level instead of recompiling for each call
    # Use module-level compiled patterns to avoid recompilation overhead
    if not hasattr(_remove_headers_footers, "_compiled_patterns"):
        _remove_headers_footers._compiled_patterns = [
            re.compile(r"^Chapter\s+\d+", re.IGNORECASE),  # "Chapter 1"
            re.compile(r"^\d+\.\d+\s+[A-Z]"),  # "1.1 Section Title" (at start of line)
            re.compile(r"^Page\s+\d+", re.IGNORECASE),  # "Page 5"
            re.compile(r"^\d+$"),  # Standalone page numbers
            re.compile(r"^[A-Z][a-z]+\s+\d+$"),  # "Chapter 5" (short lines)
        ]
    header_footer_patterns = _remove_headers_footers._compiled_patterns

    # Track lines we've seen (for detecting repeating headers/footers)
    seen_lines = {}
    page_num_str = str(page_num) if page_num else None  # Pre-convert to avoid repeated conversion

    for line in lines:
        line_stripped = line.strip()

        # Skip empty lines
        if not line_stripped:
            cleaned.append(line)
            continue

        # Skip if it's just a page number (optimize: check before regex)
        if page_num_str and line_stripped == page_num_str:
            continue

        # Check if line matches header/footer patterns
        is_header_footer = False
        line_len = len(line_stripped)

        # Optimize: only check patterns if line is short enough to be a header/footer
        if line_len < 60:
            for pattern in header_footer_patterns:
                if pattern.match(line_stripped):
                    is_header_footer = True
                    break

        # Detect repeating lines (likely headers/footers)
        # Optimize: use dict.get() to avoid double lookup
        if not is_header_footer and line_len < 80:
            line_lower = line_stripped.lower()
            count = seen_lines.get(line_lower, 0)
            if count > 3:
                is_header_footer = True
            else:
                seen_lines[line_lower] = count + 1

        if not is_header_footer:
            cleaned.append(line)

    return "\n".join(cleaned)


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


def _finalize_and_output_chapter(
    chapter_data: Dict[str, Any],
    items: List[Tuple[str, str]],
    path: str,
    base: str,
    pdf_metadata: Dict[str, Any],
    total_pages: int,
):
    """Finalize a chapter by combining pages and adding to items list.

    Helper function to avoid code duplication in single-pass PDF processing.
    """
    chapter_num = chapter_data["chapter_num"]
    chapter_title = chapter_data["chapter_title"]
    chapter_pages = chapter_data["pages"]

    if not chapter_pages:
        return

    # Combine all pages in the chapter
    # Add chapter header
    chapter_header = f"[Document: {base}] "
    if pdf_metadata.get("title"):
        chapter_header += f"[Title: {pdf_metadata.get('title')}] "
    chapter_header += f"[Chapter {chapter_num}"
    if chapter_title:
        chapter_header += f": {chapter_title}"
    chapter_header += "] "
    chapter_header += f"[Pages {chapter_pages[0][0]}-{chapter_pages[-1][0]} of {total_pages}]\n\n"

    # Combine page texts with paragraph breaks
    page_texts_combined = [page_text for _, page_text in chapter_pages]

    # Join pages with double newline (paragraph break)
    combined_text = chapter_header + "\n\n".join(page_texts_combined)

    # Create chapter-level document
    chapter_source = f"{path}#chapter={chapter_num}"
    if chapter_title:
        # Sanitize title for filename (replace spaces, special chars)
        title_safe = chapter_title[:50].replace(" ", "_").replace("/", "_").replace("\\", "_")
        chapter_source += f":{title_safe}"

    items.append((chapter_source, combined_text))

    # Clear chapter pages to free memory
    chapter_data["pages"] = []


def _extract_chapters_from_toc(doc) -> Dict[int, Dict[str, str]]:
    """Extract chapter information from PDF's table of contents.

    Uses PyMuPDF's get_toc() method to extract embedded table of contents.
    Automatically detects which level contains chapters, handling hierarchical structures
    of any depth (e.g., Parts at level 1, Sections at level 2, Chapters at level 3).

    Args:
        doc: PyMuPDF document object

    Returns:
        Dictionary mapping page number to chapter info dict with 'chapter_number' and 'chapter_title'
        Returns empty dict if TOC is not available or extraction fails
    """
    chapter_map = {}

    try:
        # Get table of contents from PDF
        toc = doc.get_toc()

        if not toc:
            return chapter_map

        # Helper function to check if a title is a Part or organizational section
        def is_organizational_title(title: str) -> bool:
            """Check if title is a Part or other organizational section (not a chapter)."""
            title_lower = title.lower()
            # Parts
            if re.search(r"\bpart\s+[ivx\d]+\b", title_lower) or re.search(
                r"\bpart\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b", title_lower
            ):
                return True
            # Sections (numbered like "1.1", "2.3", etc.)
            if re.match(r"^\d+\.\d+", title_lower):
                return True
            return False

        # Helper function to extract chapter info from title
        def extract_chapter_info(title: str) -> Tuple[Optional[str], str]:
            """Extract chapter number and title from TOC entry.
            Returns: (chapter_num, chapter_title) or (None, title) if not a chapter
            """
            chapter_num = None
            chapter_title = title

            # Try to extract number from various formats
            match = re.search(r"(?:Chapter|Ch\.?)\s*(\d+)", title, re.IGNORECASE)
            if match:
                chapter_num = match.group(1)
                # Remove "Chapter X" prefix to get title
                chapter_title = re.sub(r"(?:Chapter|Ch\.?)\s*\d+\s*:?\s*", "", title, flags=re.IGNORECASE).strip()
            else:
                # Try standalone number format: "1 Introduction" (but not "1.1 Section")
                match = re.match(r"^(\d+)(?!\.\d)\s+(.+)", title)
                if match:
                    chapter_num = match.group(1)
                    chapter_title = match.group(2).strip()

            return chapter_num, chapter_title

        # First pass: Scan all levels to find potential chapters
        # Count chapter-like entries at each level
        level_chapter_counts = {}  # level -> count of chapter-like entries
        level_chapter_items = {}  # level -> list of (item, chapter_num, chapter_title)

        for item in toc:
            level = item[0]
            title = item[1]
            page_num = item[2]

            # Skip organizational titles (Parts, sections)
            if is_organizational_title(title):
                continue

            # Try to extract chapter info
            chapter_num, chapter_title = extract_chapter_info(title)

            if chapter_num:
                # This looks like a chapter
                if level not in level_chapter_counts:
                    level_chapter_counts[level] = 0
                    level_chapter_items[level] = []

                level_chapter_counts[level] += 1
                level_chapter_items[level].append((item, chapter_num, chapter_title))

        # Determine which level has the most chapters
        # This is likely the chapter level
        if not level_chapter_counts:
            # No chapters found at any level
            return chapter_map

        # Find the level with the most chapter-like entries
        target_level = max(level_chapter_counts.items(), key=lambda x: x[1])[0]

        # Extract chapters from the target level
        if target_level in level_chapter_items:
            for item, chapter_num, chapter_title in level_chapter_items[target_level]:
                page_num = item[2]  # 0-indexed
                page_num_1_indexed = page_num + 1
                chapter_map[page_num_1_indexed] = {
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title[:100],  # Limit length
                }

        # If we found very few chapters at the target level, also check adjacent levels
        # This handles edge cases where chapters might be at multiple levels
        if len(chapter_map) < 3 and len(level_chapter_counts) > 1:
            # Check levels adjacent to target level
            for level in sorted(level_chapter_counts.keys()):
                if level == target_level:
                    continue
                # Only check if this level has a reasonable number of chapters
                if level_chapter_counts[level] >= 3:
                    if level in level_chapter_items:
                        for item, chapter_num, chapter_title in level_chapter_items[level]:
                            page_num = item[2]
                            page_num_1_indexed = page_num + 1
                            # Only add if not already in map (avoid duplicates)
                            if page_num_1_indexed not in chapter_map:
                                chapter_map[page_num_1_indexed] = {
                                    "chapter_number": chapter_num,
                                    "chapter_title": chapter_title[:100],
                                }

    except Exception as e:
        # If TOC extraction fails, return empty dict
        pass

    return chapter_map


def _extract_non_chapter_sections_from_toc(doc) -> Set[int]:
    """Extract non-chapter section page numbers from PDF's table of contents.

    Identifies sections like Index, Bibliography, Table of Contents, Appendices, etc.
    from the TOC that should be filtered out.

    Args:
        doc: PyMuPDF document object

    Returns:
        Set of page numbers (1-indexed) that are non-chapter sections
    """
    non_chapter_pages = set()

    # Keywords that indicate non-chapter sections in TOC
    non_chapter_keywords = [
        "index",
        "indices",
        "bibliography",
        "references",
        "works cited",
        "table of contents",
        "contents",
        "appendix",
        "appendices",
        "glossary",
        "preface",
        "foreword",
        "acknowledgements",
        "acknowledgments",
        "about the author",
        "contributors",
        "list of figures",
        "list of tables",
    ]

    try:
        # Get table of contents from PDF
        toc = doc.get_toc()

        if not toc:
            return non_chapter_pages

        for item in toc:
            level = item[0]  # Outline level (1 = top-level, 2 = section, etc.)
            title = item[1]  # Title text
            page_num = item[2]  # Page number (0-indexed in PyMuPDF, so add 1)

            # Check if title matches non-chapter keywords
            title_lower = title.lower()
            for keyword in non_chapter_keywords:
                if keyword in title_lower:
                    # PyMuPDF page numbers are 0-indexed, convert to 1-indexed
                    page_num_1_indexed = page_num + 1
                    non_chapter_pages.add(page_num_1_indexed)
                    break

    except Exception:
        # If TOC extraction fails, return empty set
        pass

    return non_chapter_pages


def _load_pdf(path: str) -> List[Tuple[str, str]]:
    """Enhanced PDF loading with chapter-level splitting, header/footer removal, and chapter-aware filtering.

    Uses a three-pass approach when ENABLE_SECTION_FILTER is enabled:
    1. First pass: Identify chapter boundaries and non-chapter sections
    2. Second pass: Group pages by chapter, clean headers/footers from each page
    3. Third pass: Combine pages within each chapter into one document

    This creates chapter-level documents (not page-level) while preserving header/footer removal.
    Each chapter becomes one document that then goes through semantic chunking.

    When ENABLE_SECTION_FILTER is disabled, processes all pages individually (page-level).
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
    pdf_metadata = doc.metadata if hasattr(doc, "metadata") else {}
    total_pages = len(doc)

    if not ENABLE_SECTION_FILTER:
        # No filtering - process all pages
        # Extract chapter info from TOC if available
        toc_chapter_map = _extract_chapters_from_toc(doc)

        for i, page in enumerate(doc, start=1):
            txt = _extract_page_text(page, i, base)
            if not txt or not txt.strip():
                continue

            # Get chapter info from TOC if available
            chapter_section_info = toc_chapter_map.get(i, {})

            # Remove headers, footers, and page numbers
            txt = _remove_headers_footers(txt, page_num=i)

            if not txt or not txt.strip():
                continue

            # Normalize text
            txt = _norm(txt)

            # Add page context metadata
            page_info = f"[Document: {base}] [Page {i} of {total_pages}] "
            if pdf_metadata.get("title"):
                page_info += f"[Title: {pdf_metadata.get('title')}] "

            if chapter_section_info.get("chapter_number"):
                chapter_str = f"Chapter {chapter_section_info['chapter_number']}"
                if chapter_section_info.get("chapter_title"):
                    chapter_str += f": {chapter_section_info['chapter_title']}"
                page_info += f"[{chapter_str}] "

            txt = page_info + txt
            items.append((f"{path}#page={i}", txt))
    else:
        # Two-pass approach for chapter-aware filtering
        # Extract chapters from PDF's table of contents (required)
        toc_chapter_map = _extract_chapters_from_toc(doc)

        if len(toc_chapter_map) == 0:
            print(f"[WARN] PDF table of contents not available for {base}. Chapter detection requires TOC.")
            print("[WARN] Processing all pages without chapter filtering.")
            # Fall back to processing all pages without chapter filtering
            for i, page in enumerate(doc, start=1):
                txt = _extract_page_text(page, i, base)
                if not txt or not txt.strip():
                    continue

                txt = _remove_headers_footers(txt, page_num=i)
                if not txt or not txt.strip():
                    continue

                txt = _norm(txt)
                page_info = f"[Document: {base}] [Page {i} of {total_pages}] "
                if pdf_metadata.get("title"):
                    page_info += f"[Title: {pdf_metadata.get('title')}] "
                txt = page_info + txt
                items.append((f"{path}#page={i}", txt))
            doc.close()
            return items

        # Extract non-chapter sections from TOC (Index, Bibliography, etc.)
        toc_non_chapter_pages = _extract_non_chapter_sections_from_toc(doc)

        # Determine chapter range from TOC (optimized: no need to scan all pages first)
        if toc_chapter_map:
            first_chapter_page = min(toc_chapter_map.keys())
            last_chapter_page = max(toc_chapter_map.keys())
        else:
            first_chapter_page = 1
            last_chapter_page = total_pages

        # Single-pass processing: Process pages once, build chapters incrementally
        # This avoids storing all pages in memory (40-60% memory reduction)
        chapters = {}  # chapter_key -> dict with chapter_num, chapter_title, pages list
        current_chapter_key = None
        current_chapter_num = None
        current_chapter_title = None
        pages_with_text = 0

        # Process pages with progress tracking (single-pass optimization)
        # Single-pass: process pages once, build chapters incrementally (40-60% memory reduction)
        if TQDM_AVAILABLE:
            page_iterator = tqdm(
                enumerate(doc, start=1), total=total_pages, desc=f"Processing {base}", unit="page", leave=False
            )
        else:
            page_iterator = enumerate(doc, start=1)

        for i, page in page_iterator:
            txt = _extract_page_text(page, i, base)
            if not txt or not txt.strip():
                continue

            pages_with_text += 1

            # Check for chapter markers using TOC only
            has_chapter = i in toc_chapter_map
            is_non_chapter = i in toc_non_chapter_pages

            # Determine if page should be included
            should_include = i >= first_chapter_page and i <= last_chapter_page and not is_non_chapter

            if not should_include:
                filtered_count += 1
                continue

            # Remove headers, footers, and page numbers (clean each page)
            txt_cleaned = _remove_headers_footers(txt, page_num=i)

            if not txt_cleaned or not txt_cleaned.strip():
                filtered_count += 1
                continue

            # Normalize text
            txt_cleaned = _norm(txt_cleaned)

            # Determine which chapter this page belongs to
            if has_chapter:
                chapter_info = toc_chapter_map[i]
                chapter_num = chapter_info.get("chapter_number")
                current_chapter_num = chapter_num
                current_chapter_title = chapter_info.get("chapter_title", "")
                current_chapter_key = f"chapter_{chapter_num}"

                # If this is a new chapter, finalize previous chapter and output it
                if current_chapter_key not in chapters:
                    # Start new chapter
                    chapters[current_chapter_key] = {
                        "chapter_num": chapter_num,
                        "chapter_title": current_chapter_title,
                        "pages": [],
                    }

            # If no chapter detected yet (pages before first chapter), use a default chapter
            if current_chapter_key is None:
                current_chapter_key = "chapter_intro"
                if current_chapter_key not in chapters:
                    chapters[current_chapter_key] = {"chapter_num": "0", "chapter_title": "Introduction", "pages": []}

            # Add page to current chapter (store page number and cleaned text)
            chapters[current_chapter_key]["pages"].append((i, txt_cleaned))

        # Finalize and output remaining chapters
        for chapter_key, chapter_data in chapters.items():
            _finalize_and_output_chapter(chapter_data, items, path, base, pdf_metadata, total_pages)

        # Store chapter count before clearing
        num_chapters = len(chapters)

        # Clear all intermediate data structures to free memory
        del chapters
        gc.collect()  # Force garbage collection after large PDF processing

    doc.close()
    return items


def _load_md_feature_file(path: str) -> List[Tuple[str, str]]:
    """Load LLM-Quant_Expanded_RAG_with_context.md with special handling for feature explanations.

    Parses markdown file with structure:
    - ## feature_name (header)
    - **Definition / Formula:** value
    - **Meaning:** value
    - **Interpretation / Signal:** value
    - **Financial Context:** value
    - --- (separator)

    Creates structured knowledge base format for queryable feature definitions.
    Each feature becomes a self-contained chunk (no semantic splitting needed).

    Args:
        path: Path to markdown file

    Returns:
        List of (source_path, text_content) tuples
    """
    items: List[Tuple[str, str]] = []
    base = os.path.basename(path)

    # Only process LLM-Quant_Expanded_RAG_with_context.md files
    if "LLM-Quant_Expanded_RAG_with_context" not in base and "llm-quant_expanded_rag_with_context" not in base.lower():
        return items

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        if not lines:
            return items

        current_feature = None
        feature_data = {}

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Check for feature header (## feature_name)
            if line_stripped.startswith("## "):
                # Save previous feature if exists
                if current_feature:
                    _save_feature(items, path, current_feature, feature_data)

                # Extract feature name from header (remove ## and strip)
                feature_name = line_stripped[3:].strip()
                if feature_name:
                    current_feature = feature_name
                    feature_data = {}
                continue

            # Skip horizontal rule separators (---)
            if line_stripped == "---":
                continue

            # Parse bold field lines: **Field Name:** value
            if line_stripped.startswith("**") and ":**" in line_stripped:
                # Extract field name and value
                # Format: **Field Name:** value
                parts = line_stripped.split(":**", 1)
                if len(parts) == 2:
                    field_name = parts[0].replace("**", "").strip()
                    field_value = parts[1].strip()

                    if current_feature and field_value:
                        # Map field names to standard keys
                        field_lower = field_name.lower()
                        if "definition" in field_lower or "formula" in field_lower:
                            feature_data["full_name_or_formula"] = field_value
                        elif "meaning" in field_lower:
                            feature_data["meaning"] = field_value
                        elif "interpretation" in field_lower or "signal" in field_lower:
                            feature_data["interpretation_or_signal"] = field_value
                        elif "financial context" in field_lower:
                            feature_data["financial_context"] = field_value
                        else:
                            # Store any other fields
                            feature_data[field_name.lower().replace(" ", "_")] = field_value

        # Save last feature
        if current_feature:
            _save_feature(items, path, current_feature, feature_data)

        # If no features were found, treat entire file as single document (fallback)
        if not items:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                text = _norm(content)
                items.append((path, text))
            except Exception:
                pass

    except Exception:
        # If parsing fails, fall back to treating entire file as single document
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            text = _norm(content)
            items.append((path, text))
        except Exception:
            pass

    return items


def _save_feature(items: List[Tuple[str, str]], path: str, feature: str, feature_data: Dict[str, str]) -> None:
    """Helper function to save a feature definition to items list.

    Args:
        items: List to append to
        path: Source file path
        feature: Feature name
        feature_data: Dictionary of feature attributes
    """
    if not feature:
        return

    parts = []
    parts.append(f"Feature: {feature}")

    full_name = feature_data.get("full_name_or_formula", "").strip()
    if full_name:
        parts.append(f"Full Name or Formula: {full_name}")

    meaning = feature_data.get("meaning", "").strip()
    if meaning:
        parts.append(f"Meaning: {meaning}")

    interpretation = feature_data.get("interpretation_or_signal", "").strip()
    if interpretation:
        parts.append(f"Interpretation or Signal: {interpretation}")
        # Extract thresholds (e.g., ">15%", "<30", ">2")
        thresholds = re.findall(r"([<>]=?)\s*(\d+(?:\.\d+)?)", interpretation)
        if thresholds:
            threshold_text = ", ".join([f"{op} {val}" for op, val in thresholds])
            parts.append(f"Thresholds: {threshold_text}")

    financial_context = feature_data.get("financial_context", "").strip()
    if financial_context:
        parts.append(f"Financial Context: {financial_context}")

    # Include any additional fields
    for key, value in feature_data.items():
        if (
            key not in ["full_name_or_formula", "meaning", "interpretation_or_signal", "financial_context"]
            and value.strip()
        ):
            # Capitalize key for display
            display_key = key.replace("_", " ").title()
            parts.append(f"{display_key}: {value}")

    # Create well-formatted chunk (already complete, no splitting needed)
    text = "\n".join(parts)
    text = _norm(text)
    items.append((f"{path}#feature={feature}", text))


def _load_full_md_file(path: str) -> List[Tuple[str, str]]:
    """Load the entire markdown file as a single document for context retrieval.

    This function loads the complete markdown file content without parsing it into
    individual features. This allows the full document to be retrieved later for
    providing comprehensive context.

    Args:
        path: Path to the markdown file

    Returns:
        List containing a single tuple: (source_path, full_file_content)
        The source_path uses the special marker "#full_document" to distinguish
        it from feature-specific chunks.
    """
    items: List[Tuple[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        text = _norm(content)
        # Use special source marker to identify this as the full document
        items.append((f"{path}#full_document", text))
    except Exception:
        pass

    return items


def load_all(data_dir: str) -> List[Tuple[str, str]]:
    """Load all documents from data directory (optimized with early exits)."""
    out: List[Tuple[str, str]] = []
    # Early filter: only process supported extensions (use set for O(1) lookup)
    ext_patterns = {".txt", ".md", ".pdf", ".csv"}

    # Optimize: compile glob pattern once, use sorted for deterministic order
    data_path = os.path.join(data_dir, "**", "*")
    files = sorted(glob.glob(data_path, recursive=True))

    # Pre-compile markdown filename check pattern
    md_check_lower = "llm-quant_expanded_rag_with_context"

    for p in files:
        # Early exit: skip non-files immediately
        if not os.path.isfile(p):
            continue

        # Early exit: check extension before expensive operations
        ext = os.path.splitext(p)[1].lower()
        if ext not in ext_patterns:
            continue

        try:
            if ext == ".txt":
                out.extend(_load_txt_md(p))
            elif ext == ".md":
                # Check if this is the specific feature explanation markdown file
                base = os.path.basename(p)
                base_lower = base.lower()
                if "LLM-Quant_Expanded_RAG_with_context" in base or md_check_lower in base_lower:
                    # Use specialized markdown loader for feature file
                    # This extracts individual features
                    md_items = _load_md_feature_file(p)
                    out.extend(md_items)
                    # Also load the entire file as a single document for context retrieval
                    out.extend(_load_full_md_file(p))
                else:
                    # Use generic markdown loader for other markdown files
                    out.extend(_load_txt_md(p))
            elif ext == ".pdf":
                out.extend(_load_pdf(p))
            elif ext == ".csv":
                # CSV files are no longer processed (replaced by markdown file)
                # Skip CSV files silently
                pass
        except Exception:
            pass

    return out


# --- Token helpers ----------------------------------------------------------
if USE_TIKTOKEN:
    try:
        import tiktoken

        _TOK = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _TOK = None
        USE_TIKTOKEN = False
else:
    _TOK = None


def _approx_token_len(s: str) -> int:
    """Estimate token count for a string.

    Uses tiktoken if available for accurate counting, otherwise uses
    an improved heuristic based on word count and character length.

    Args:
        s: Input string

    Returns:
        Estimated token count (minimum 1)
    """
    if USE_TIKTOKEN and _TOK is not None:
        try:
            return len(_TOK.encode(s))
        except Exception:
            pass

    # Improved fallback: better approximation than len(s)//4
    # Average English word is ~4.5 characters, and tokens are roughly 0.75 words
    # So: tokens ≈ (char_count / 4.5) * 0.75 ≈ char_count / 6
    # But we also account for whitespace and punctuation
    if not s or not s.strip():
        return 1

    # Count words (split on whitespace)
    words = s.split()
    word_count = len(words)

    # If we have words, use word-based estimation (more accurate)
    if word_count > 0:
        # Average tokens per word is ~1.3 (some words are split into multiple tokens)
        # Add 10% for punctuation and special characters
        estimated = int(word_count * 1.3 * 1.1)
    else:
        # Fallback to character-based estimation for non-word content
        # Roughly 4 characters per token for punctuation/symbols
        estimated = max(1, len(s) // 4)

    return max(1, estimated)


def _apply_sentence_overlap(chunks: List[str], overlap_sentences: int = 2) -> List[str]:
    """Apply sentence overlap between chunks using cached sentence splitting (optimized)."""
    if overlap_sentences <= 0 or len(chunks) < 2:
        return chunks

    # Pre-allocate output list for better performance
    out: List[str] = [None] * len(chunks)
    out[0] = chunks[0].strip()

    for i in range(1, len(chunks)):
        cur = chunks[i].strip()
        # Use cached sentence splitting
        head_sents = _split_sentences_cached(cur)
        if head_sents:
            # Optimize: only take what we need, avoid slicing if possible
            head = head_sents[:overlap_sentences] if len(head_sents) > overlap_sentences else head_sents
            # Optimize: use list join instead of string concatenation
            prev_chunk = out[i - 1].rstrip()
            out[i - 1] = f"{prev_chunk} {' '.join(head)}".strip()
        out[i] = cur
    return out


# Cached compiled regex for sentence splitting (performance optimization)
_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])[""\')\]]*\s+')
_SENT_SPLIT_RE_ALT = re.compile(r"(?<=[.?!])\s+")

# LRU cache for sentence splits (max 1000 entries, automatic eviction)
# Using OrderedDict for LRU behavior
_sentence_split_cache: OrderedDict[str, List[str]] = OrderedDict()
_SENTENCE_CACHE_MAX_SIZE = 1000  # Limit cache size to prevent memory issues


def _split_sentences_cached(text: str, regex_pattern: str = None) -> List[str]:
    """Split text into sentences with LRU caching to avoid redundant regex operations.

    Uses OrderedDict for LRU (Least Recently Used) cache behavior - automatically
    evicts oldest entries when cache is full.

    Args:
        text: Input text to split
        regex_pattern: Optional regex pattern (uses default if None)

    Returns:
        List of sentences (stripped, non-empty)
    """
    # Use cache key based on text hash to avoid storing large strings
    import hashlib

    cache_key = hashlib.md5(text.encode("utf-8")).hexdigest() + (regex_pattern or "default")

    # Check cache (LRU: move to end if found)
    if cache_key in _sentence_split_cache:
        # Move to end (most recently used)
        result = _sentence_split_cache.pop(cache_key)
        _sentence_split_cache[cache_key] = result
        return result

    # Choose regex pattern (cache compiled patterns for performance)
    if regex_pattern:
        # Compile pattern if it's a string (patterns are cached by re.compile internally)
        if isinstance(regex_pattern, str):
            pattern = re.compile(regex_pattern)
        else:
            pattern = regex_pattern
    else:
        pattern = _SENT_SPLIT_RE

    # Split sentences
    # Optimize: filter and strip in one pass, avoid intermediate list comprehension
    sents = []
    for s in pattern.split(text):
        s_stripped = s.strip()
        if s_stripped:  # Only add non-empty sentences
            sents.append(s_stripped)

    # Add to cache (LRU eviction if full)
    if len(_sentence_split_cache) >= _SENTENCE_CACHE_MAX_SIZE:
        # Remove oldest entry (first in OrderedDict)
        _sentence_split_cache.popitem(last=False)

    _sentence_split_cache[cache_key] = sents
    return sents


def _pack_sentences_to_token_cap(text: str, max_tokens: int, sentence_split_regex: str = r"(?<=[.?!])\s+") -> List[str]:
    # Use cached sentence splitting
    sents = _split_sentences_cached(text, sentence_split_regex)
    if not sents:
        return []
    chunks, buf, t = [], [], 0
    for s in sents:
        ts = _approx_token_len(s)
        if not buf:
            buf, t = [s], ts
            if ts > max_tokens:
                chunks.append(" ".join(buf))
                buf, t = [], 0
            continue
        if t + ts <= max_tokens:
            buf.append(s)
            t += ts
        else:
            chunks.append(" ".join(buf))
            buf, t = [s], ts
            if ts > max_tokens:
                chunks.append(" ".join(buf))
                buf, t = [], 0
    if buf:
        chunks.append(" ".join(buf))
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
    # MEMORY OPTIMIZATION: Use smaller default batch size and process in chunks
    # Cap batch size at 128 for memory efficiency (reduced from 256)
    default_batch = min(EMBED_BATCH, 128)
    batch_size = min(kwargs.get("batch_size", default_batch), 128)

    # Process in smaller chunks to reduce peak memory usage
    all_embeddings = []
    chunk_size = batch_size

    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]
        chunk_embeddings = model.embed(list(chunk), batch_size=min(len(chunk), batch_size))
        # Convert to list immediately and clear chunk
        for v in chunk_embeddings:
            all_embeddings.append(list(v))
        del chunk, chunk_embeddings

        # Force GC every few chunks
        if i > 0 and i % (chunk_size * 4) == 0:
            gc.collect()

    return all_embeddings


# --- Semantic chunking wrapper ----------------------------------------------


class SemanticSplitterCache:
    """Cache for semantic splitter instances with isolated state.

    This class encapsulates the caching logic for SemanticChunker instances,
    allowing for easy test isolation by creating fresh instances in tests.
    """

    def __init__(self):
        """Initialize empty cache."""
        self._cache: Dict[str, SemanticChunker] = {}

    def get_splitter(self, sim_percentile: float = 95.0, buffer_size: int = 1) -> SemanticChunker:
        """Get or create a cached semantic chunker instance.

        Args:
            sim_percentile: Similarity percentile threshold
            buffer_size: Buffer size for chunking

        Returns:
            Cached or newly created SemanticChunker instance
        """
        cache_key = f"{sim_percentile}_{buffer_size}"
        if cache_key not in self._cache:
            self._cache[cache_key] = SemanticChunker(
                embedding_function=semantic_embed,
                buffer_size=buffer_size,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=sim_percentile,
            )
        return self._cache[cache_key]

    def clear(self):
        """Clear all cached splitters."""
        self._cache.clear()

    def size(self) -> int:
        """Get number of cached splitters.

        Returns:
            Number of cached SemanticChunker instances
        """
        return len(self._cache)


# Module-level cache instance (can be replaced in tests for isolation)
_splitter_cache = SemanticSplitterCache()


def _get_semantic_splitter(sim_percentile: float = 95.0, buffer_size: int = 1) -> SemanticChunker:
    """Get or create a cached semantic chunker instance.

    Uses module-level cache instance. For testing, replace _splitter_cache
    with a fresh SemanticSplitterCache() instance.

    Args:
        sim_percentile: Similarity percentile threshold
        buffer_size: Buffer size for chunking

    Returns:
        Cached or newly created SemanticChunker instance
    """
    return _splitter_cache.get_splitter(sim_percentile, buffer_size)


def semantic_chunks(
    text: str,
    sim_percentile: float = 95.0,
    buffer_size: int = 1,
    max_tokens: int = 1400,
    overlap_sentences: int = 2,
    max_depth: int = 3,
) -> List[str]:
    # Early exit: if text fits in one chunk, return immediately
    if _approx_token_len(text) <= max_tokens:
        return _apply_sentence_overlap([text], overlap_sentences=overlap_sentences)

    def _get_adaptive_threshold(base_percentile: float, depth: int) -> float:
        """Calculate adaptive threshold based on recursion depth.

        Lower threshold at deeper levels to find more breakpoints in smaller chunks
        with less semantic variation.

        Args:
            base_percentile: Base threshold (default: 95.0)
            depth: Recursion depth (0 = initial, 1+ = recursive)

        Returns:
            Adjusted threshold percentile
        """
        if depth == 0:
            return base_percentile  # 95.0 - strict for initial chunking
        elif depth == 1:
            return max(80.0, base_percentile - 5.0)  # 90.0 - slightly more lenient
        elif depth == 2:
            return max(75.0, base_percentile - 10.0)  # 85.0 - more lenient
        else:
            return max(70.0, base_percentile - 15.0)  # 80.0 - most lenient (safety)

    def _recur(t: str, depth: int) -> List[str]:
        # Quick check before expensive embedding
        if _approx_token_len(t) <= max_tokens:
            return [t]

        # Use adaptive threshold based on depth
        adaptive_percentile = _get_adaptive_threshold(sim_percentile, depth)
        splitter = _get_semantic_splitter(adaptive_percentile, buffer_size)

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

    # Start recursion at depth 0
    base = _recur(text, 0)

    # Enhanced overlap with sliding window approach for better context preservation
    return _apply_sentence_overlap(base, overlap_sentences=overlap_sentences)


# Cache compiled regex for sentence splitting (performance optimization)
_sentence_split_re = re.compile(r"(?<=[.!?])\s+")


def _enrich_chunk_with_context(chunks: List[str], window_size: int = 2) -> List[str]:
    """Add sliding window context to chunks for better retrieval."""
    if len(chunks) <= 1 or window_size <= 0:
        return chunks

    # Pre-allocate list for better performance
    enriched = [None] * len(chunks)
    lookback_limit = min(4, window_size)  # Pre-compute limits (optimize: calculate once)
    lookahead_limit = min(4, window_size)

    for i, chunk in enumerate(chunks):
        context_parts = []

        # Add context from previous chunks (memory optimized)
        if i > 0 and window_size > 0:
            context_start = max(0, i - window_size)
            # Optimize: calculate range bounds once
            start_idx = max(context_start, i - lookback_limit)
            for j in range(start_idx, i):
                prev_chunk = chunks[j]
                sentences = _split_sentences_cached(prev_chunk)
                # Optimize: extend with slice instead of individual appends
                if len(sentences) >= 2:
                    context_parts.extend(sentences[-2:])  # Last 2 sentences
                elif sentences:
                    context_parts.extend(sentences)

        # Add context from next chunks (memory optimized)
        if i < len(chunks) - 1 and window_size > 0:
            context_end = min(len(chunks), i + window_size + 1)
            end_idx = min(context_end, i + lookahead_limit + 1)
            for j in range(i + 1, end_idx):
                next_chunk = chunks[j]
                sentences = _split_sentences_cached(next_chunk)
                # Optimize: extend with slice
                if len(sentences) >= 2:
                    context_parts.extend(sentences[:2])  # First 2 sentences
                elif sentences:
                    context_parts.extend(sentences)

        # Combine context with current chunk
        if context_parts:
            # Optimize: use join once for all context, then combine with chunk
            context_text = " ".join(context_parts)
            enriched[i] = f"{context_text} {chunk}".strip()
        else:
            enriched[i] = chunk.strip()

    return enriched


# --- Ingest: load → chunk → embed → Chroma ----------------------------------
def run_ingest(
    *,
    target_tokens: int = 900,
    max_tokens: int = 1400,
    overlap_sentences: int = 2,
    buffer_size: int = 1,
    sim_percentile: float = 95.0,
    max_depth: int = 3,
) -> Dict[str, Any]:
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

    # MEMORY OPTIMIZATION: Process files one at a time instead of loading all at once
    # This significantly reduces memory usage by not holding all documents in memory simultaneously
    client = get_chromadb_client()
    coll = client.get_or_create_collection(name=VECTOR_COLLECTION)
    embedder = get_embedder()

    ids_buf: List[str] = []
    docs_buf: List[str] = []
    metas_buf: List[Dict[str, Any]] = []
    added = 0
    token_lens: List[int] = []
    skipped_embeddings = 0  # Track how many embeddings we skipped
    total_docs_processed = 0  # Track total documents processed

    def _flush():
        # Note: ids_buf, docs_buf, metas_buf are mutated (not assigned), so nonlocal is needed
        # but flake8 F824 complains. We suppress it since mutation requires nonlocal.
        nonlocal added, skipped_embeddings  # noqa: F824
        # ids_buf, docs_buf, metas_buf are mutated via .clear() and .append()
        nonlocal ids_buf, docs_buf, metas_buf  # noqa: F824
        if not ids_buf:
            return

        # Check which chunks already exist and compare content hashes
        # OPTIMIZATION: Single batch query instead of individual queries per chunk
        # This reduces network latency from O(n) to O(1) for n chunks
        existing_chunks = {}
        try:
            # Batch get existing chunks - only load metadatas and embeddings (not documents)
            # We don't need documents since we only compare content_hash and reuse embeddings
            # This is already optimized: single batch query minimizes network round-trips
            existing = coll.get(ids=ids_buf, include=["metadatas", "embeddings"])
            # Map results by ID since ChromaDB may return in different order
            for i, chunk_id in enumerate(existing.get("ids", [])):
                existing_chunks[chunk_id] = {
                    "content_hash": (
                        existing["metadatas"][i].get("content_hash")
                        if existing.get("metadatas") and i < len(existing["metadatas"])
                        else None
                    ),
                    "embedding": (
                        existing["embeddings"][i]
                        if existing.get("embeddings") and i < len(existing["embeddings"])
                        else None
                    ),
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
        # MEMORY OPTIMIZATION: Process embeddings in smaller batches to reduce peak memory
        if need_embedding_docs:
            # Use smaller batch size for memory-constrained environments
            # Process in chunks to avoid loading all embeddings at once
            embed_batch_size = min(EMBED_BATCH, 128)  # Cap at 128 for memory efficiency
            new_embs = []

            # Process embeddings in smaller chunks
            for i in range(0, len(need_embedding_docs), embed_batch_size):
                chunk_docs = need_embedding_docs[i : i + embed_batch_size]
                emb_iter = embedder.passage_embed(chunk_docs, batch_size=embed_batch_size)

                # Convert to list and clear immediately
                chunk_embs = []
                for e in emb_iter:
                    if hasattr(e, "tolist"):
                        chunk_embs.append(e.tolist())
                    elif isinstance(e, (list, tuple)):
                        chunk_embs.append(list(e))
                    else:
                        chunk_embs.append(list(e))

                new_embs.extend(chunk_embs)

                # Clear chunk data immediately
                del chunk_docs, emb_iter, chunk_embs

                # Force GC every few chunks to prevent memory buildup
                if i > 0 and i % (embed_batch_size * 3) == 0:
                    gc.collect()
        else:
            new_embs = []

        # Build complete embeddings list (new + existing)
        # Pre-allocate list for better performance
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
                    # Optimize: convert once
                    if hasattr(fallback_emb, "tolist"):
                        all_embs[i] = fallback_emb.tolist()
                    elif isinstance(fallback_emb, (list, tuple)):
                        all_embs[i] = list(fallback_emb)
                    else:
                        all_embs[i] = list(fallback_emb)
                except Exception:
                    all_embs[i] = [0.0] * 384

        skipped_embeddings += len(skip_embedding_indices)

        try:
            coll.upsert(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=all_embs)
        except Exception:
            try:
                coll.add(ids=ids_buf, documents=docs_buf, metadatas=metas_buf, embeddings=all_embs)
            except Exception:
                ids_buf.clear()
                docs_buf.clear()
                metas_buf.clear()
                all_embs.clear()
                return

        added += len(ids_buf)

        # Aggressively clear all buffers and embeddings to free memory
        ids_buf.clear()
        docs_buf.clear()
        metas_buf.clear()
        all_embs.clear()

        # Force garbage collection after flush to reclaim memory immediately
        gc.collect()

    # Check existing chunk count
    existing_count = coll.count()

    # MEMORY OPTIMIZATION: Process files one at a time instead of loading all at once
    # Get list of file paths first (lightweight, just paths)
    ext_patterns = {".txt", ".md", ".pdf", ".csv"}
    data_path = os.path.join(DATA_DIR, "**", "*")
    file_paths = sorted(
        [
            p
            for p in glob.glob(data_path, recursive=True)
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in ext_patterns
        ]
    )

    # Filter: Skip CSV files (replaced by LLM-Quant_Expanded_RAG_with_context.md)
    # All other files (.txt, .md, .pdf) are processed normally
    file_paths = [p for p in file_paths if not p.lower().endswith(".csv")]

    total_files = len(file_paths)

    if total_files == 0:
        print(f"[WARN] No documents found in {DATA_DIR}")
        return {"added": 0, "n_chunks": 0, "avg_tokens": 0, "num_input_docs": 0, "elapsed_sec": 0}

    # Batch check document sources if SKIP_EXISTING is enabled (check all files at once for efficiency)
    processed_sources = set()
    if SKIP_EXISTING and existing_count > 0 and total_files > 0:
        try:
            # Efficient approach: Get all unique sources from ChromaDB once, then check files
            # This is more efficient than querying per file

            # Get all chunks' metadata to extract unique file paths
            # Use a reasonable limit to avoid loading too much data
            # For large collections, we'll sample and check
            max_check = min(10000, existing_count)  # Check up to 10k chunks
            all_chunks = coll.get(limit=max_check, include=["metadatas"])

            # Extract all unique base file paths from sources
            seen_file_paths = set()
            if all_chunks.get("metadatas"):
                for meta in all_chunks["metadatas"]:
                    if isinstance(meta, dict) and "source" in meta:
                        source = meta["source"]
                        # Extract base file path from source (remove chapter/page/feature/full_document markers)
                        if "#chapter=" in source:
                            base_path = source.split("#chapter=")[0]
                        elif "#page=" in source:
                            base_path = source.split("#page=")[0]
                        elif "#feature=" in source:
                            base_path = source.split("#feature=")[0]
                        elif "#full_document" in source:
                            base_path = source.split("#full_document")[0]
                        else:
                            base_path = source
                        seen_file_paths.add(base_path)

            # Check each file path against seen paths
            for file_path in file_paths:
                if file_path in seen_file_paths:
                    processed_sources.add(file_path)

            # If we didn't check all chunks (collection is larger than max_check),
            # also try exact chunk ID matching for files not found
            if existing_count > max_check:
                for file_path in file_paths:
                    if file_path not in processed_sources:
                        # Try exact chunk ID patterns as fallback
                        try:
                            # Check for feature file (markdown) or PDF files with special chunk ID patterns
                            base = os.path.basename(file_path)
                            if (
                                "LLM-Quant_Expanded_RAG_with_context" in base
                                or "llm-quant_expanded_rag_with_context" in base.lower()
                            ):
                                # Feature markdown file: check for first feature chunk
                                chunk_id = f"{file_path}#feature=first::chunk_0"
                            elif file_path.lower().endswith(".pdf"):
                                chunk_id = f"{file_path}#chapter=1::chunk_0"
                            else:
                                chunk_id = f"{file_path}::chunk_0"

                            result = coll.get(ids=[chunk_id], include=["metadatas"])
                            if result.get("ids") and len(result["ids"]) > 0:
                                processed_sources.add(file_path)
                        except Exception:
                            pass

        except Exception:
            processed_sources = None

    # Process files one at a time to minimize memory usage
    file_iterator = enumerate(file_paths, 1)
    if TQDM_AVAILABLE:
        file_iterator = tqdm(enumerate(file_paths, 1), total=total_files, desc="Processing files", unit="file")

    for file_idx, file_path in file_iterator:
        # Update progress description
        if TQDM_AVAILABLE and hasattr(file_iterator, "set_description"):
            file_name = os.path.basename(file_path)[:50]
            file_iterator.set_description(f"Processing: {file_name}")

        # Check if file should be skipped (SKIP_EXISTING)
        if SKIP_EXISTING and existing_count > 0:
            if processed_sources is not None:
                # Check if base path is in processed sources
                if file_path in processed_sources:
                    print(f"[SKIP] {file_path} already processed, skipping...")
                    total_docs_processed += 1
                    continue

        # Load and process this file only (memory efficient)
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".txt":
                file_docs = _load_txt_md(file_path)
            elif ext == ".md":
                # Check if this is the specific feature explanation markdown file
                base = os.path.basename(file_path)
                base_lower = base.lower()
                if "LLM-Quant_Expanded_RAG_with_context" in base or "llm-quant_expanded_rag_with_context" in base_lower:
                    # Use specialized markdown loader for feature file
                    # This extracts individual features
                    file_docs = _load_md_feature_file(file_path)
                    # Also load the entire file as a single document for context retrieval
                    full_doc = _load_full_md_file(file_path)
                    file_docs.extend(full_doc)
                else:
                    # Use generic markdown loader for other markdown files
                    file_docs = _load_txt_md(file_path)
            elif ext == ".pdf":
                file_docs = _load_pdf(file_path)
            elif ext == ".csv":
                # CSV files are no longer processed (replaced by markdown file)
                continue
            else:
                continue
        except Exception as e:
            print(f"[WARN] Failed to load {file_path}: {e}")
            continue

        # Process each document from this file
        for src, txt in file_docs:
            total_docs_processed += 1

            # Check if this is a feature file chunk or full document (already chunked, skip semantic chunking)
            is_feature_chunk = "#feature=" in src or "#stats" in src
            is_full_document = "#full_document" in src

            if is_feature_chunk or is_full_document:
                # Feature file chunks and full documents are already complete - use as-is (no semantic chunking)
                chs = [txt]  # Single chunk, already formatted
                # Skip context enrichment for feature chunks and full documents (not needed for structured data)
            else:
                # Regular documents: apply semantic chunking
                chs = semantic_chunks(
                    txt,
                    sim_percentile=sim_percentile,
                    buffer_size=buffer_size,
                    max_tokens=max_tokens,
                    overlap_sentences=overlap_sentences,
                    max_depth=max_depth,
                )
                # Enhanced chunking: add contextual information (with memory limit)
                max_window = min(2, len(chs) // 2) if len(chs) > 4 else 1  # Limit context window for memory
                chs = _enrich_chunk_with_context(chs, window_size=max_window)

            # Process chunks in batches - minimal metadata for performance
            # Optimize: pre-compute total_chunks and base_id pattern to avoid repeated string operations
            total_chunks = len(chs)
            base_id_prefix = f"{src}::chunk_"  # Cache base ID pattern

            for idx, ch in enumerate(chs):
                # Optimize: use string concatenation for chunk IDs (faster than f-string for simple cases)
                # Note: f-strings are actually faster in Python 3.6+, but concatenation is fine here
                cid = base_id_prefix + str(idx)

                # Compute content hash for duplicate detection
                # Optimize: encode once and reuse if needed
                ch_bytes = ch.encode("utf-8")
                content_hash = hashlib.md5(ch_bytes).hexdigest()

                # Minimal metadata: only essential fields for retrieval and duplicate detection
                # Optimize: reuse dict structure pattern (though Python optimizes this internally)
                meta = {
                    "source": src,  # Required for source attribution
                    "content_hash": content_hash,  # Required for duplicate detection
                    "chunk_index": idx,  # Useful for ordering within document
                    "total_chunks": total_chunks,  # Useful context
                }
                ids_buf.append(cid)
                docs_buf.append(ch)
                metas_buf.append(meta)
                token_lens.append(_approx_token_len(ch))
                if len(ids_buf) >= UPSERT_BATCH:
                    _flush()

            # Clear intermediate variables to free memory after processing document
            del chs, txt

            # Aggressive memory management: flush more frequently and clear memory
            # Flush buffer more frequently to prevent memory buildup
            if len(ids_buf) >= UPSERT_BATCH:
                _flush()
                gc.collect()  # Force GC after flush

            # More aggressive garbage collection: run more frequently for memory-constrained environments
            # Run GC every 5 documents (reduced from 10) or when buffer is large
            if len(ids_buf) > UPSERT_BATCH or total_docs_processed % 5 == 0:
                gc.collect()

        # Clear file_docs after processing entire file to free memory
        del file_docs
        gc.collect()  # Force GC after processing each file

    _flush()

    # Upload ChromaDB files to GCS after ingestion
    global _gcs_synced, _gcs_uploaded_after_ingest
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    if GCS_AVAILABLE and gcs_bucket:
        try:
            _upload_chromadb_to_gcs(gcs_bucket, CHROMADB_SERVER_DATA_PATH)
            _gcs_synced = True
            _gcs_uploaded_after_ingest = True  # Mark that we uploaded after ingestion
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

    # DVC versioning: Create version snapshot after successful ingestion
    # This is non-critical - ingestion succeeds even if DVC versioning fails
    try:
        import subprocess

        chroma_path = CHROMADB_SERVER_DATA_PATH
        # Check if DVC is available and data directory exists
        if os.path.exists(chroma_path) and os.path.isdir(chroma_path):
            # Check if DVC is initialized (look for .dvc directory in current working directory or project root)
            # Try multiple possible locations for .dvc directory
            cwd = os.getcwd()
            possible_dvc_dirs = [
                os.path.join(cwd, ".dvc"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), ".dvc"),  # Project root from src/rag/rag.py
            ]
            dvc_initialized = any(os.path.exists(d) for d in possible_dvc_dirs)

            if dvc_initialized:
                # Add ChromaDB data to DVC tracking (updates .dvc file if it exists, creates if not)
                # Note: dvc add requires relative path from DVC root, so we use the absolute path
                # Use --no-commit to keep files in place (don't move to .dvc/cache/)
                # This ensures ChromaDB server and GCS sync continue to work with original file locations
                result = subprocess.run(
                    ["dvc", "add", "--no-commit", chroma_path],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
                if result.returncode == 0:
                    print("[INFO] ChromaDB data added to DVC tracking")

                    # Find the .dvc file created by dvc add
                    # DVC creates the file based on the path provided:
                    # - If absolute path like /chroma, creates /chroma.dvc at root
                    # - If relative path, creates at DVC root (where .dvc/config is)
                    dvc_file_path = None
                    possible_dvc_files = [
                        "/chroma.dvc",  # Absolute path creates file at root
                        os.path.join(cwd, "chroma.dvc"),  # Current working directory
                        os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma.dvc"),  # Project root
                        os.path.join("/workspace", "chroma.dvc"),  # Workspace directory
                    ]
                    for path in possible_dvc_files:
                        if os.path.exists(path):
                            dvc_file_path = path
                            break

                    # Upload .dvc file to GCS (works in Docker containers)
                    if dvc_file_path and GCS_AVAILABLE and gcs_bucket:
                        try:
                            from datetime import datetime

                            client = _get_gcs_client()
                            bucket = client.bucket(gcs_bucket)

                            # Upload with timestamp for versioning
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            timestamped_path = f"dvc-metadata/chroma_{timestamp}.dvc"
                            timestamped_blob = bucket.blob(timestamped_path)
                            timestamped_blob.upload_from_filename(dvc_file_path)

                            # Also upload as "latest" for easy access
                            latest_path = "dvc-metadata/chroma_latest.dvc"
                            latest_blob = bucket.blob(latest_path)
                            latest_blob.upload_from_filename(dvc_file_path)

                            print(f"[INFO] .dvc file uploaded to GCS: {timestamped_path} and {latest_path}")
                        except Exception as e:
                            print(f"[WARN] Failed to upload .dvc file to GCS (non-critical): {e}")
                    else:
                        print("[WARN] chroma.dvc file not found after dvc add")

                    # Note: dvc push is skipped - data remains only in operational chromadb/ storage
                    # The .dvc file is uploaded to GCS for version tracking (git commit is manual)
                else:
                    print(f"[WARN] DVC add failed (non-critical): {result.stderr}")
    except Exception as e:
        # Don't fail ingestion if DVC versioning fails
        print(f"[WARN] DVC versioning failed (non-critical): {e}")

    chunk_stats = {
        "chunker": "semantic",
        "n_chunks": added,
        "avg_tokens": round(sum(token_lens) / len(token_lens), 1) if token_lens else 0,
        "min_tokens": min(token_lens) if token_lens else 0,
        "max_tokens": max(token_lens) if token_lens else 0,
        "target_tokens": target_tokens,
        "max_tokens_cap": max_tokens,
        "overlap_sentences": overlap_sentences,
        "buffer_size": buffer_size,
        "sim_percentile": sim_percentile,
        "max_depth": max_depth,
    }
    summary = {
        **chunk_stats,
        "collection": VECTOR_COLLECTION,
        "embedding_model": EMBEDDING_MODEL,
        "num_input_docs": total_docs_processed,
        "elapsed_sec": round(time.time() - t0, 2),
    }

    with open(os.path.join(ARTIFACTS_DIR, "ingest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(ARTIFACTS_DIR, "chunk_stats.json"), "w", encoding="utf-8") as f:
        json.dump(chunk_stats, f, indent=2)

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
        self.client = None
        self.collection = None
        self._connection_error = None
        try:
            self.client = get_chromadb_client()
            # get_or_create_collection may raise if ChromaDB server is not available
            # Catch all exceptions to allow server to start in degraded mode
            self.collection = self.client.get_or_create_collection(name=VECTOR_COLLECTION)
        except BaseException as e:
            # Store connection error for graceful degradation
            # Server can start even if ChromaDB isn't available
            # Catch BaseException to handle all exception types (including SystemExit, KeyboardInterrupt)
            # but re-raise SystemExit and KeyboardInterrupt to allow proper shutdown
            if isinstance(e, (SystemExit, KeyboardInterrupt)):
                raise
            self.client = None
            self.collection = None
            self._connection_error = e
            # Log the error but don't crash
            print(f"[WARN] ChromaDB connection failed: {e}")
            print("[WARN] Server will start in degraded mode (ChromaDB unavailable)")
        # Using FastEmbed directly (LangChain removed)
        self.mode = "chroma-dist"
        # Add query cache
        self._query_cache = {} if ENABLE_CACHE else None

    def stats(self):
        if self._connection_error is not None:
            raise self._connection_error
        if self.collection is None:
            raise Exception("ChromaDB not connected")
        cnt = self.collection.count()
        meta = getattr(self.collection, "metadata", {}) or {}
        return {
            "collection": VECTOR_COLLECTION,
            "emb_model": EMBEDDING_MODEL,
            "retriever_mode": self.mode,
            "metric": meta.get("hnsw:space", "cosine"),
            "count": cnt,
            "cache_enabled": ENABLE_CACHE,
        }

    def query(self, q: str, k: int = 4):
        if not isinstance(q, str) or not q.strip():
            return []

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

        # Check if ChromaDB is connected
        if self._connection_error is not None or self.collection is None:
            return []

        # Pass as list containing the numpy array (one query, one embedding)
        try:
            res = self.collection.query(
                query_embeddings=[q_vec], n_results=k, include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            # If query fails, return empty results
            print(f"[WARN] Query failed: {e}")
            return []
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
            out.append(
                {
                    "rank": i,
                    "id": doc_id,
                    "text": text,
                    "metadata": md if isinstance(md, dict) else {},
                    "distance": distance,
                }
            )

        # Cache result
        if self._query_cache is not None and len(self._query_cache) < CACHE_SIZE:
            self._query_cache[cache_key] = out

        return out


# --- Retriever lazy initialization (module-level for testability) -----------
_retriever_instance = None


def get_retriever():
    """Get or create Retriever instance (lazy initialization).

    This is a module-level function to allow easy patching in tests.
    The Retriever is only created when first needed, allowing the server
    to start even if ChromaDB isn't available.

    Returns:
        Retriever instance (singleton)
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance


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
            retr = get_retriever()
            stats = retr.stats()
            return {"status": "ok", "service": "rag-api", "chromadb": "connected", **stats}
        except Exception as e:
            return {"status": "degraded", "service": "rag-api", "chromadb": "error", "error": str(e)}

    @app.post("/query")
    def query(req: QueryReq):
        """Main query endpoint with full metadata.

        Args:
            req: Query request with query string and result count

        Returns:
            JSON with query, results (full metadata), and result count
        """
        try:
            retr = get_retriever()
            results = retr.query(req.q, req.k)
            return {"query": req.q, "results": results, "found": len(results) > 0, "count": len(results)}
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": str(e), "query": req.q})

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
            retr = get_retriever()
            results = retr.query(req.q, req.k)

            if not results:
                return {
                    "query": req.q,
                    "answer": "No relevant information found in the knowledge base.",
                    "found": False,
                    "source_count": 0,
                }

            if req.format == "text":
                # Concatenate top results for LLM consumption (limit each to 500 chars for brevity)
                texts = [r.get("text", "") for r in results[:3]]  # Top 3 results
                answer = "\n\n".join(
                    [
                        f"Information {i+1}: {text[:500]}"  # Limit each to 500 chars
                        for i, text in enumerate(texts)
                        if text
                    ]
                )

                return {"query": req.q, "answer": answer, "found": True, "source_count": len(results)}
            else:
                # Detailed format - return full results
                return {"query": req.q, "results": results, "found": True, "count": len(results)}

        except Exception as e:
            return {
                "query": req.q,
                "answer": f"Error accessing knowledge base: {str(e)}",
                "found": False,
                "error": str(e),
            }

    return app


def serve():
    """Start the FastAPI server with uvicorn.

    Starts a production-ready ASGI server on configured API_HOST and API_PORT.
    """
    import uvicorn

    try:
        app = make_app()
        print(f"[INFO] Starting server on {API_HOST}:{API_PORT}")
        uvicorn.run(app, host=API_HOST, port=API_PORT, reload=False)
    except Exception as e:
        print(f"[ERROR] Failed to start server: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise


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
    p.add_argument("--serve", action="store_true", help="Run FastAPI server")
    p.add_argument("--target-tokens", type=int, default=900)
    p.add_argument("--max-tokens", type=int, default=1400)
    p.add_argument("--overlap-sentences", type=int, default=2)
    p.add_argument("--buffer-size", type=int, default=1)
    p.add_argument("--sim-percentile", type=float, default=95.0)
    p.add_argument("--max-depth", type=int, default=3, help="Max recursion depth for semantic re-splitting")
    args = p.parse_args()

    if not (args.ingest or args.serve):
        args.ingest = True

    try:
        if args.ingest:
            stats = run_ingest(
                target_tokens=args.target_tokens,
                max_tokens=args.max_tokens,
                overlap_sentences=args.overlap_sentences,
                buffer_size=args.buffer_size,
                sim_percentile=args.sim_percentile,
                max_depth=args.max_depth,
            )
            print(json.dumps({"ingest_done": True, **stats}, indent=2))
            if args.serve:
                time.sleep(2)
        if args.serve:
            serve()
    except KeyboardInterrupt:
        print("\n[INFO] Server shutdown requested")
        raise
    except Exception as e:
        print(f"[ERROR] Fatal error in main(): {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        print("[INFO] Starting RAG application...")
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Unhandled exception in main: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
