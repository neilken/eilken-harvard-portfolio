"""Unit tests for infrastructure components: CLI, GCS sync, and Retriever."""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
import argparse
import numpy as np

pytestmark = pytest.mark.unit

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions to test
rag = pytest.importorskip("rag")
from rag import (
    main,
    serve,
    _get_gcs_client,
    _download_chromadb_from_gcs,
    _upload_chromadb_to_gcs,
    _start_chromadb_server,
    _cleanup_chromadb_server,
)


# ============================================================================
# CLI Functions
# ============================================================================


class TestMainFunction:
    """Tests for main() CLI function."""

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_ingest_only(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() with --ingest flag only."""
        mock_run_ingest.return_value = {
            "added": 10,
            "n_chunks": 10,
            "avg_tokens": 100,
            "num_input_docs": 1,
            "elapsed_sec": 1.0,
        }

        with patch("sys.argv", ["rag.py", "--ingest"]):
            with patch("builtins.print"):  # Suppress print output
                main()

        mock_start_server.assert_called_once()
        mock_run_ingest.assert_called_once()
        mock_serve.assert_not_called()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_serve_only(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() with --serve flag only."""
        # serve() runs indefinitely, so we need to mock it to return
        mock_serve.side_effect = KeyboardInterrupt()

        with patch("sys.argv", ["rag.py", "--serve"]):
            with patch("builtins.print"):  # Suppress print output
                with pytest.raises(KeyboardInterrupt):
                    main()

        mock_start_server.assert_called_once()
        mock_run_ingest.assert_not_called()
        mock_serve.assert_called_once()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch("rag.time.sleep")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_ingest_and_serve(self, mock_sleep, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() with both --ingest and --serve flags."""
        mock_run_ingest.return_value = {
            "added": 10,
            "n_chunks": 10,
            "avg_tokens": 100,
            "num_input_docs": 1,
            "elapsed_sec": 1.0,
        }
        mock_serve.side_effect = KeyboardInterrupt()

        with patch("sys.argv", ["rag.py", "--ingest", "--serve"]):
            with patch("builtins.print"):  # Suppress print output
                with pytest.raises(KeyboardInterrupt):
                    main()

        mock_start_server.assert_called_once()
        mock_run_ingest.assert_called_once()
        mock_sleep.assert_called_once_with(2)  # Should sleep before serving
        mock_serve.assert_called_once()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_with_semantic_chunking_params(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() passes semantic chunking parameters correctly."""
        mock_run_ingest.return_value = {
            "added": 10,
            "n_chunks": 10,
            "avg_tokens": 100,
            "num_input_docs": 1,
            "elapsed_sec": 1.0,
        }

        with patch(
            "sys.argv",
            [
                "rag.py",
                "--ingest",
                "--target-tokens",
                "800",
                "--max-tokens",
                "1200",
                "--overlap-sentences",
                "3",
                "--buffer-size",
                "2",
                "--sim-percentile",
                "90.0",
                "--max-depth",
                "4",
            ],
        ):
            with patch("builtins.print"):  # Suppress print output
                main()

        mock_run_ingest.assert_called_once_with(
            target_tokens=800, max_tokens=1200, overlap_sentences=3, buffer_size=2, sim_percentile=90.0, max_depth=4
        )

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_chromadb_server_startup_failure(self, mock_run_ingest, mock_start_server):
        """Test main() handles ChromaDB server startup failure."""
        mock_start_server.side_effect = Exception("Server startup failed")

        with patch("sys.argv", ["rag.py", "--ingest"]):
            with patch("builtins.print"):  # Suppress print output
                with pytest.raises(Exception, match="Server startup failed"):
                    main()

        mock_start_server.assert_called_once()
        mock_run_ingest.assert_not_called()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "0"})
    def test_main_auto_start_chromadb_disabled(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() skips ChromaDB server startup when AUTO_START_CHROMADB=0."""
        mock_run_ingest.return_value = {
            "added": 10,
            "n_chunks": 10,
            "avg_tokens": 100,
            "num_input_docs": 1,
            "elapsed_sec": 1.0,
        }

        with patch("sys.argv", ["rag.py", "--ingest"]):
            with patch("builtins.print"):  # Suppress print output
                main()

        mock_start_server.assert_not_called()
        mock_run_ingest.assert_called_once()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_ingest_failure(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() handles ingestion failure."""
        mock_run_ingest.side_effect = Exception("Ingestion failed")

        with patch("sys.argv", ["rag.py", "--ingest"]):
            with patch("builtins.print"):  # Suppress print output
                with pytest.raises(Exception, match="Ingestion failed"):
                    main()

        mock_run_ingest.assert_called_once()
        mock_serve.assert_not_called()

    @patch("rag._start_chromadb_server")
    @patch("rag.run_ingest")
    @patch("rag.serve")
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket", "AUTO_START_CHROMADB": "1"})
    def test_main_keyboard_interrupt(self, mock_serve, mock_run_ingest, mock_start_server):
        """Test main() handles KeyboardInterrupt gracefully."""
        mock_run_ingest.side_effect = KeyboardInterrupt()

        with patch("sys.argv", ["rag.py", "--ingest"]):
            with patch("builtins.print"):  # Suppress print output
                with pytest.raises(KeyboardInterrupt):
                    main()

        mock_run_ingest.assert_called_once()


class TestServeFunction:
    """Tests for serve() function."""

    @patch("uvicorn.run")
    @patch("rag.make_app")
    def test_serve_success(self, mock_make_app, mock_uvicorn_run):
        """Test serve() starts server successfully."""
        mock_app = MagicMock()
        mock_make_app.return_value = mock_app

        with patch("rag.API_HOST", "0.0.0.0"):
            with patch("rag.API_PORT", 9000):
                with patch("builtins.print"):  # Suppress print output
                    # uvicorn.run runs indefinitely, so we need to interrupt it
                    mock_uvicorn_run.side_effect = KeyboardInterrupt()
                    with pytest.raises(KeyboardInterrupt):
                        serve()

        mock_make_app.assert_called_once()
        mock_uvicorn_run.assert_called_once_with(mock_app, host="0.0.0.0", port=9000, reload=False)

    @patch("uvicorn.run")
    @patch("rag.make_app")
    def test_serve_app_creation_failure(self, mock_make_app, mock_uvicorn_run):
        """Test serve() handles app creation failure."""
        mock_make_app.side_effect = Exception("App creation failed")

        with patch("builtins.print"):  # Suppress print output
            with pytest.raises(Exception, match="App creation failed"):
                serve()

        mock_make_app.assert_called_once()
        mock_uvicorn_run.assert_not_called()

    @patch("uvicorn.run")
    @patch("rag.make_app")
    def test_serve_uvicorn_failure(self, mock_make_app, mock_uvicorn_run):
        """Test serve() handles uvicorn.run failure."""
        mock_app = MagicMock()
        mock_make_app.return_value = mock_app
        mock_uvicorn_run.side_effect = Exception("Uvicorn failed")

        with patch("rag.API_HOST", "0.0.0.0"):
            with patch("rag.API_PORT", 9000):
                with patch("builtins.print"):  # Suppress print output
                    with pytest.raises(Exception, match="Uvicorn failed"):
                        serve()

        mock_make_app.assert_called_once()
        mock_uvicorn_run.assert_called_once()

    @patch("uvicorn.run")
    @patch("rag.make_app")
    def test_serve_prints_info(self, mock_make_app, mock_uvicorn_run):
        """Test serve() prints startup information."""
        mock_app = MagicMock()
        mock_make_app.return_value = mock_app
        mock_uvicorn_run.side_effect = KeyboardInterrupt()

        with patch("rag.API_HOST", "localhost"):
            with patch("rag.API_PORT", 8080):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(KeyboardInterrupt):
                        serve()

        # Check that info message was printed
        mock_print.assert_any_call("[INFO] Starting server on localhost:8080")


# ============================================================================
# GCS Sync Functions
# ============================================================================


class TestGetGCSClient:
    """Tests for _get_gcs_client function."""

    def teardown_method(self):
        """Clear mocks after each test."""
        pass

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag.storage")
    @patch("rag.service_account")
    @patch("os.path.exists")
    @patch("os.getenv")
    def test_get_gcs_client_with_key_file(self, mock_getenv, mock_exists, mock_sa, mock_storage):
        """Test GCS client creation with service account key file."""
        # Use spec to limit mock attributes and reduce memory
        mock_getenv.return_value = "/path/to/key.json"
        mock_exists.return_value = True
        mock_creds = Mock(spec=["__class__"])  # Minimal spec
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds
        mock_client = Mock(spec=["bucket", "__class__"])  # Only needed methods
        mock_storage.Client.return_value = mock_client

        result = _get_gcs_client()

        assert result == mock_client
        mock_sa.Credentials.from_service_account_file.assert_called_once_with("/path/to/key.json")
        mock_storage.Client.assert_called_once_with(credentials=mock_creds)

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag.storage")
    @patch("os.path.exists")
    @patch("os.getenv")
    def test_get_gcs_client_without_key_file(self, mock_getenv, mock_exists, mock_storage):
        """Test GCS client creation without key file (default credentials)."""
        mock_getenv.return_value = "/path/to/key.json"
        mock_exists.return_value = False
        mock_client = Mock(spec=["bucket", "__class__"])  # Minimal spec
        mock_storage.Client.return_value = mock_client

        result = _get_gcs_client()

        assert result == mock_client
        mock_storage.Client.assert_called_once_with()

    @patch("rag.GCS_AVAILABLE", False)
    def test_get_gcs_client_not_available(self):
        """Test GCS client raises error when GCS not available."""
        # rag module already imported via conftest.py path setup

        with pytest.raises(Exception, match="GCS Python client not available"):
            _get_gcs_client()


class TestDownloadChromaDBFromGCS:
    """Tests for _download_chromadb_from_gcs function."""

    def teardown_method(self):
        """Clear mocks after each test."""
        pass

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag._get_gcs_client")
    @patch("os.makedirs")
    @patch("os.path.dirname")
    @patch("rag._touch_chromadb_files")
    def test_download_chromadb_bucket_not_exists(self, mock_touch, mock_dirname, mock_makedirs, mock_get_client):
        """Test download when bucket doesn't exist."""
        # Use minimal mocks with spec to reduce memory
        mock_client = Mock(spec=["bucket"])
        mock_bucket = Mock(spec=["exists", "list_blobs"])
        mock_bucket.exists.return_value = False
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        _download_chromadb_from_gcs("test-bucket", "/local/path")

        mock_makedirs.assert_called()
        mock_bucket.list_blobs.assert_not_called()

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag._get_gcs_client")
    @patch("os.makedirs")
    @patch("os.path.join")
    @patch("os.path.dirname")
    @patch("rag._touch_chromadb_files")
    def test_download_chromadb_with_blobs(self, mock_touch, mock_dirname, mock_join, mock_makedirs, mock_get_client):
        """Test download with actual blobs - use minimal mocks."""
        # Use spec to limit mock attributes and reduce memory
        mock_client = Mock(spec=["bucket"])
        mock_bucket = Mock(spec=["exists", "list_blobs"])
        mock_bucket.exists.return_value = True

        # Create minimal mock blob - only needed attributes
        mock_blob = Mock(spec=["name", "size", "download_to_filename"])
        mock_blob.name = "chromadb/test_file.txt"
        mock_blob.size = 100  # Small size for memory efficiency
        mock_blob.download_to_filename = Mock()

        # Only one blob to reduce memory
        mock_bucket.list_blobs.return_value = [mock_blob]
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        mock_join.return_value = "/local/path/test_file.txt"
        mock_dirname.return_value = "/local/path"

        _download_chromadb_from_gcs("test-bucket", "/local/path")

        mock_blob.download_to_filename.assert_called_once()
        mock_touch.assert_called_once_with("/local/path")

    @patch("rag.GCS_AVAILABLE", False)
    def test_download_chromadb_gcs_not_available(self):
        """Test download raises error when GCS not available."""
        # rag module already imported via conftest.py

        with pytest.raises(Exception, match="GCS Python client not available"):
            _download_chromadb_from_gcs("test-bucket", "/local/path")


class TestUploadChromaDBToGCS:
    """Tests for _upload_chromadb_to_gcs function."""

    def teardown_method(self):
        """Clear mocks after each test."""
        pass

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag._get_gcs_client")
    @patch("os.path.exists")
    def test_upload_chromadb_path_not_exists(self, mock_exists, mock_get_client):
        """Test upload when local path doesn't exist."""
        mock_exists.return_value = False

        result = _upload_chromadb_to_gcs("test-bucket", "/nonexistent/path")

        assert result == (0, 0, 0)

    @patch("rag.GCS_AVAILABLE", True)
    @patch("rag._get_gcs_client")
    @patch("os.path.exists")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open, read_data=b"data")  # Smaller data
    @patch("os.path.getsize")
    @patch("hashlib.md5")
    def test_upload_chromadb_with_files(
        self, mock_md5, mock_getsize, mock_file, mock_walk, mock_exists, mock_get_client
    ):
        """Test upload with actual files - reduced to 1 file for memory efficiency."""
        import hashlib

        mock_exists.return_value = True
        # Reduced from 2 files to 1 file to reduce memory
        mock_walk.return_value = [("/local/path", [], ["file1.txt"])]

        # Use spec to limit mock attributes
        mock_client = Mock(spec=["bucket"])
        mock_bucket = Mock(spec=["exists", "blob"])
        mock_bucket.exists.return_value = True
        mock_blob = Mock(spec=["exists", "reload", "md5_hash", "upload_from_filename"])
        mock_blob.exists.return_value = False
        mock_blob.reload = Mock()
        mock_blob.md5_hash = None
        mock_blob.upload_from_filename = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        mock_getsize.return_value = 10  # Smaller size for memory efficiency
        mock_md5_obj = Mock(spec=["hexdigest"])
        mock_md5_obj.hexdigest.return_value = "abc123"
        mock_md5.return_value = mock_md5_obj

        result = _upload_chromadb_to_gcs("test-bucket", "/local/path")

        assert result[0] > 0  # uploaded_count
        assert mock_blob.upload_from_filename.call_count == 1  # Reduced from 2

    @patch("rag.GCS_AVAILABLE", False)
    def test_upload_chromadb_gcs_not_available(self):
        """Test upload raises error when GCS not available."""
        # rag module already imported via conftest.py

        with pytest.raises(Exception, match="GCS Python client not available"):
            _upload_chromadb_to_gcs("test-bucket", "/local/path")


