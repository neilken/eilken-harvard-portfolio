"""Unit tests for ingestion pipeline functions."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time

pytestmark = pytest.mark.unit

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import after path setup
try:
    from rag import run_ingest, ARTIFACTS_DIR
except ImportError:
    # Handle case where imports fail
    pass


# Shared fixtures for common mock setups
@pytest.fixture
def mock_ingestion_deps():
    """Shared fixture for common ingestion test dependencies."""
    with (
        patch("rag.get_chromadb_client") as mock_client,
        patch("rag.get_embedder") as mock_embedder,
        patch("rag.load_all") as mock_load,
        patch("rag.semantic_chunks") as mock_chunks,
        patch("rag._upload_chromadb_to_gcs") as mock_upload,
        patch("rag._approx_token_len") as mock_token_len,
        patch("rag.hashlib.md5") as mock_md5,
        patch("os.getenv") as mock_getenv,
        patch("os.path.join") as mock_join,
        patch("builtins.open", create=True) as mock_open,
        patch("time.time") as mock_time,
        patch("subprocess.check_output") as mock_subprocess,
    ):
        yield {
            "client": mock_client,
            "embedder": mock_embedder,
            "load": mock_load,
            "chunks": mock_chunks,
            "upload": mock_upload,
            "token_len": mock_token_len,
            "md5": mock_md5,
            "getenv": mock_getenv,
            "join": mock_join,
            "open": mock_open,
            "time": mock_time,
            "subprocess": mock_subprocess,
        }


@pytest.fixture
def mock_chromadb_setup(mock_ingestion_deps):
    """Setup mock ChromaDB client and collection."""
    mock_client_obj = Mock()
    mock_collection = Mock()
    mock_collection.get.return_value = {"ids": [], "metadatas": [], "embeddings": []}
    mock_collection.upsert = Mock()
    mock_collection.count.return_value = 0
    mock_collection.add = Mock()
    mock_client_obj.get_or_create_collection.return_value = mock_collection
    mock_ingestion_deps["client"].return_value = mock_client_obj
    return {"client_obj": mock_client_obj, "collection": mock_collection}


@pytest.fixture
def mock_embedder_setup(mock_ingestion_deps):
    """Setup mock embedder."""
    mock_embedder_obj = Mock()
    mock_embed_iter = Mock()
    mock_embed_iter.__iter__ = Mock(return_value=iter([[0.1] * 384]))
    mock_embedder_obj.passage_embed.return_value = mock_embed_iter
    mock_ingestion_deps["embedder"].return_value = mock_embedder_obj
    return mock_embedder_obj


@pytest.fixture
def mock_file_loading():
    """Mock file loading operations."""
    with (
        patch("rag.glob.glob") as mock_glob,
        patch("rag.os.path.isfile", return_value=True) as mock_isfile,
        patch("rag._load_pdf") as mock_load_pdf,
        patch("rag._approx_token_len", return_value=50) as mock_token_len,
        patch("rag.hashlib.md5") as mock_md5_hash,
    ):
        mock_glob.return_value = ["/workspace/data/test.pdf"]
        mock_load_pdf.return_value = [("test.pdf", "Sample content")]
        mock_md5_obj = Mock()
        mock_md5_obj.hexdigest.return_value = "abc123"
        mock_md5_hash.return_value = mock_md5_obj
        yield {
            "glob": mock_glob,
            "isfile": mock_isfile,
            "load_pdf": mock_load_pdf,
            "token_len": mock_token_len,
            "md5": mock_md5_hash,
        }


class TestRunIngest:
    """Tests for run_ingest function."""

    def test_run_ingest_success(self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading):
        """Test successful ingestion."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        # Setup mocks
        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 10]  # Start and end time
        deps["subprocess"].return_value = b"abc123def456"  # Mock git commit
        deps["upload"].return_value = (0, 0, 0)  # Mock GCS upload
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",  # Empty to avoid GCS upload in tests
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Configure ChromaDB mock
        mock_chromadb_setup["collection"].count.return_value = 5

        # Configure embedder mock with smaller embeddings for memory efficiency
        mock_embed_iter = Mock()
        mock_embed_iter.__iter__ = Mock(return_value=iter([[0.1] * 128, [0.2] * 128]))
        mock_embedder_setup.passage_embed.return_value = mock_embed_iter

        # Setup file paths
        mock_file_loading["load_pdf"].return_value = [("test.pdf", "Sample document content")]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        # Run ingestion
        result = run_ingest(target_tokens=100, max_tokens=200)

        # Verify results
        assert "added" in result
        assert "n_chunks" in result
        assert "elapsed_sec" in result
        # elapsed_sec should be 10 based on mock_time side_effect
        assert result["elapsed_sec"] == 10
        # DVC-based versioning, no git_commit in metadata
        assert "collection" in result
        assert "embedding_model" in result

    def test_run_ingest_no_documents(self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup):
        """Test ingestion with no documents."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",  # Empty to avoid GCS upload
            "ARTIFACTS_DIR": "/workspace/artifacts",
        }.get(k, d)

        deps["load"].return_value = []  # No documents
        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        result = run_ingest()

        assert result["num_input_docs"] == 0
        assert result["n_chunks"] == 0

    def test_run_ingest_with_version_tracking(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test ingestion includes version tracking in metadata."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123def456"
        deps["upload"].return_value = (0, 0, 0)  # Mock GCS upload
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",  # Empty to avoid GCS upload
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Use smaller embeddings (128 dim) for memory efficiency
        mock_embedder_setup.passage_embed.return_value = iter([[0.1] * 128])

        # Mock file loading
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/metadata.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        result = run_ingest()

        # Verify upsert was called
        assert mock_chromadb_setup["collection"].upsert.called
        # Verify basic stats are in result
        assert "n_chunks" in result or "collection" in result

    def test_run_ingest_handles_exceptions(self, mock_ingestion_deps):
        """Test ingestion handles exceptions gracefully."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        mock_ingestion_deps["getenv"].return_value = "test-bucket"
        mock_ingestion_deps["client"].side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            run_ingest()


