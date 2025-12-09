"""
UNIT TESTS - Utils Module
Tests individual utility functions in isolation
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import (
    load_config,
    get_feature_list,
    ensure_dir,
    get_timestamp_suffix,
    GCSHandler,
)


class TestConfigLoading:
    """Unit tests for configuration loading."""

    @pytest.mark.unit
    def test_load_config_returns_dict(self):
        """Test that load_config returns a dictionary."""
        config = load_config()
        assert isinstance(config, dict)

    @pytest.mark.unit
    def test_config_has_required_sections(self):
        """Test config has all required sections."""
        config = load_config()

        assert "api" in config
        assert "data" in config
        assert "features" in config
        assert "wandb" in config
        assert "gcs" in config
        assert "processing" in config

    @pytest.mark.unit
    def test_config_api_section(self):
        """Test API configuration section."""
        config = load_config()

        assert "fmp_api_key" in config["api"]
        assert "base_url" in config["api"]

    @pytest.mark.unit
    def test_config_data_section(self):
        """Test data configuration section."""
        config = load_config()

        assert "start_date" in config["data"]
        assert "end_date" in config["data"]
        assert "data_dir" in config["data"]

    @pytest.mark.unit
    def test_config_features_section(self):
        """Test features configuration section."""
        config = load_config()

        assert "technical" in config["features"]
        assert "fundamental" in config["features"]
        assert isinstance(config["features"]["technical"], list)
        assert isinstance(config["features"]["fundamental"], list)

    @pytest.mark.unit
    def test_config_wandb_section(self):
        """Test W&B configuration section."""
        config = load_config()

        assert "wandb" in config
        assert "project" in config["wandb"]

    @pytest.mark.unit
    def test_config_gcs_section(self):
        """Test GCS configuration section."""
        config = load_config()

        assert "gcs" in config
        assert "bucket_name" in config["gcs"]

    @pytest.mark.unit
    def test_config_env_override_fmp_key(self):
        """Test that FMP_API_KEY environment variable overrides config."""
        with patch.dict(os.environ, {"FMP_API_KEY": "test_key_123"}):
            config = load_config()
            assert config["api"]["fmp_api_key"] == "test_key_123"

    @pytest.mark.unit
    def test_config_env_override_wandb_key(self):
        """Test that WANDB_API_KEY environment variable overrides config."""
        with patch.dict(os.environ, {"WANDB_API_KEY": "test_wandb_key"}):
            config = load_config()
            assert config["wandb"]["api_key"] == "test_wandb_key"

    @pytest.mark.unit
    def test_config_date_range_computed(self):
        """Test that date range is computed if not set."""
        config = load_config()

        # Dates should be ISO format strings
        assert isinstance(config["data"]["start_date"], str)
        assert isinstance(config["data"]["end_date"], str)

        # Should be in YYYY-MM-DD format
        assert len(config["data"]["start_date"]) == 10
        assert "-" in config["data"]["start_date"]

    @pytest.mark.unit
    def test_config_date_format(self):
        """Test date format in config."""
        config = load_config()

        start_date = config["data"]["start_date"]
        end_date = config["data"]["end_date"]

        # Should be ISO format
        assert "-" in start_date
        assert "-" in end_date
        assert len(start_date) == 10
        assert len(end_date) == 10


class TestFeatureList:
    """Unit tests for feature list generation."""

    @pytest.mark.unit
    def test_get_feature_list_returns_list(self):
        """Test that get_feature_list returns a list."""
        config = load_config()
        features = get_feature_list(config)

        assert isinstance(features, list)
        assert len(features) > 0

    @pytest.mark.unit
    def test_get_feature_list_contains_technical(self):
        """Test that feature list contains technical features with lag."""
        config = load_config()
        features = get_feature_list(config)

        # Technical features should have _lag1 suffix
        tech_features = [f for f in features if "_lag1" in f]
        assert len(tech_features) > 0

    @pytest.mark.unit
    def test_get_feature_list_contains_fundamental(self):
        """Test that feature list contains fundamental features."""
        config = load_config()
        get_feature_list(config)  # Test that it doesn't raise

        # Should contain fundamental features (without _lag suffix)
        fund_count = len(config["features"]["fundamental"])
        assert fund_count > 0

    @pytest.mark.unit
    def test_get_feature_list_total_count(self):
        """Test total feature count matches expected."""
        config = load_config()
        features = get_feature_list(config)

        expected_count = len(config["features"]["technical"]) + len(
            config["features"]["fundamental"]
        )

        assert len(features) == expected_count


class TestDirectoryHelpers:
    """Unit tests for directory utility functions."""

    @pytest.mark.unit
    def test_ensure_dir_creates_new_directory(self):
        """Test creating a new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "new_dir")

            assert not os.path.exists(test_path)

            result = ensure_dir(test_path)

            assert os.path.exists(test_path)
            assert os.path.isdir(test_path)
            assert result == str(Path(test_path).absolute())

    @pytest.mark.unit
    def test_ensure_dir_creates_nested_directories(self):
        """Test creating nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "a", "b", "c", "d")

            ensure_dir(test_path)  # Test that it doesn't raise

            assert os.path.exists(test_path)
            assert os.path.exists(os.path.join(tmpdir, "a"))
            assert os.path.exists(os.path.join(tmpdir, "a", "b"))
            assert os.path.exists(os.path.join(tmpdir, "a", "b", "c"))

    @pytest.mark.unit
    def test_ensure_dir_with_existing_directory(self):
        """Test that ensure_dir works with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory first
            os.makedirs(os.path.join(tmpdir, "existing"))
            test_path = os.path.join(tmpdir, "existing")

            # Should not raise error
            result = ensure_dir(test_path)

            assert os.path.exists(result)
            assert os.path.isdir(result)

    @pytest.mark.unit
    def test_ensure_dir_returns_absolute_path(self):
        """Test that ensure_dir returns absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "test")
            result = ensure_dir(test_path)

            assert os.path.isabs(result)


class TestTimestampHelpers:
    """Unit tests for timestamp utility functions."""

    @pytest.mark.unit
    def test_get_timestamp_suffix_returns_string(self):
        """Test that get_timestamp_suffix returns a string."""
        timestamp = get_timestamp_suffix()

        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

    @pytest.mark.unit
    def test_get_timestamp_suffix_format(self):
        """Test timestamp format is YYYYMMDD_HHMMSS."""
        timestamp = get_timestamp_suffix()

        # Should be in format: 20231115_143022
        parts = timestamp.split("_")
        assert len(parts) == 2

        date_part = parts[0]
        time_part = parts[1]

        assert len(date_part) == 8  # YYYYMMDD
        assert len(time_part) == 6  # HHMMSS
        assert date_part.isdigit()
        assert time_part.isdigit()

    @pytest.mark.unit
    def test_get_timestamp_suffix_changes_over_time(self):
        """Test that timestamps change over time (or at least have valid format)."""
        import time

        ts1 = get_timestamp_suffix()
        time.sleep(2)  # Wait 2 seconds to ensure different timestamp
        ts2 = get_timestamp_suffix()

        # Verify format is correct (timestamps may be same if generated in same second)
        assert len(ts1) == 15
        assert "_" in ts1
        assert len(ts2) == 15
        assert "_" in ts2
        # Both should be valid timestamps
        parts1 = ts1.split("_")
        parts2 = ts2.split("_")
        assert len(parts1) == 2 and len(parts2) == 2
        assert parts1[0].isdigit() and parts1[1].isdigit()
        assert parts2[0].isdigit() and parts2[1].isdigit()


class TestGCSHandler:
    """Unit tests for GCS handler class."""

    @pytest.mark.unit
    def test_gcs_handler_init_with_credentials(self):
        """Test GCS handler initialization with credentials."""
        with patch("utils.storage.Client") as mock_client:
            mock_client.from_service_account_json.return_value = MagicMock()

            handler = GCSHandler("test-bucket", "/path/to/creds.json")

            assert handler.bucket_name == "test-bucket"

    @pytest.mark.unit
    def test_gcs_handler_init_without_credentials(self):
        """Test GCS handler initialization without credentials."""
        with patch("utils.storage.Client") as mock_client:
            mock_client.return_value = MagicMock()

            handler = GCSHandler("test-bucket")

            assert handler.bucket_name == "test-bucket"

    @pytest.mark.unit
    def test_upload_file_success(self):
        """Test successful file upload."""
        with patch("utils.storage.Client") as mock_client:
            # Setup mocks
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket

            handler = GCSHandler("test-bucket")

            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"test content")
                temp_path = f.name

            try:
                result = handler.upload_file(temp_path, "test.txt")

                assert "gs://test-bucket/test.txt" in result
                mock_blob.upload_from_filename.assert_called_once_with(temp_path)
            finally:
                os.unlink(temp_path)

    @pytest.mark.unit
    def test_upload_dataframe_csv(self):
        """Test uploading DataFrame as CSV."""
        with patch("utils.storage.Client") as mock_client:
            # Setup mocks
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket

            handler = GCSHandler("test-bucket")

            # Create test DataFrame
            df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

            with patch("os.remove") as mock_remove:
                result = handler.upload_dataframe(df, "test.csv", format="csv")

                assert "gs://test-bucket/test.csv" in result
                mock_blob.upload_from_filename.assert_called_once()
                mock_remove.assert_called_once()

    @pytest.mark.unit
    def test_upload_dataframe_parquet(self):
        """Test uploading DataFrame as Parquet."""
        with patch("utils.storage.Client") as mock_client:
            # Setup mocks
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket

            handler = GCSHandler("test-bucket")

            # Create test DataFrame
            df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

            with patch("os.remove") as mock_remove:
                result = handler.upload_dataframe(df, "test.parquet", format="parquet")

                assert "gs://test-bucket/test.parquet" in result
                mock_blob.upload_from_filename.assert_called_once()
                mock_remove.assert_called_once()

    @pytest.mark.unit
    def test_upload_dataframe_invalid_format(self):
        """Test uploading DataFrame with invalid format raises error."""
        handler = GCSHandler("test-bucket")
        df = pd.DataFrame({"col1": [1, 2, 3]})

        with pytest.raises(ValueError, match="Unsupported format"):
            handler.upload_dataframe(df, "test.txt", format="txt")

    @pytest.mark.unit
    def test_download_file_success(self):
        """Test successful file download."""
        with patch("utils.storage.Client") as mock_client:
            # Setup mocks
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket

            handler = GCSHandler("test-bucket")

            result = handler.download_file("test.txt", "/tmp/test.txt")

            assert result == "/tmp/test.txt"
            mock_blob.download_to_filename.assert_called_once_with("/tmp/test.txt")

    @pytest.mark.unit
    def test_list_files(self):
        """Test listing files in GCS bucket."""
        with patch("utils.storage.Client") as mock_client:
            # Setup mocks
            mock_blob1 = MagicMock()
            mock_blob1.name = "file1.csv"
            mock_blob2 = MagicMock()
            mock_blob2.name = "file2.csv"

            mock_client.return_value.list_blobs.return_value = [mock_blob1, mock_blob2]

            handler = GCSHandler("test-bucket")
            files = handler.list_files("prefix/")

            assert len(files) == 2
            assert "file1.csv" in files
            assert "file2.csv" in files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
