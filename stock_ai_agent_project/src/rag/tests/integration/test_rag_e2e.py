"""End-to-end tests for RAG pipeline (ingestion → query flow)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

pytestmark = pytest.mark.integration

# Path setup now handled by conftest.py


class TestRAGE2EPipeline:
    """End-to-end tests for full RAG pipeline with mocked dependencies."""

    @patch("rag.get_chromadb_client")
    @patch("rag.get_embedder")
    @patch("rag.semantic_chunks")
    @patch("rag._upload_chromadb_to_gcs")
    @patch("rag._start_chromadb_server")
    @patch("rag._approx_token_len")
    @patch("rag.hashlib.md5")
    @patch("os.getenv")
    @patch("os.path.join")
    @patch("builtins.open", create=True)
    @patch("time.time")
    @patch("subprocess.check_output")
    def test_full_ingestion_to_query_flow(
        self,
        mock_subprocess,
        mock_time,
        mock_open,
        mock_join,
        mock_getenv,
        mock_md5,
        mock_token_len,
        mock_start_server,
        mock_upload,
        mock_chunks,
        mock_embedder,
        mock_client,
    ):
        """Test full pipeline: ingestion → query with mocked dependencies."""
        from rag import run_ingest, Retriever
        import hashlib

        # Setup time
        mock_time.side_effect = [0, 10, 11]  # Ingestion time, query time

        # Setup environment
        mock_getenv.side_effect = lambda k, d=None: {
            "GCS_BUCKET_NAME": "test-bucket",
            "ARTIFACTS_DIR": "/workspace/artifacts",
            "DATA_DIR": "/workspace/data",
            "VECTOR_COLLECTION": "test_collection",
            "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
        }.get(k, d)

        # Mock git commit
        mock_subprocess.return_value = b"abc123def456"

        # Setup ChromaDB client
        mock_client_obj = Mock()
        mock_collection = Mock()
        mock_collection.get.return_value = {"ids": [], "metadatas": [], "embeddings": []}
        mock_collection.upsert = Mock()
        mock_collection.count.return_value = 0  # Start with 0 existing chunks
        mock_collection.query.return_value = {
            "ids": [["chunk1", "chunk2"]],
            "documents": [["Chunk 1 about ROE", "Chunk 2 about profitability"]],
            "metadatas": [[{"source": "test.pdf"}, {"source": "test.pdf"}]],
            "distances": [[0.1, 0.2]],
        }
        mock_client_obj.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_obj

        # Setup embedder - use smaller embeddings for memory efficiency (128 dim)
        mock_embedder_obj = Mock()
        mock_embed_iter = Mock()
        mock_embed_iter.__iter__ = Mock(return_value=iter([[0.1] * 128, [0.2] * 128]))
        mock_embedder_obj.passage_embed.return_value = mock_embed_iter
        mock_embedder_obj.query_embed.return_value = iter([[0.15] * 128])
        mock_embedder.return_value = mock_embedder_obj

        # Setup semantic chunks
        mock_chunks.return_value = ["Chunk 1 about ROE", "Chunk 2 about profitability"]

        # Setup file operations
        mock_join.return_value = "/workspace/artifacts/ingest_summary.json"
        mock_open.return_value.__enter__ = Mock(return_value=Mock())
        mock_open.return_value.__exit__ = Mock(return_value=False)

        # Mock token length and hash
        mock_token_len.return_value = 50
        mock_md5_obj = Mock()
        mock_md5_obj.hexdigest.return_value = "abc123"
        mock_md5.return_value = mock_md5_obj

        # Mock glob and file loading to simulate documents being found
        # This is critical - run_ingest uses glob.glob to find files, not load_all
        with (
            patch("rag.glob.glob") as mock_glob,
            patch("rag.os.path.isfile", return_value=True),
            patch("rag._load_pdf") as mock_load_pdf,
        ):
            # Setup file paths - return a PDF file
            mock_glob.return_value = ["/workspace/data/test.pdf"]
            # Setup document loading - return tuple of (source, text)
            mock_load_pdf.return_value = [("test.pdf", "Sample financial document about ROE and profitability.")]

            # Run ingestion
            ingest_result = run_ingest()

            # Verify ingestion
            assert "added" in ingest_result
            assert "n_chunks" in ingest_result
            assert mock_collection.upsert.called, "upsert should be called to store chunks"

        # Now test query
        with patch("rag.get_chromadb_client", return_value=mock_client_obj):
            retriever = Retriever()
            query_result = retriever.query("What is ROE?", k=2)

        # Verify query results
        assert len(query_result) > 0
        assert "text" in query_result[0] or "document" in query_result[0]