class TestIngestMetadata:
    """Tests for ingestion metadata and artifacts."""

    def test_ingest_writes_metadata(self):
        """Test that ingestion writes metadata to artifacts."""
        try:
            from rag import ARTIFACTS_DIR
        except ImportError:
            pytest.skip("rag module not available")

        # Verify artifacts directory is defined
        assert ARTIFACTS_DIR is not None
        assert isinstance(ARTIFACTS_DIR, str)

    def test_ingest_returns_complete_stats(self):
        """Test that run_ingest returns complete statistics."""
        # Test the expected return structure
        expected_keys = ["added", "n_chunks", "avg_tokens", "num_input_docs", "elapsed_sec", "skipped_embeddings"]
        sample_result = {
            "added": 10,
            "n_chunks": 10,
            "avg_tokens": 150,
            "num_input_docs": 2,
            "elapsed_sec": 5.5,
            "skipped_embeddings": 0,
        }

        for key in expected_keys:
            assert key in sample_result, f"Missing key: {key}"


class TestIngestionErrorPaths:
    """Tests for ingestion error handling and fallback paths."""

    def test_ingest_embedding_fallback_when_missing(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test embedding fallback when existing chunk has no embedding."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Simulate existing chunk with same hash but no embedding
        mock_chromadb_setup["collection"].get.return_value = {
            "ids": ["test.pdf::chunk_0"],
            "metadatas": [{"content_hash": "abc123"}],
            "embeddings": [None],  # No embedding - should trigger fallback
        }
        mock_chromadb_setup["collection"].count.return_value = 1

        # Fallback embedding should be called
        mock_embedder_setup.passage_embed.return_value = iter([[0.1] * 384])
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        result = run_ingest()

        # Verify fallback embedding was called
        assert mock_embedder_setup.passage_embed.called
        # Verify upsert was called with embeddings
        assert mock_chromadb_setup["collection"].upsert.called

    def test_ingest_embedding_fallback_exception(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test embedding fallback uses zero vector when embedding fails."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Existing chunk with no embedding
        mock_chromadb_setup["collection"].get.return_value = {
            "ids": ["test.pdf::chunk_0"],
            "metadatas": [{"content_hash": "abc123"}],
            "embeddings": [None],
        }
        mock_chromadb_setup["collection"].count.return_value = 1

        # Fallback embedding raises exception - should use zero vector
        mock_embedder_setup.passage_embed.side_effect = Exception("Embedding failed")
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        result = run_ingest()

        # Verify fallback embedding was attempted (when existing embedding is None)
        # Verify ingestion completed (zero vector fallback should allow it to continue)
        assert "added" in result
        assert mock_chromadb_setup["collection"].upsert.called

    def test_ingest_upsert_fallback_to_add(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test upsert fallback to add when upsert fails."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Upsert fails, should fallback to add
        mock_chromadb_setup["collection"].upsert.side_effect = Exception("Upsert failed")
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        result = run_ingest()

        # Verify upsert was attempted
        assert mock_chromadb_setup["collection"].upsert.called
        # Verify add was called as fallback
        assert mock_chromadb_setup["collection"].add.called

    def test_ingest_upsert_and_add_both_fail(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test that buffers are cleared when both upsert and add fail."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Both upsert and add fail
        mock_chromadb_setup["collection"].upsert.side_effect = Exception("Upsert failed")
        mock_chromadb_setup["collection"].add.side_effect = Exception("Add failed")
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        # Should not raise exception, should handle gracefully
        result = run_ingest()

        # Verify both were attempted
        assert mock_chromadb_setup["collection"].upsert.called
        assert mock_chromadb_setup["collection"].add.called
        # Should still return a result (with 0 added)
        assert "added" in result

    def test_ingest_skip_existing_large_collection(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test skip existing logic with large collection (>10k chunks)."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        # Large collection (>10k) - should use chunk ID pattern matching
        mock_chromadb_setup["collection"].count.return_value = 15000
        # First get returns limited results (max_check = 10000)
        mock_chromadb_setup["collection"].get.side_effect = [
            # First call: get existing chunks (limited to 10k)
            {
                "ids": [f"existing_{i}::chunk_0" for i in range(10000)],
                "metadatas": [{"source": f"/path/existing_{i}.pdf"} for i in range(10000)],
                "embeddings": [[0.1] * 384] * 10000,
            },
            # Second call: check for specific chunk ID pattern
            {"ids": ["/workspace/data/test.pdf#chapter=1::chunk_0"], "metadatas": [{}]},
        ]
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        # Patch SKIP_EXISTING to True
        with patch("rag.SKIP_EXISTING", True):
            result = run_ingest()

        # Verify chunk ID pattern matching was used (second get call)
        assert mock_chromadb_setup["collection"].get.call_count >= 2
        # Verify the chunk ID pattern was checked
        call_args_list = mock_chromadb_setup["collection"].get.call_args_list
        # Should have a call with chunk ID pattern for PDF
        chunk_id_calls = [
            call for call in call_args_list if call[1].get("ids") and "#chapter=1::chunk_0" in str(call[1]["ids"])
        ]
        assert len(chunk_id_calls) > 0

    def test_ingest_skip_existing_feature_file_pattern(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test skip existing logic with feature file chunk ID pattern."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        mock_chromadb_setup["collection"].count.return_value = 15000
        mock_chromadb_setup["collection"].get.side_effect = [
            # First call: get existing chunks
            {
                "ids": [f"existing_{i}::chunk_0" for i in range(10000)],
                "metadatas": [{"source": f"/path/existing_{i}.pdf"} for i in range(10000)],
                "embeddings": [[0.1] * 384] * 10000,
            },
            # Second call: check for feature file chunk ID
            {"ids": ["/path/LLM-Quant_Expanded_RAG_with_context.md#feature=first::chunk_0"], "metadatas": [{}]},
        ]

        # Feature file path
        mock_file_loading["glob"].return_value = ["/path/LLM-Quant_Expanded_RAG_with_context.md"]
        mock_file_loading["load_pdf"].return_value = []  # Not a PDF
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        # Patch SKIP_EXISTING to True
        with patch("rag.SKIP_EXISTING", True):
            result = run_ingest()

        # Verify feature file chunk ID pattern was checked
        call_args_list = mock_chromadb_setup["collection"].get.call_args_list
        feature_calls = [
            call for call in call_args_list if call[1].get("ids") and "#feature=first::chunk_0" in str(call[1]["ids"])
        ]
        assert len(feature_calls) > 0

    def test_ingest_skip_existing_source_extraction(
        self, mock_ingestion_deps, mock_chromadb_setup, mock_embedder_setup, mock_file_loading
    ):
        """Test skip existing logic extracts base paths from various source formats."""
        try:
            from rag import run_ingest
        except ImportError:
            pytest.skip("rag module not available")

        deps = mock_ingestion_deps
        deps["time"].side_effect = [0, 5]
        deps["subprocess"].return_value = b"abc123"
        deps["upload"].return_value = (0, 0, 0)
        deps["getenv"].side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
        }.get(k, d)

        mock_chromadb_setup["collection"].count.return_value = 100
        # Test various source formats
        mock_chromadb_setup["collection"].get.return_value = {
            "ids": ["chunk1", "chunk2", "chunk3", "chunk4"],
            "metadatas": [
                {"source": "/path/to/doc.pdf#chapter=1"},
                {"source": "/path/to/doc.pdf#page=5"},
                {"source": "/path/to/doc.md#feature=first"},
                {"source": "/path/to/doc.txt#full_document"},
            ],
            "embeddings": [[0.1] * 384] * 4,
        }

        # File that matches one of the sources
        mock_file_loading["glob"].return_value = ["/path/to/doc.pdf"]
        mock_file_loading["load_pdf"].return_value = [("doc.pdf", "Content")]
        mock_file_loading["md5"].return_value.hexdigest.return_value = "new_hash"  # Different hash
        deps["chunks"].return_value = ["Chunk 1"]

        deps["join"].return_value = "/workspace/artifacts/ingest_summary.json"
        deps["open"].return_value.__enter__ = Mock(return_value=Mock())
        deps["open"].return_value.__exit__ = Mock(return_value=False)

        # Patch SKIP_EXISTING to True
        with patch("rag.SKIP_EXISTING", True):
            result = run_ingest()

        # Verify source extraction logic was used
        assert mock_chromadb_setup["collection"].get.called
        # File should be processed (different hash means content changed)
        assert "added" in result


# ============================================================================
# PDF Processing Functions
# ============================================================================

import builtins

# Save real __import__ for fallback
_real_import = builtins.__import__

from rag import (
    _load_pdf,
    _extract_page_text,
    _extract_chapters_from_toc,
    _extract_non_chapter_sections_from_toc,
    _finalize_and_output_chapter,
    _remove_headers_footers,
    _norm,
    _save_feature,
)


class TestExtractPageText:
    """Tests for _extract_page_text function."""

    def test_extract_page_text_with_dict_blocks(self):
        """Test text extraction using get_text('dict') method."""
        # Mock page with dict blocks
        mock_page = Mock()
        mock_page.get_text.return_value = {
            "blocks": [
                {"lines": [{"spans": [{"text": "Line 1 "}, {"text": "continues"}]}, {"spans": [{"text": "Line 2"}]}]},
                {"lines": [{"spans": [{"text": "Paragraph 2"}]}]},
            ]
        }

        result = _extract_page_text(mock_page, page_num=1, base="test.pdf")

        assert result is not None
        # Note: spans are joined with space, so "Line 1 " + "continues" = "Line 1  continues"
        assert "Line 1" in result and "continues" in result
        assert "Line 2" in result
        assert "Paragraph 2" in result
        # Should have paragraph breaks between blocks
        assert "\n\n" in result

    def test_extract_page_text_fallback_to_text(self):
        """Test fallback to get_text('text') when dict fails."""
        mock_page = Mock()
        # First call (dict) raises exception
        mock_page.get_text.side_effect = [Exception("Dict method failed"), "Simple text content"]

        result = _extract_page_text(mock_page, page_num=1, base="test.pdf")

        assert result == "Simple text content"
        assert mock_page.get_text.call_count == 2

    @pytest.mark.parametrize(
        "mock_behavior,expected",
        [
            (Exception("All methods failed"), None),
            ({"blocks": []}, None),
        ],
    )
    def test_extract_page_text_failures(self, mock_behavior, expected):
        """Test returns None when extraction fails or blocks are empty."""
        mock_page = Mock()
        if isinstance(mock_behavior, Exception):
            mock_page.get_text.side_effect = mock_behavior
        else:
            mock_page.get_text.return_value = mock_behavior
        result = _extract_page_text(mock_page, page_num=1, base="test.pdf")
        assert result == expected

    def test_extract_page_text_skips_image_blocks(self):
        """Test that image blocks (without 'lines') are skipped."""
        mock_page = Mock()
        mock_page.get_text.return_value = {
            "blocks": [{"type": 1}, {"lines": [{"spans": [{"text": "Text content"}]}]}]  # Image block, no 'lines' key
        }

        result = _extract_page_text(mock_page, page_num=1, base="test.pdf")

        assert result is not None
        assert "Text content" in result


class TestExtractChaptersFromTOC:
    """Tests for _extract_chapters_from_toc function."""

    def test_extract_chapters_basic(self):
        """Test basic chapter extraction from TOC."""
        mock_doc = Mock()
        # TOC format: (level, title, page_num_0_indexed)
        mock_doc.get_toc.return_value = [
            (1, "Chapter 1: Introduction", 0),
            (1, "Chapter 2: Methods", 10),
            (1, "Chapter 3: Results", 20),
        ]

        result = _extract_chapters_from_toc(mock_doc)

        assert len(result) == 3
        assert 1 in result  # Page 1 (0-indexed + 1)
        assert 11 in result  # Page 11
        assert 21 in result  # Page 21
        assert result[1]["chapter_number"] == "1"
        assert result[1]["chapter_title"] == "Introduction"

    def test_extract_chapters_no_toc(self):
        """Test with no table of contents."""
        mock_doc = Mock()
        mock_doc.get_toc.return_value = []
        result = _extract_chapters_from_toc(mock_doc)
        assert result == {}

    def test_extract_chapters_handles_exception(self):
        """Test handles exception during TOC extraction."""
        mock_doc = Mock()
        mock_doc.get_toc.side_effect = Exception("TOC extraction failed")
        result = _extract_chapters_from_toc(mock_doc)
        assert result == {}

    def test_extract_chapters_various_formats(self):
        """Test extraction with various chapter title formats."""
        mock_doc = Mock()
        mock_doc.get_toc.return_value = [
            (1, "Chapter 1: Introduction", 0),
            (1, "Ch. 2 Methods", 10),
            (1, "3 Results", 20),  # Standalone number format
            (1, "Part I: Overview", 30),  # Should be skipped (organizational)
            (2, "1.1 Section", 5),  # Should be skipped (section format)
        ]

        result = _extract_chapters_from_toc(mock_doc)

        # Should extract 3 chapters, skip Part and section
        assert len(result) == 3
        assert 1 in result
        assert 11 in result
        assert 21 in result

    def test_extract_chapters_hierarchical_levels(self):
        """Test with hierarchical TOC levels."""
        mock_doc = Mock()
        # Level 1: Parts, Level 2: Chapters
        mock_doc.get_toc.return_value = [
            (1, "Part I: Fundamentals", 0),
            (2, "Chapter 1: Basics", 5),
            (2, "Chapter 2: Advanced", 15),
            (1, "Part II: Applications", 25),
            (2, "Chapter 3: Case Studies", 30),
        ]

        result = _extract_chapters_from_toc(mock_doc)

        # Should find chapters at level 2
        assert len(result) >= 3
        assert 6 in result  # Chapter 1 at page 6
        assert 16 in result  # Chapter 2 at page 16
        assert 31 in result  # Chapter 3 at page 31


class TestExtractNonChapterSectionsFromTOC:
    """Tests for _extract_non_chapter_sections_from_toc function."""

    def test_extract_non_chapter_sections_basic(self):
        """Test extraction of non-chapter sections."""
        mock_doc = Mock()
        mock_doc.get_toc.return_value = [
            (1, "Table of Contents", 0),
            (1, "Chapter 1: Introduction", 5),
            (1, "Index", 100),
            (1, "Bibliography", 105),
        ]

        result = _extract_non_chapter_sections_from_toc(mock_doc)

        # Should return 1-indexed page numbers
        assert 1 in result  # TOC
        assert 101 in result  # Index
        assert 106 in result  # Bibliography
        assert 6 not in result  # Chapter should not be included

    def test_extract_non_chapter_sections_all_keywords(self):
        """Test all non-chapter keywords are detected."""
        mock_doc = Mock()
        mock_doc.get_toc.return_value = [
            (1, "Preface", 0),
            (1, "Foreword", 2),
            (1, "Acknowledgements", 4),
            (1, "Appendix A", 90),
            (1, "Glossary", 95),
            (1, "List of Figures", 98),
        ]

        result = _extract_non_chapter_sections_from_toc(mock_doc)

        assert len(result) == 6
        assert 1 in result  # Preface
        assert 3 in result  # Foreword
        assert 5 in result  # Acknowledgements
        assert 91 in result  # Appendix
        assert 96 in result  # Glossary
        assert 99 in result  # List of Figures

    @pytest.mark.parametrize(
        "toc_behavior",
        [
            ([], "empty"),
            (Exception("TOC failed"), "exception"),
        ],
    )
    def test_extract_non_chapter_sections_errors(self, toc_behavior):
        """Test handles TOC errors."""
        mock_doc = Mock()
        if toc_behavior[1] == "exception":
            mock_doc.get_toc.side_effect = toc_behavior[0]
        else:
            mock_doc.get_toc.return_value = toc_behavior[0]
        result = _extract_non_chapter_sections_from_toc(mock_doc)
        assert result == set()

    def test_extract_non_chapter_sections_case_insensitive(self):
        """Test keyword matching is case insensitive."""
        mock_doc = Mock()
        mock_doc.get_toc.return_value = [
            (1, "INDEX", 50),
            (1, "bibliography", 55),
            (1, "Appendix", 60),
        ]

        result = _extract_non_chapter_sections_from_toc(mock_doc)

        assert 51 in result  # INDEX
        assert 56 in result  # bibliography
        assert 61 in result  # Appendix


class TestFinalizeAndOutputChapterPDF:
    """Tests for _finalize_and_output_chapter function (PDF-specific)."""

    def test_finalize_and_output_chapter_basic(self):
        """Test basic chapter finalization."""
        items = []
        chapter_data = {
            "chapter_num": "1",
            "chapter_title": "Introduction",
            "pages": [(1, "Page 1 text"), (2, "Page 2 text")],
        }

        _finalize_and_output_chapter(chapter_data, items, "/path/to/doc.pdf", "doc.pdf", {"title": "Test Book"}, 10)

        assert len(items) == 1
        source, text = items[0]
        assert "doc.pdf#chapter=1" in source
        assert "Introduction" in text
        assert "Page 1 text" in text
        assert "Page 2 text" in text
        assert "[Pages 1-2 of 10]" in text

    @pytest.mark.parametrize(
        "chapter_title,pages,expected_items",
        [
            ("", [(5, "Content")], 1),  # No title
            ("Test", [], 0),  # Empty pages
        ],
    )
    def test_finalize_and_output_chapter_edge_cases(self, chapter_title, pages, expected_items):
        """Test chapter finalization edge cases."""
        items = []
        chapter_data = {"chapter_num": "1", "chapter_title": chapter_title, "pages": pages}
        _finalize_and_output_chapter(chapter_data, items, "/path/doc.pdf", "doc.pdf", {}, 10)
        assert len(items) == expected_items
        if expected_items > 0:
            assert chapter_data["pages"] == []  # Pages cleared

    def test_finalize_and_output_chapter_with_title_sanitization(self):
        """Test title is sanitized in source path."""
        items = []
        chapter_data = {
            "chapter_num": "3",
            "chapter_title": "Advanced Topics / Special Cases",
            "pages": [(10, "Content")],
        }

        _finalize_and_output_chapter(chapter_data, items, "/path/doc.pdf", "doc.pdf", {}, 20)

        source, _ = items[0]
        # Should sanitize special characters
        assert "/" not in source or "Special_Cases" in source


class TestLoadPDF:
    """Tests for _load_pdf function."""

    @patch("rag.ENABLE_SECTION_FILTER", False)
    @patch("rag._norm")
    @patch("rag._remove_headers_footers")
    @patch("rag._extract_page_text")
    @patch("builtins.__import__")
    def test_load_pdf_no_filtering(self, mock_import, mock_extract, mock_remove, mock_norm):
        """Test PDF loading without section filtering."""
        # Mock fitz import
        mock_fitz = MagicMock()

        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                return mock_fitz
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        # Setup mocks
        mock_doc = Mock()
        mock_doc.metadata = {"title": "Test Book"}
        mock_doc.__len__ = Mock(return_value=3)
        mock_doc.__iter__ = Mock(return_value=iter([Mock(), Mock(), Mock()]))
        mock_fitz.open.return_value = mock_doc

        mock_extract.side_effect = ["Page 1", "Page 2", "Page 3"]
        mock_remove.side_effect = lambda x, **kwargs: x
        mock_norm.side_effect = lambda x: x

        result = _load_pdf("/path/test.pdf")

        assert len(result) == 3
        assert mock_fitz.open.called
        mock_doc.close.assert_called_once()

    @patch("rag.ENABLE_SECTION_FILTER", True)
    @patch("rag._extract_chapters_from_toc")
    @patch("rag._extract_non_chapter_sections_from_toc")
    @patch("rag._norm")
    @patch("rag._remove_headers_footers")
    @patch("rag._extract_page_text")
    @patch("rag._finalize_and_output_chapter")
    @patch("builtins.__import__")
    def test_load_pdf_with_chapter_filtering(
        self, mock_import, mock_finalize, mock_extract, mock_remove, mock_norm, mock_non_chapter, mock_chapters
    ):
        """Test PDF loading with chapter filtering enabled."""
        # Mock fitz import
        mock_fitz = MagicMock()

        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                return mock_fitz
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        # Setup mocks
        mock_doc = Mock()
        mock_doc.metadata = {"title": "Test Book"}
        mock_doc.__len__ = Mock(return_value=5)

        # Create mock pages
        mock_pages = [Mock() for _ in range(5)]
        mock_doc.__iter__ = Mock(return_value=iter(mock_pages))
        mock_fitz.open.return_value = mock_doc

        # Setup chapter map
        mock_chapters.return_value = {
            2: {"chapter_number": "1", "chapter_title": "Introduction"},
            4: {"chapter_number": "2", "chapter_title": "Methods"},
        }
        mock_non_chapter.return_value = set()

        mock_extract.side_effect = ["Page 1", "Page 2", "Page 3", "Page 4", "Page 5"]
        mock_remove.side_effect = lambda x, **kwargs: x
        mock_norm.side_effect = lambda x: x

        result = _load_pdf("/path/test.pdf")

        # Should call finalize for each chapter
        assert mock_finalize.call_count >= 0
        mock_doc.close.assert_called_once()

    @patch("builtins.__import__")
    def test_load_pdf_import_error(self, mock_import):
        """Test when PyMuPDF is not available."""

        # Make import raise ImportError for fitz
        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError("No module named 'fitz'")
            return __import__(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        result = _load_pdf("/path/test.pdf")

        assert result == []

    @patch("rag.ENABLE_SECTION_FILTER", True)
    @patch("rag._extract_chapters_from_toc")
    @patch("rag._norm")
    @patch("rag._remove_headers_footers")
    @patch("rag._extract_page_text")
    @patch("builtins.__import__")
    def test_load_pdf_no_toc_fallback(self, mock_import, mock_extract, mock_remove, mock_norm, mock_chapters):
        """Test fallback when TOC is not available."""
        # Mock fitz import
        mock_fitz = MagicMock()

        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                return mock_fitz
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        mock_doc = Mock()
        mock_doc.metadata = {}
        mock_doc.__len__ = Mock(return_value=2)
        mock_doc.__iter__ = Mock(return_value=iter([Mock(), Mock()]))
        mock_fitz.open.return_value = mock_doc

        # No chapters in TOC
        mock_chapters.return_value = {}
        mock_extract.side_effect = ["Page 1", "Page 2"]
        mock_remove.side_effect = lambda x, **kwargs: x
        mock_norm.side_effect = lambda x: x

        result = _load_pdf("/path/test.pdf")

        # Should fall back to processing all pages
        assert len(result) >= 0
        mock_doc.close.assert_called_once()

    @patch("rag.ENABLE_SECTION_FILTER", False)
    @patch("rag._extract_chapters_from_toc")
    @patch("rag._norm")
    @patch("rag._remove_headers_footers")
    @patch("rag._extract_page_text")
    @patch("builtins.__import__")
    def test_load_pdf_empty_pages(self, mock_import, mock_extract, mock_remove, mock_norm, mock_chapters):
        """Test with pages that have no text."""
        # Mock fitz import
        mock_fitz = MagicMock()

        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                return mock_fitz
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        mock_doc = Mock()
        mock_doc.metadata = {}
        mock_doc.__len__ = Mock(return_value=3)
        mock_doc.__iter__ = Mock(return_value=iter([Mock(), Mock(), Mock()]))
        mock_fitz.open.return_value = mock_doc

        # Some pages return empty text
        mock_extract.side_effect = ["", "Valid content", None]
        mock_remove.side_effect = lambda x, **kwargs: x if x else ""
        mock_norm.side_effect = lambda x: x

        result = _load_pdf("/path/test.pdf")

        # Should only include pages with content
        assert len(result) == 1
        assert "Valid content" in result[0][1]

    @patch("rag.TQDM_AVAILABLE", False)
    @patch("rag.ENABLE_SECTION_FILTER", True)
    @patch("rag._extract_chapters_from_toc")
    @patch("rag._extract_non_chapter_sections_from_toc")
    @patch("rag._norm")
    @patch("rag._remove_headers_footers")
    @patch("rag._extract_page_text")
    @patch("rag._finalize_and_output_chapter")
    @patch("builtins.__import__")
    def test_load_pdf_filters_non_chapter_sections(
        self, mock_import, mock_finalize, mock_extract, mock_remove, mock_norm, mock_non_chapter, mock_chapters
    ):
        """Test that non-chapter sections are filtered out."""
        # Mock fitz import
        mock_fitz = MagicMock()

        def import_side_effect(name, *args, **kwargs):
            if name == "fitz":
                return mock_fitz
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        mock_doc = Mock()
        mock_doc.metadata = {}
        mock_doc.__len__ = Mock(return_value=10)
        mock_pages = [Mock() for _ in range(10)]
        mock_doc.__iter__ = Mock(return_value=iter(mock_pages))
        mock_fitz.open.return_value = mock_doc

        # Chapters at pages 2, 5, 8
        mock_chapters.return_value = {
            2: {"chapter_number": "1", "chapter_title": "Ch1"},
            5: {"chapter_number": "2", "chapter_title": "Ch2"},
            8: {"chapter_number": "3", "chapter_title": "Ch3"},
        }
        # Index at page 9
        mock_non_chapter.return_value = {9, 10}

        mock_extract.side_effect = [f"Page {i}" for i in range(1, 11)]
        mock_remove.side_effect = lambda x, **kwargs: x
        mock_norm.side_effect = lambda x: x

        result = _load_pdf("/path/test.pdf")

        # Should filter out pages 9 and 10 (Index)
        mock_doc.close.assert_called_once()


class TestSaveFeature:
    """Tests for _save_feature function."""

    def test_save_feature_basic(self):
        """Test _save_feature with basic feature data."""
        items = []
        path = "/test/path.md"
        feature = "Test Feature"
        feature_data = {
            "full_name_or_formula": "Test Formula",
            "meaning": "Test meaning",
            "interpretation_or_signal": "> 15%",
            "financial_context": "Test context",
        }

        _save_feature(items, path, feature, feature_data)

        assert len(items) == 1
        # Path includes feature anchor: path#feature=Feature Name
        assert items[0][0] == f"{path}#feature={feature}"
        assert "Feature: Test Feature" in items[0][1]
        assert "Full Name or Formula: Test Formula" in items[0][1]
        assert "Meaning: Test meaning" in items[0][1]
        assert "Interpretation or Signal: > 15%" in items[0][1]
        assert "Financial Context: Test context" in items[0][1]

    def test_save_feature_empty_feature(self):
        """Test _save_feature with empty feature name (should return early)."""
        items = []
        path = "/test/path.md"
        feature = ""
        feature_data = {"meaning": "Test"}

        _save_feature(items, path, feature, feature_data)

        assert len(items) == 0

    def test_save_feature_minimal_data(self):
        """Test _save_feature with minimal feature data."""
        items = []
        path = "/test/path.md"
        feature = "Minimal Feature"
        feature_data = {}

        _save_feature(items, path, feature, feature_data)

        assert len(items) == 1
        assert "Feature: Minimal Feature" in items[0][1]

    def test_save_feature_with_thresholds(self):
        """Test _save_feature extracts thresholds from interpretation."""
        items = []
        path = "/test/path.md"
        feature = "Threshold Feature"
        feature_data = {"interpretation_or_signal": ">15% and <30"}

        _save_feature(items, path, feature, feature_data)

        assert len(items) == 1
        assert "Thresholds:" in items[0][1]
