"""
Unit tests for GCS bucket utilities.
"""

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit
import pandas as pd
from io import BytesIO


class TestGetGcsData:
    """Tests for get_gcs_data function."""

    def test_csv_data_retrieval_success(self, mock_gcs_client):
        """Test successful CSV data retrieval from GCS."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client

        csv_data = b"symbol,price,volume\nAAPL,150.0,1000000\nGOOGL,140.0,500000"
        mock_blob.download_as_bytes.return_value = csv_data

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            result = get_gcs_data("test.csv", storage_client=mock_client)

            assert result is not None
            assert len(result) == 2
            assert "symbol" in result.columns

    def test_parquet_data_retrieval_success(self, mock_gcs_client):
        """Test successful Parquet data retrieval from GCS."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client

        df = pd.DataFrame({"symbol": ["AAPL", "GOOGL"], "price": [150.0, 140.0]})
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer)
        parquet_bytes = parquet_buffer.getvalue()

        mock_blob.download_as_bytes.return_value = parquet_bytes

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            result = get_gcs_data("test.parquet", file_type="parquet", storage_client=mock_client)

            assert result is not None
            assert len(result) == 2

    def test_client_not_initialized_returns_none(self):
        """Test handling when GCS client is not initialized."""
        from api.utils.get_gcs_bucket import get_gcs_data

        result = get_gcs_data("test.csv", storage_client=None)

        assert result is None

    def test_file_not_found_returns_none(self, mock_gcs_client):
        """Test handling when file is not found in GCS."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client
        mock_blob.download_as_bytes.side_effect = Exception("File not found")

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            result = get_gcs_data("nonexistent.csv", storage_client=mock_client)

            assert result is None

    def test_uses_correct_bucket_name(self, mock_gcs_client):
        """Test that correct bucket name is used."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client
        mock_blob.download_as_bytes.return_value = b"col1,col2\na,b"

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            get_gcs_data("test.csv", storage_client=mock_client, bucket_name="test-bucket")

            mock_client.bucket.assert_called_with("test-bucket")

    def test_uses_correct_file_path(self, mock_gcs_client):
        """Test that correct file path is used."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client
        mock_blob.download_as_bytes.return_value = b"col1,col2\na,b"

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            get_gcs_data("model_output/test.csv", storage_client=mock_client)

            mock_bucket.blob.assert_called_with("model_output/test.csv")

    def test_csv_with_multiple_columns(self, mock_gcs_client):
        """Test CSV with multiple columns."""
        mock_client, mock_bucket, mock_blob = mock_gcs_client

        csv_data = b"symbol,price,volume,sector\nAAPL,150.0,1000000,Tech"
        mock_blob.download_as_bytes.return_value = csv_data

        with patch("api.utils.get_gcs_bucket.storage_client", mock_client):
            from api.utils.get_gcs_bucket import get_gcs_data

            result = get_gcs_data("test.csv", storage_client=mock_client)

            assert len(result.columns) == 4
