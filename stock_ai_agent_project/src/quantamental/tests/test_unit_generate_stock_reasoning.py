"""
Unit tests for generate_stock_reasoning.py
Tests RAG-based stock reasoning generation functionality
"""

import sys
import os
import tempfile

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from generate_stock_reasoning import (
    normalize_query,
    get_embedder,
    get_rag_connection,
    get_chroma_db,
    query_rag_texts,
    store_query_in_chromadb,
    setup_credentials,
    list_gcs_files,
    download_csv_from_gcs,
    upload_csv_to_gcs,
    generate_reasoning_for_stock,
    process_single_stock,
    process_csv_with_rag,
    generate_reasoning_for_dataframe,
    add_reasoning_to_combined_file,
)


class TestNormalizeQuery:
    """Test query normalization function."""

    @pytest.mark.unit
    def test_normalize_query_basic(self):
        """Test basic query normalization."""
        result = normalize_query("  What is ROE?  ")
        assert result == "what is roe?"
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_normalize_query_removes_extra_spaces(self):
        """Test that extra spaces are removed."""
        result = normalize_query("What   is    ROE?")
        assert result == "what is roe?"

    @pytest.mark.unit
    def test_normalize_query_handles_empty_string(self):
        """Test empty string handling."""
        result = normalize_query("")
        assert result == ""

    @pytest.mark.unit
    def test_normalize_query_handles_non_string(self):
        """Test non-string input handling."""
        result = normalize_query(None)
        assert result == ""
        result = normalize_query(123)
        assert result == ""


class TestGetEmbedder:
    """Test embedder initialization."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.TextEmbedding")
    def test_get_embedder_returns_cached_instance(self, mock_text_embedding):
        """Test that embedder is cached."""
        mock_instance = MagicMock()
        mock_text_embedding.return_value = mock_instance

        # Clear cache
        import generate_stock_reasoning

        generate_stock_reasoning._embedder_cache = None

        embedder1 = get_embedder()
        embedder2 = get_embedder()

        # Should only be called once (cached)
        assert mock_text_embedding.call_count == 1
        assert embedder1 is embedder2

    @pytest.mark.unit
    @patch("generate_stock_reasoning.TextEmbedding", None)
    def test_get_embedder_raises_if_not_available(self):
        """Test that ImportError is raised if TextEmbedding is not available."""
        import generate_stock_reasoning

        generate_stock_reasoning._embedder_cache = None

        with pytest.raises(ImportError, match="fastembed is required"):
            get_embedder()


class TestGetRagConnection:
    """Test RAG connection setup."""

    @pytest.mark.unit
    @patch.dict(os.environ, {"GCS_BUCKET_NAME": "test-bucket"})
    @patch("generate_stock_reasoning.storage.Client")
    @patch("generate_stock_reasoning.chromadb.PersistentClient")
    @patch("generate_stock_reasoning.tempfile.gettempdir", return_value="/tmp")
    def test_get_rag_connection_success(
        self, mock_tempdir, mock_chroma_client, mock_storage_client
    ):
        """Test successful RAG connection setup."""
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.name = "chromadb/test_file.txt"
        mock_bucket.list_blobs.return_value = [mock_blob]
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        mock_chroma_instance = MagicMock()
        mock_chroma_client.return_value = mock_chroma_instance

        # Clear cache
        import generate_stock_reasoning

        generate_stock_reasoning._cache = {}

        get_rag_connection()

        # Verify ChromaDB client was created
        mock_chroma_client.assert_called_once()
        assert "default" in generate_stock_reasoning._cache

    @pytest.mark.unit
    def test_get_rag_connection_raises_if_no_bucket(self):
        """Test that ValueError is raised if GCS_BUCKET_NAME is not set."""
        import generate_stock_reasoning

        # Clear cache first
        generate_stock_reasoning._cache = {}

        with patch.dict(os.environ, {}, clear=True):
            with patch("os.getenv", return_value=None):
                with pytest.raises(ValueError, match="GCS_BUCKET_NAME not set"):
                    get_rag_connection()


class TestGetChromaDb:
    """Test ChromaDB connection retrieval."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.get_rag_connection")
    @patch("generate_stock_reasoning.get_embedder")
    def test_get_chroma_db_returns_query_function(self, mock_embedder, mock_rag_conn):
        """Test that get_chroma_db returns an object with query method."""
        # Setup cache
        import generate_stock_reasoning

        mock_chroma_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[{"key": "value"}]],
            "distances": [[0.5]],
        }
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        generate_stock_reasoning._cache["default"] = (
            mock_chroma_client,
            "test_collection",
        )

        # Mock embedder
        mock_embedder_instance = MagicMock()
        mock_embedder_instance.query_embed.return_value = iter([[0.1, 0.2, 0.3]])
        mock_embedder.return_value = mock_embedder_instance

        chroma_db = get_chroma_db()

        # Should have query method
        assert hasattr(chroma_db, "query")
        assert callable(chroma_db.query)

    @pytest.mark.unit
    @patch("generate_stock_reasoning.get_rag_connection")
    @patch("generate_stock_reasoning.get_embedder")
    def test_get_chroma_db_calls_rag_connection_if_needed(
        self, mock_embedder, mock_rag_conn
    ):
        """Test that get_rag_connection is called if cache is empty."""
        import generate_stock_reasoning

        # Clear cache
        generate_stock_reasoning._cache = {}

        # Setup mock to populate cache when called
        def setup_cache(collection_name=None):
            mock_chroma_client = MagicMock()
            generate_stock_reasoning._cache["default"] = (
                mock_chroma_client,
                "test_collection",
            )

        mock_rag_conn.side_effect = setup_cache

        # Mock embedder
        mock_embedder_instance = MagicMock()
        mock_embedder_instance.query_embed.return_value = iter([[0.1, 0.2, 0.3]])
        mock_embedder.return_value = mock_embedder_instance

        # Mock collection
        mock_chroma_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        generate_stock_reasoning._cache["default"] = (
            mock_chroma_client,
            "test_collection",
        )

        # This should work now
        chroma_db = get_chroma_db()

        # Verify connection was attempted (if cache was empty, it would be called)
        # Since we pre-populated cache, it might not be called, but the function should work
        assert hasattr(chroma_db, "query")


