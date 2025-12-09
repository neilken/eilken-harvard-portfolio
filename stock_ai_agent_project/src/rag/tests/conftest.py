"""Pytest fixtures for RAG tests."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any
import numpy as np

# Centralize path setup - add src/rag to Python path for all tests
# This eliminates the need for sys.path.insert in every test file
_rag_src_path = Path(__file__).parent.parent.resolve()
if str(_rag_src_path) not in sys.path:
    sys.path.insert(0, str(_rag_src_path))


def pytest_configure(config):
    """Configure pytest with centralized path setup."""
    # Ensure rag module is importable
    try:
        import rag
    except ImportError:
        # If rag can't be imported, tests will use pytest.importorskip
        pass


# Patch print and traceback at module import time (before any tests run)
import builtins
import traceback

_original_print = builtins.print
_original_print_exc = traceback.print_exc


def _filtered_print(*args, **kwargs):
    """Filter out GCS error messages from print output."""
    if args and len(args) > 0 and isinstance(args[0], str):
        msg = args[0]
        if any(keyword in msg for keyword in ["[ERROR] Failed to upload ChromaDB", "Failed to initialize GCS client"]):
            return  # Suppress this message
    _original_print(*args, **kwargs)


def _filtered_print_exc(*args, **kwargs):
    """Filter out GCS-related tracebacks."""
    import sys

    exc_type, exc_value, exc_tb = sys.exc_info()
    if exc_value:
        exc_str = str(exc_value)
        if any(
            keyword in exc_str for keyword in ["GCS", "google.auth", "DefaultCredentialsError", "File  was not found"]
        ):
            return  # Suppress GCS-related tracebacks
    _original_print_exc(*args, **kwargs)


# Apply patches immediately when conftest is imported
builtins.print = _filtered_print
traceback.print_exc = _filtered_print_exc


@pytest.fixture(scope="function")  # Explicit scope for clarity
def mock_chromadb_client():
    """Mock ChromaDB HTTP client."""
    client = Mock()
    collection = Mock()

    # Mock collection methods
    collection.count.return_value = 100
    collection.metadata = {"hnsw:space": "cosine"}
    collection.query.return_value = {
        "ids": [["doc1", "doc2"]],
        "documents": [["Sample document text 1", "Sample document text 2"]],
        "metadatas": [[{"source": "test.pdf", "page": 1}, {"source": "test.pdf", "page": 2}]],
        "distances": [[0.1, 0.2]],
    }
    collection.get_or_create_collection.return_value = collection
    client.get_or_create_collection.return_value = collection

    return client, collection


@pytest.fixture(scope="function")  # Keep function scope for test isolation
def mock_embedder():
    """Mock FastEmbed embedder with memory-efficient small embeddings."""
    embedder = Mock()

    # Use smaller embedding dimension (128 instead of 384) to reduce memory
    # This is 3x less memory per embedding while still testing functionality
    EMBED_DIM = 128

    # Mock embedding generation - use simple deterministic values instead of random
    def mock_embed(texts, **kwargs):
        # Return lightweight mock embeddings (128 dim for memory efficiency)
        embeddings = []
        for i, text in enumerate(texts):
            # Use hash-based deterministic value, but keep it small
            # Just use a simple list of small floats instead of numpy arrays
            seed = hash(text) % 1000
            emb = [float((seed + j) % 100) / 100.0 for j in range(EMBED_DIM)]
            embeddings.append(emb)
        return iter(embeddings)

    def mock_query_embed(text):
        # Single query embedding - lightweight
        seed = hash(text) % 1000
        emb = [float((seed + j) % 100) / 100.0 for j in range(EMBED_DIM)]
        return iter([emb])

    def mock_passage_embed(texts, **kwargs):
        # Alias for passage_embed
        return mock_embed(texts, **kwargs)

    embedder.embed = mock_embed
    embedder.query_embed = mock_query_embed
    embedder.passage_embed = mock_passage_embed

    return embedder


@pytest.fixture
def sample_text():
    """Sample text for testing - kept small for memory efficiency."""
    return "This is a sample document for testing. It contains multiple sentences. Each sentence has some content."


@pytest.fixture(autouse=True)
def mock_time_sleep(monkeypatch):
    """Mock time.sleep to speed up tests by removing waits."""
    import time

    monkeypatch.setattr(time, "sleep", lambda x: None)  # No-op sleep for speed


@pytest.fixture(autouse=True)
def clear_caches_after_test():
    """Automatically clear RAG caches after each test to prevent memory buildup."""
    yield
    # Clear caches after test
    try:
        import rag

        if hasattr(rag, "_splitter_cache"):
            rag._splitter_cache.clear()
        if hasattr(rag, "_embedding_cache"):
            rag._embedding_cache.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def sample_chunks():
    """Sample text chunks for testing."""
    return [
        "First chunk of text with some content.",
        "Second chunk with different content.",
        "Third chunk with more text.",
    ]


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        ("test1.pdf", "Document 1 content about finance and stocks."),
        ("test2.pdf", "Document 2 content about investment strategies."),
        ("test3.txt", "Document 3 plain text content."),
    ]


@pytest.fixture
def mock_fastapi_app():
    """Mock FastAPI app for testing."""
    # Use importorskip to handle missing fastapi gracefully
    TestClient = pytest.importorskip("fastapi.testclient").TestClient

    # Patch ChromaDB and GCS dependencies before importing
    with patch("rag.get_chromadb_client"), patch("rag._get_gcs_client"), patch("rag._start_chromadb_server"):
        from rag import make_app

        app = make_app()
        return TestClient(app)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def sample_query_results():
    """Sample query results from ChromaDB."""
    return [
        {
            "rank": 1,
            "id": "doc1",
            "text": "Return on Equity (ROE) measures profitability.",
            "metadata": {"source": "finance.pdf", "page": 42},
            "distance": 0.15,
        },
        {
            "rank": 2,
            "id": "doc2",
            "text": "ROE is calculated as Net Income divided by Equity.",
            "metadata": {"source": "accounting.pdf", "page": 15},
            "distance": 0.28,
        },
    ]


@pytest.fixture
def mock_gcs_client():
    """Mock GCS storage client."""
    mock_client = Mock()
    mock_bucket = Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.exists.return_value = True
    mock_bucket.list_blobs.return_value = []
    return mock_client, mock_bucket


@pytest.fixture
def mock_gcs_blob():
    """Mock GCS blob for testing upload/download."""
    blob = Mock()
    blob.name = "chromadb/test_file.txt"
    blob.size = 100
    blob.md5_hash = "abc123"
    blob.exists.return_value = True
    blob.download_to_filename = Mock()
    blob.upload_from_filename = Mock()
    return blob


@pytest.fixture
def mock_chromadb_server_process():
    """Mock ChromaDB server subprocess."""
    process = Mock()
    process.poll.return_value = None  # Still running
    process.terminate = Mock()
    process.wait = Mock(return_value=0)
    return process


@pytest.fixture
def sample_ingest_metadata():
    """Sample ingestion metadata for testing."""
    return {
        "data_versioning": "DVC (Data Version Control)",
        "ingestion_stats": {
            "n_chunks": 100,
            "avg_tokens": 150,
            "num_input_docs": 5,
        },
        "collection": "stocks_rag_v1",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "note": "Use 'dvc add' to track this data, then 'dvc push' to store in remote",
    }


@pytest.fixture(scope="class")
def rag_module():
    """Import rag module with proper error handling. Use class scope for efficiency."""
    rag = pytest.importorskip("rag")
    return rag


@pytest.fixture
def mock_ingestion_patches():
    """Composite fixture for common ingestion test patches.
    Reduces boilerplate in tests with many patches."""
    with (
        patch("rag.get_chromadb_client") as mock_client,
        patch("rag.get_embedder") as mock_embedder,
        patch("rag.load_all") as mock_load,
        patch("rag.semantic_chunks") as mock_chunks,
        patch("rag._upload_chromadb_to_gcs") as mock_upload,
        patch("rag._approx_token_len") as mock_token_len,
        patch("os.getenv") as mock_getenv,
        patch("time.time") as mock_time,
        patch("subprocess.check_output") as mock_subprocess,
    ):
        # Set common defaults
        mock_time.side_effect = [0, 10]  # Start and end time
        mock_subprocess.return_value = b"abc123def456"  # Mock git commit
        mock_upload.return_value = (0, 0, 0)  # Mock GCS upload
        mock_getenv.side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)
        mock_token_len.return_value = 50

        yield {
            "client": mock_client,
            "embedder": mock_embedder,
            "load": mock_load,
            "chunks": mock_chunks,
            "upload": mock_upload,
            "token_len": mock_token_len,
            "getenv": mock_getenv,
            "time": mock_time,
            "subprocess": mock_subprocess,
        }