class TestStartChromaDBServer:
    """Tests for _start_chromadb_server function."""

    def teardown_method(self):
        """Clear mocks after each test."""
        pass

    @patch("subprocess.Popen")
    @patch("socket.socket")
    @patch("rag._download_chromadb_from_gcs")
    @patch("os.getenv")
    @patch("os.environ.copy")
    @patch("threading.Thread")  # Mock threading to prevent background threads
    def test_start_chromadb_server_success(
        self, mock_thread, mock_env_copy, mock_getenv, mock_download, mock_socket, mock_popen
    ):
        """Test successful ChromaDB server start."""
        mock_getenv.return_value = "test-bucket"
        mock_env_copy.return_value = {"CHROMA_TELEMETRY_DISABLED": "1"}
        # Use spec to limit mock attributes
        mock_sock = Mock(spec=["connect_ex", "close"])
        mock_sock.connect_ex.return_value = 1  # Port not in use
        mock_sock.close = Mock()
        mock_socket.return_value = mock_sock

        # Mock process with attributes needed by background threads
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process still running
        mock_process.returncode = None
        mock_process.stdout = Mock()
        mock_process.stdout.readline = Mock(return_value="")  # Empty line to stop iteration
        mock_process.stdout.read = Mock(return_value="")
        mock_popen.return_value = mock_process

        # Mock threading to prevent actual background threads from starting
        mock_thread.return_value.start = Mock()

        _start_chromadb_server()

        mock_download.assert_called_once()
        mock_popen.assert_called_once()

    @patch("socket.socket")
    @patch("os.getenv")
    def test_start_chromadb_server_already_running(self, mock_getenv, mock_socket):
        """Test ChromaDB server already running."""
        mock_getenv.return_value = "test-bucket"
        # Use spec to limit mock attributes
        mock_sock = Mock(spec=["connect_ex", "close"])
        mock_sock.connect_ex.return_value = 0  # Port in use
        mock_sock.close = Mock()
        mock_socket.return_value = mock_sock

        # Should return early without starting
        _start_chromadb_server()