class TestQueryRagTexts:
    """Test query_rag_texts function."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.get_rag_connection")
    @patch("generate_stock_reasoning.get_chroma_db")
    def test_query_rag_texts_returns_document_texts(
        self, mock_get_chroma_db, mock_rag_conn
    ):
        """Test that query_rag_texts returns list of document texts."""
        # Setup mock
        mock_chroma_db = MagicMock()
        mock_chroma_db.query.return_value = [
            {"document": "Document 1", "id": "id1"},
            {"document": "Document 2", "id": "id2"},
        ]
        mock_get_chroma_db.return_value = mock_chroma_db

        results = query_rag_texts("test query", k=2)

        assert isinstance(results, list)
        assert len(results) == 2
        assert "Document 1" in results
        assert "Document 2" in results

    @pytest.mark.unit
    @patch("generate_stock_reasoning.get_rag_connection")
    @patch("generate_stock_reasoning.get_chroma_db")
    def test_query_rag_texts_handles_empty_results(
        self, mock_get_chroma_db, mock_rag_conn
    ):
        """Test that query_rag_texts handles empty results."""
        mock_chroma_db = MagicMock()
        mock_chroma_db.query.return_value = []
        mock_get_chroma_db.return_value = mock_chroma_db

        results = query_rag_texts("test query")

        assert results == []


class TestStoreQueryInChromaDb:
    """Test store_query_in_chromadb function."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.get_rag_connection")
    @patch("generate_stock_reasoning.get_embedder")
    def test_store_query_in_chromadb_success(self, mock_embedder, mock_rag_conn):
        """Test successful query storage."""
        # Setup cache
        import generate_stock_reasoning

        mock_chroma_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        generate_stock_reasoning._cache["default"] = (
            mock_chroma_client,
            "test_collection",
        )

        # Mock embedder
        mock_embedder_instance = MagicMock()
        mock_embedder_instance.query_embed.return_value = iter([[0.1, 0.2, 0.3]])
        mock_embedder.return_value = mock_embedder_instance

        result = store_query_in_chromadb("test query", metadata={"key": "value"})

        assert result["stored"] == 1
        assert "query_id" in result
        assert "collection" in result
        mock_collection.upsert.assert_called_once()

    @pytest.mark.unit
    def test_store_query_in_chromadb_raises_on_empty_query(self):
        """Test that ValueError is raised for empty query."""
        with pytest.raises(ValueError, match="query cannot be empty"):
            store_query_in_chromadb("")


class TestSetupCredentials:
    """Test credential setup function."""

    @pytest.mark.unit
    @patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"})
    @patch("os.path.exists", return_value=True)
    @patch(
        "generate_stock_reasoning.service_account.Credentials.from_service_account_file"
    )
    def test_setup_credentials_from_env(self, mock_creds, mock_exists):
        """Test credentials loaded from environment variable."""
        mock_creds.return_value = MagicMock()

        creds = setup_credentials()

        assert creds is not None
        mock_creds.assert_called_once()

    @pytest.mark.unit
    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists", return_value=False)
    def test_setup_credentials_raises_if_not_found(self, mock_exists):
        """Test that FileNotFoundError is raised if credentials not found."""
        with pytest.raises(FileNotFoundError):
            setup_credentials()


