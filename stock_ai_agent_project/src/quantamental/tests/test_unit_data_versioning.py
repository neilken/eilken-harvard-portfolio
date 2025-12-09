"""
Test suite for data_versioning.py
Tests data versioning with W&B artifacts
"""

import tempfile
import shutil
from pathlib import Path

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from data_versioning import DataVersionManager


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config(temp_data_dir):
    """Create sample configuration"""
    return {
        "data": {"data_dir": temp_data_dir},
        "wandb": {"project": "test-project"},
        "gcs": {"bucket_name": "test-bucket"},
    }


@pytest.fixture
def sample_data_files(temp_data_dir):
    """Create sample data files"""
    # Create ohlcv data
    ohlcv = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 100,
            "date": pd.date_range("2024-01-01", periods=100, freq="D"),
            "open": np.random.uniform(150, 200, 100),
            "high": np.random.uniform(150, 200, 100),
            "low": np.random.uniform(150, 200, 100),
            "close": np.random.uniform(150, 200, 100),
            "volume": np.random.randint(1000000, 10000000, 100),
        }
    )
    ohlcv.to_parquet(f"{temp_data_dir}/ohlcv_raw.parquet")

    # Create sp500 data
    sp500 = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=100, freq="D"),
            "close": np.random.uniform(4000, 4500, 100),
        }
    )
    sp500.to_parquet(f"{temp_data_dir}/sp500_index.parquet")

    # Create fundamentals data
    fundamentals = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 50,
            "date": pd.date_range("2024-01-01", periods=50, freq="D"),
            "roe": np.random.uniform(0.1, 0.3, 50),
            "peRatio": np.random.uniform(15, 25, 50),
        }
    )
    fundamentals.to_parquet(f"{temp_data_dir}/fundamentals_combined.parquet")

    # Create output files
    output = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 10,
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "pred_prob": np.random.uniform(0, 1, 10),
            "Hybrid_Score": np.random.uniform(0, 1, 10),
        }
    )
    output.to_csv(
        f"{temp_data_dir}/combined_quantamental_hybrid_with_factors_and_backtest.csv",
        index=False,
    )

    profiles = pd.DataFrame(
        {"symbol": ["AAPL", "GOOGL"], "companyName": ["Apple Inc", "Alphabet Inc"]}
    )
    profiles.to_csv(f"{temp_data_dir}/company_profiles.csv", index=False)

    equity = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "equity_value": np.random.uniform(90, 110, 5),
        }
    )
    equity.to_csv(f"{temp_data_dir}/all_equity_curves.csv", index=False)

    return temp_data_dir


class TestDataVersionManager:
    """Test DataVersionManager initialization and basic methods"""

    @pytest.mark.unit
    def test_init_with_config(self, sample_config):
        """Test initialization with config"""
        with patch("data_versioning.HAS_GCS", False):
            manager = DataVersionManager(sample_config)

            assert manager.data_dir == sample_config["data"]["data_dir"]
            assert manager.wandb_project == sample_config["wandb"]["project"]

    @pytest.mark.unit
    def test_init_with_gcs_available(self, sample_config):
        """Test initialization when GCS is available"""
        with patch("data_versioning.HAS_GCS", True):
            with patch("data_versioning.storage.Client") as mock_client:
                mock_bucket = MagicMock()
                mock_client.return_value.bucket.return_value = mock_bucket

                manager = DataVersionManager(sample_config)

                assert manager.gcs_client is not None
                assert manager.gcs_bucket is not None

    @pytest.mark.unit
    def test_init_with_gcs_error(self, sample_config):
        """Test initialization when GCS fails"""
        with patch("data_versioning.HAS_GCS", True):
            with patch(
                "data_versioning.storage.Client", side_effect=Exception("GCS error")
            ):
                manager = DataVersionManager(sample_config)

                assert manager.gcs_client is None
                assert manager.gcs_bucket is None

    @pytest.mark.unit
    def test_save_input_data_snapshot_basic(self, sample_config, sample_data_files):
        """Test saving input data snapshot"""
        with patch("data_versioning.HAS_GCS", False):
            with patch("wandb.init") as mock_wandb_init:
                with patch("wandb.Artifact") as mock_artifact:
                    mock_run = MagicMock()
                    mock_wandb_init.return_value = mock_run
                    mock_artifact_instance = MagicMock()
                    mock_artifact.return_value = mock_artifact_instance

                    manager = DataVersionManager(sample_config)

                    result = manager.save_input_data_snapshot(
                        f"{sample_data_files}/ohlcv_raw.parquet",
                        f"{sample_data_files}/sp500_index.parquet",
                        version_tag="test_v1",
                    )

                    assert result["version_tag"] == "test_v1"
                    assert "timestamp" in result
                    assert "files" in result

    def test_init_without_gcs(self, sample_config):
        """Test initialization without GCS"""
        with patch("data_versioning.HAS_GCS", False):
            manager = DataVersionManager(sample_config)

            assert manager.gcs_client is None
            assert manager.gcs_bucket is None