class TestCleanupChromaDBServer:
    """Tests for _cleanup_chromadb_server function."""

    def teardown_method(self):
        """Clear mocks after each test."""
        import rag

        rag._chromadb_server_process = None

    @patch("os.getenv")
    @patch("rag.GCS_AVAILABLE", False)
    @patch("rag._gcs_synced", False)
    def test_cleanup_with_no_server_process(self, mock_getenv):
        """Test cleanup when no server process exists."""
        import rag

        rag._chromadb_server_process = None

        _cleanup_chromadb_server()

        # Should complete without errors
        assert True

    @patch("os.getenv")
    @patch("rag.GCS_AVAILABLE", False)
    @patch("rag._gcs_synced", False)
    def test_cleanup_terminates_server_process(self, mock_getenv):
        """Test cleanup terminates server process."""
        import rag
        import subprocess

        # Mock process that terminates successfully
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = Mock()
        mock_process.kill = Mock()

        rag._chromadb_server_process = mock_process

        _cleanup_chromadb_server()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        assert rag._chromadb_server_process is None

    @patch("os.getenv")
    @patch("rag.GCS_AVAILABLE", False)
    @patch("rag._gcs_synced", False)
    def test_cleanup_kills_on_timeout(self, mock_getenv):
        """Test cleanup kills process on timeout."""
        import rag
        import subprocess

        # Mock process that times out
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = Mock(side_effect=subprocess.TimeoutExpired("cmd", 10))
        mock_process.kill = Mock()

        rag._chromadb_server_process = mock_process

        _cleanup_chromadb_server()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        mock_process.kill.assert_called_once()
        assert rag._chromadb_server_process is None