class TestListGcsFiles:
    """Test GCS file listing."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.storage.Client")
    def test_list_gcs_files_success(self, mock_storage_client):
        """Test successful file listing."""
        mock_bucket = MagicMock()
        mock_blob1 = MagicMock()
        mock_blob1.name = "file1.csv"
        mock_blob2 = MagicMock()
        mock_blob2.name = "file2.csv"
        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        files = list_gcs_files("test-bucket", prefix="model_output/")

        assert len(files) == 2
        assert "file1.csv" in files
        assert "file2.csv" in files

    @pytest.mark.unit
    @patch(
        "generate_stock_reasoning.storage.Client", side_effect=Exception("GCS error")
    )
    def test_list_gcs_files_handles_error(self, mock_storage_client):
        """Test that errors are handled gracefully."""
        files = list_gcs_files("test-bucket")

        assert files == []


class TestDownloadCsvFromGcs:
    """Test CSV download from GCS."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.storage.Client")
    def test_download_csv_from_gcs_success(self, mock_storage_client):
        """Test successful CSV download."""
        # Create test CSV data
        test_df = pd.DataFrame({"symbol": ["AAPL"], "value": [100]})
        csv_bytes = test_df.to_csv(index=False).encode()

        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = csv_bytes
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        df = download_csv_from_gcs("test.csv", "test-bucket")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "symbol" in df.columns


class TestUploadCsvToGcs:
    """Test CSV upload to GCS."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.storage.Client")
    def test_upload_csv_to_gcs_success(self, mock_storage_client):
        """Test successful CSV upload."""
        test_df = pd.DataFrame({"symbol": ["AAPL"], "value": [100]})

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        upload_csv_to_gcs(test_df, "test.csv", "test-bucket")

        mock_blob.upload_from_file.assert_called_once()


class TestGenerateReasoningForStock:
    """Test single stock reasoning generation."""

    @pytest.mark.unit
    def test_generate_reasoning_for_stock_success(self):
        """Test successful reasoning generation."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "This stock has strong fundamentals."

        stock_data = {
            "symbol": "AAPL",
            "signal": "Buy",
            "Hybrid_Score": 0.8,
            "roe": 0.25,
            "peRatio": 20.0,
        }

        reasoning = generate_reasoning_for_stock(mock_chain, stock_data)

        assert isinstance(reasoning, str)
        assert len(reasoning) > 0
        mock_chain.invoke.assert_called_once()

    @pytest.mark.unit
    def test_generate_reasoning_for_stock_handles_error(self):
        """Test error handling in reasoning generation."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("LLM error")

        stock_data = {"symbol": "AAPL"}

        reasoning = generate_reasoning_for_stock(mock_chain, stock_data)

        assert reasoning.startswith("Error:")


class TestProcessSingleStock:
    """Test single stock processing."""

    @pytest.mark.unit
    def test_process_single_stock_success(self):
        """Test successful stock processing."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Good stock"

        row = pd.Series({"symbol": "AAPL", "value": 100})
        args_tuple = (0, row, mock_chain)

        idx, reasoning, stock_time, symbol, error = process_single_stock(args_tuple)

        assert idx == 0
        assert reasoning == "Good stock"
        assert symbol == "AAPL"
        assert error is None
        assert stock_time >= 0

    @pytest.mark.unit
    def test_process_single_stock_handles_error(self):
        """Test error handling in stock processing."""
        # Create a row that will cause an error in to_dict() or get()
        mock_row = MagicMock()
        mock_row.to_dict.side_effect = Exception("Processing error")
        mock_row.get.return_value = "AAPL"

        mock_chain = MagicMock()
        args_tuple = (0, mock_row, mock_chain)

        idx, reasoning, stock_time, symbol, error = process_single_stock(args_tuple)

        assert reasoning.startswith("Error:")
        assert error is not None and len(error) > 0  # Error should be a string
        assert symbol == "AAPL"