class TestVersioning:
    """Test versioning functionality"""

    @patch("data_versioning.wandb")
    def test_create_version_snapshot_structure(
        self, mock_wandb, sample_config, sample_data_files
    ):
        """Test version snapshot creates correct structure"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Check structure
        assert "version_tag" in result
        assert "timestamp" in result
        assert "methods" in result
        assert "input_files" in result
        assert "output_files" in result
        assert result["version_tag"] == "test"

    @patch("data_versioning.wandb")
    def test_versions_input_files(self, mock_wandb, sample_config, sample_data_files):
        """Test input files are versioned"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Check input files
        assert "ohlcv_raw" in result["input_files"]
        assert "sp500_index" in result["input_files"]
        assert "fundamentals" in result["input_files"]

    @patch("data_versioning.wandb")
    def test_versions_output_files(self, mock_wandb, sample_config, sample_data_files):
        """Test output files are versioned"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Check output files
        assert "combined_quantamental" in result["output_files"]
        assert "company_profiles" in result["output_files"]
        assert "equity_curves" in result["output_files"]

    @patch("data_versioning.wandb")
    def test_creates_wandb_artifacts(
        self, mock_wandb, sample_config, sample_data_files
    ):
        """Test W&B artifacts are created"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run
        mock_wandb.Artifact = MagicMock()

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Should create 6 artifacts (3 inputs + 3 outputs)
        assert mock_run.log_artifact.call_count == 6

    @patch("data_versioning.wandb")
    def test_saves_local_snapshot(self, mock_wandb, sample_config, sample_data_files):
        """Test local JSON snapshot is saved"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            manager.create_version_snapshot(
                version_tag="test_v1"
            )  # Test that it doesn't raise

        # Check JSON file was created
        json_file = (
            Path(sample_config["data"]["data_dir"]) / "version_info_test_v1.json"
        )
        assert json_file.exists()

    @patch("data_versioning.wandb")
    def test_handles_missing_files_gracefully(
        self, mock_wandb, sample_config, temp_data_dir
    ):
        """Test handles missing files without crashing"""
        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Should complete without crashing
        assert "version_tag" in result
        assert result["status"] == "success"


class TestMetadata:
    """Test metadata extraction"""

    @patch("data_versioning.wandb")
    def test_extracts_row_count(self, mock_wandb, sample_config, sample_data_files):
        """Test row count is extracted"""
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Check metadata
        assert "rows" in result["input_files"]["ohlcv_raw"]
        assert result["input_files"]["ohlcv_raw"]["rows"] == 100

    @patch("data_versioning.wandb")
    def test_extracts_file_size(self, mock_wandb, sample_config, sample_data_files):
        """Test file size is extracted"""
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 0
        mock_run.log_artifact.return_value = mock_artifact

        manager = DataVersionManager(sample_config)

        with patch.object(manager, "gcs_client", None):
            result = manager.create_version_snapshot(version_tag="test")

        # Check file size exists
        assert "file_size_mb" in result["input_files"]["ohlcv_raw"]
        assert result["input_files"]["ohlcv_raw"]["file_size_mb"] > 0


class TestErrorHandling:
    """Test error handling"""

    def test_handles_corrupt_file(self, sample_config, temp_data_dir):
        """Test handles corrupt data files"""
        # Create corrupt file
        with open(f"{temp_data_dir}/ohlcv_raw.parquet", "w") as f:
            f.write("corrupt data")

        with patch("data_versioning.wandb") as mock_wandb:
            mock_run = MagicMock()
            mock_wandb.init.return_value = mock_run

            manager = DataVersionManager(sample_config)

            with patch.object(manager, "gcs_client", None):
                result = manager.create_version_snapshot(version_tag="test")

            # Should handle error gracefully
            assert "error" in result["input_files"]["ohlcv_raw"]


class TestVersioningMethods:
    """Test individual versioning methods."""

    @pytest.mark.unit
    @patch("data_versioning.wandb")
    def test_version_with_wandb(self, mock_wandb, sample_config, sample_data_files):
        """Test version_with_wandb creates W&B artifacts."""
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        mock_artifact = MagicMock()
        mock_artifact.version = 1
        mock_run.log_artifact.return_value = mock_artifact
        mock_wandb.Artifact = MagicMock(return_value=mock_artifact)

        manager = DataVersionManager(sample_config)

        result = manager.version_with_wandb(
            f"{sample_data_files}/ohlcv_raw.parquet",
            f"{sample_data_files}/sp500_index.parquet",
            version_tag="test_v1",
        )

        assert result == "test_v1"
        mock_wandb.init.assert_called_once()

    @pytest.mark.unit
    def test_version_with_gcs_no_gcs(self, sample_config):
        """Test version_with_gcs returns error when GCS not available."""
        with patch("data_versioning.HAS_GCS", False):
            manager = DataVersionManager(sample_config)

            result = manager.version_with_gcs(
                "test_ohlcv.parquet", "test_sp500.parquet", version_tag="test"
            )

            assert "error" in result

    @pytest.mark.unit
    def test_save_input_data_snapshot_metadata(self, sample_config, sample_data_files):
        """Test save_input_data_snapshot extracts metadata correctly."""
        manager = DataVersionManager(sample_config)

        result = manager.save_input_data_snapshot(
            f"{sample_data_files}/ohlcv_raw.parquet",
            f"{sample_data_files}/sp500_index.parquet",
            fundamentals_path=f"{sample_data_files}/fundamentals_combined.parquet",
            version_tag="test_v1",
        )

        assert result["version_tag"] == "test_v1"
        assert "timestamp" in result
        assert "files" in result
        assert "ohlcv_raw" in result["files"]
        assert "sp500_index" in result["files"]
        assert "fundamentals" in result["files"]

        # Check metadata structure
        ohlcv_meta = result["files"]["ohlcv_raw"]
        assert "rows" in ohlcv_meta
        assert "columns" in ohlcv_meta
        assert ohlcv_meta["rows"] == 100  # From sample_data_files fixture


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