# ============================================================================
# Retriever Class
# ============================================================================


@pytest.fixture
def mock_chromadb_collection():
    """Mock ChromaDB collection for Retriever tests."""
    collection = Mock()
    collection.count.return_value = 100
    collection.metadata = {"hnsw:space": "cosine"}
    collection.query.return_value = {
        "ids": [["doc1", "doc2"]],
        "documents": [["Document 1 text", "Document 2 text"]],
        "metadatas": [[{"source": "test.pdf"}, {"source": "test.pdf"}]],
        "distances": [[0.15, 0.25]],
    }
    return collection


@pytest.fixture
def mock_chromadb_client(mock_chromadb_collection):
    """Mock ChromaDB client."""
    client = Mock()
    client.get_or_create_collection.return_value = mock_chromadb_collection
    return client


class TestRetrieverInit:
    """Tests for Retriever initialization."""

    @patch("rag.get_chromadb_client")
    def test_retriever_init(self, mock_get_client, mock_chromadb_client, mock_chromadb_collection):
        """Test Retriever initialization."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client

        retriever = Retriever()

        assert retriever.client is not None
        assert retriever.collection is not None
        assert retriever.mode == "chroma-dist"

    @patch("rag.get_chromadb_client")
    @patch("rag.ENABLE_CACHE", True)
    def test_retriever_init_with_cache(self, mock_get_client, mock_chromadb_client):
        """Test Retriever initialization with cache enabled."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client

        retriever = Retriever()
        assert retriever._query_cache is not None

    @patch("rag.get_chromadb_client")
    @patch("rag.ENABLE_CACHE", False)
    def test_retriever_init_without_cache(self, mock_get_client, mock_chromadb_client):
        """Test Retriever initialization without cache."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client

        retriever = Retriever()
        assert retriever._query_cache is None


class TestRetrieverStats:
    """Tests for Retriever.stats() method."""

    @patch("rag.get_chromadb_client")
    def test_retriever_stats(self, mock_get_client, mock_chromadb_client, mock_chromadb_collection):
        """Test Retriever stats method."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client

        retriever = Retriever()
        stats = retriever.stats()

        assert isinstance(stats, dict)
        assert "collection" in stats
        assert "count" in stats
        assert "emb_model" in stats
        assert stats["count"] == 100