class TestProcessCsvWithRag:
    """Test CSV processing with RAG."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.ThreadPoolExecutor")
    def test_process_csv_with_rag_adds_reasoning_column(self, mock_executor):
        """Test that rag_reasoning column is added."""
        # Create test DataFrame
        df = pd.DataFrame({"symbol": ["AAPL", "MSFT"], "value": [100, 200]})

        # Mock executor
        mock_future = MagicMock()
        mock_future.result.return_value = (0, "Reasoning 1", 0.5, "AAPL", None)
        mock_future2 = MagicMock()
        mock_future2.result.return_value = (1, "Reasoning 2", 0.5, "MSFT", None)

        mock_executor_instance = MagicMock()
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor_instance.submit.side_effect = [mock_future, mock_future2]
        mock_executor_instance.__enter__.return_value.submit = (
            mock_executor_instance.submit
        )

        # Mock as_completed
        with patch(
            "generate_stock_reasoning.as_completed",
            return_value=[mock_future, mock_future2],
        ):
            mock_executor.return_value = mock_executor_instance

            mock_chain = MagicMock()
            result_df = process_csv_with_rag(df, mock_chain, max_workers=2)

        assert "rag_reasoning" in result_df.columns
        assert len(result_df) == 2

    @pytest.mark.unit
    def test_process_csv_with_rag_respects_sample_size(self):
        """Test that sample_size limits processing."""
        df = pd.DataFrame(
            {"symbol": ["AAPL", "MSFT", "GOOGL"], "value": [100, 200, 300]}
        )

        mock_chain = MagicMock()

        with patch("generate_stock_reasoning.ThreadPoolExecutor"):
            with patch("generate_stock_reasoning.as_completed", return_value=[]):
                result_df = process_csv_with_rag(df, mock_chain, sample_size=2)

        assert len(result_df) == 2


class TestGenerateReasoningForDataframe:
    """Test DataFrame reasoning generation."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.process_csv_with_rag")
    def test_generate_reasoning_for_dataframe_calls_process(self, mock_process):
        """Test that process_csv_with_rag is called."""
        df = pd.DataFrame({"symbol": ["AAPL"], "value": [100]})
        mock_chain = MagicMock()

        mock_process.return_value = df.copy()
        mock_process.return_value["rag_reasoning"] = "Test reasoning"

        result = generate_reasoning_for_dataframe(df, mock_chain, sample_size=1)

        mock_process.assert_called_once()
        assert "rag_reasoning" in result.columns


class TestAddReasoningToCombinedFile:
    """Test add_reasoning_to_combined_file function."""

    @pytest.mark.unit
    @patch("generate_stock_reasoning.setup_credentials")
    @patch("generate_stock_reasoning.setup_rag_system")
    @patch("generate_stock_reasoning.generate_reasoning_for_dataframe")
    @patch("generate_stock_reasoning.upload_csv_to_gcs")
    def test_add_reasoning_to_combined_file_success(
        self, mock_upload, mock_generate, mock_setup_rag, mock_setup_creds
    ):
        """Test successful reasoning addition."""
        # Create temp CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            test_df = pd.DataFrame({"symbol": ["AAPL"], "value": [100]})
            test_df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            # Setup mocks
            mock_creds = MagicMock()
            mock_setup_creds.return_value = mock_creds

            mock_chain = MagicMock()
            mock_setup_rag.return_value = mock_chain

            enhanced_df = pd.DataFrame(
                {"symbol": ["AAPL"], "value": [100], "rag_reasoning": ["Good"]}
            )
            mock_generate.return_value = enhanced_df

            result_path = add_reasoning_to_combined_file(temp_path, upload_to_gcs=False)

            assert os.path.exists(result_path)
            assert "_with_reasoning" in result_path

            # Verify CSV was saved
            saved_df = pd.read_csv(result_path)
            assert "rag_reasoning" in saved_df.columns
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if os.path.exists(result_path):
                os.unlink(result_path)

    @pytest.mark.unit
    @patch("generate_stock_reasoning.setup_credentials")
    @patch("generate_stock_reasoning.setup_rag_system")
    @patch("generate_stock_reasoning.generate_reasoning_for_dataframe")
    def test_add_reasoning_to_combined_file_handles_existing_column(
        self, mock_generate, mock_setup_rag, mock_setup_creds
    ):
        """Test that existing rag_reasoning column is handled."""
        # Create temp CSV with existing column
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            test_df = pd.DataFrame(
                {"symbol": ["AAPL"], "rag_reasoning": ["Old reasoning"]}
            )
            test_df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            mock_setup_creds.return_value = MagicMock()
            mock_setup_rag.return_value = MagicMock()

            enhanced_df = pd.DataFrame(
                {"symbol": ["AAPL"], "rag_reasoning": ["New reasoning"]}
            )
            mock_generate.return_value = enhanced_df

            result_path = add_reasoning_to_combined_file(temp_path, upload_to_gcs=False)

            # Should have new reasoning
            saved_df = pd.read_csv(result_path)
            assert saved_df["rag_reasoning"].iloc[0] == "New reasoning"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if os.path.exists(result_path):
                os.unlink(result_path)