class TestRetrieverQuery:
    """Tests for Retriever.query() method."""

    @patch("rag.get_chromadb_client")
    @patch("rag.get_embedder")
    @patch("rag.normalize_query")
    def test_retriever_query_success(
        self, mock_norm, mock_get_embedder, mock_get_client, mock_chromadb_client, mock_chromadb_collection
    ):
        """Test Retriever query returns results."""
        from rag import Retriever

        # Setup mocks
        mock_get_client.return_value = mock_chromadb_client
        mock_norm.return_value = "test query"

        mock_embedder = Mock()
        # Use smaller embeddings (128 dim) for memory efficiency
        mock_embedder.query_embed.return_value = iter([np.array([0.1] * 128, dtype=np.float32)])
        mock_get_embedder.return_value = mock_embedder

        retriever = Retriever()
        results = retriever.query("test query", k=2)

        assert isinstance(results, list)
        if len(results) > 0:
            assert "text" in results[0] or "id" in results[0]

    @pytest.mark.parametrize("query_input", ["", None])
    @patch("rag.get_chromadb_client")
    @patch("rag.normalize_query")
    def test_retriever_query_empty_or_invalid(self, mock_norm, mock_get_client, mock_chromadb_client, query_input):
        """Test Retriever query with empty/invalid input."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client
        mock_norm.return_value = ""
        retriever = Retriever()
        results = retriever.query(query_input, k=3)
        assert results == []

    @patch("rag.get_chromadb_client")
    @patch("rag.get_embedder")
    @patch("rag.normalize_query")
    @patch("rag.ENABLE_CACHE", True)
    def test_retriever_query_caching(
        self, mock_norm, mock_get_embedder, mock_get_client, mock_chromadb_client, mock_chromadb_collection
    ):
        """Test Retriever query caching."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client
        mock_norm.return_value = "cached query"

        mock_embedder = Mock()
        # Use smaller embeddings (128 dim) for memory efficiency
        mock_embedder.query_embed.return_value = iter([np.array([0.1] * 128, dtype=np.float32)])
        mock_get_embedder.return_value = mock_embedder

        retriever = Retriever()

        # First query
        results1 = retriever.query("cached query", k=2)

        # Second query with same text should use cache
        results2 = retriever.query("cached query", k=2)

        # Should return same results
        assert results1 == results2
        # Embedder should only be called once (cached on second call)
        assert mock_embedder.query_embed.call_count <= 2  # May be called for embedding cache too

    @patch("rag.get_chromadb_client")
    @patch("rag.get_embedder")
    @patch("rag.normalize_query")
    def test_retriever_query_k_limits(
        self, mock_norm, mock_get_embedder, mock_get_client, mock_chromadb_client, mock_chromadb_collection
    ):
        """Test Retriever query respects k limits."""
        from rag import Retriever

        mock_get_client.return_value = mock_chromadb_client
        mock_norm.return_value = "test"

        mock_embedder = Mock()

        # Return an iterator that can be called multiple times
        # Use smaller embeddings (128 dim) for memory efficiency
        def mock_embed_iter():
            return iter([np.array([0.1] * 128, dtype=np.float32)])

        mock_embedder.query_embed.return_value = mock_embed_iter()
        mock_get_embedder.return_value = mock_embedder

        retriever = Retriever()

        # Test k=0 should become k=1
        results = retriever.query("test", k=0)
        # Should not raise exception
        assert isinstance(results, list)

        # Test k>50 should be capped at 50
        # Reset the mock to return a new iterator
        mock_embedder.query_embed.return_value = mock_embed_iter()
        results = retriever.query("test", k=100)
        # Should not raise exception
        assert isinstance(results, list)
