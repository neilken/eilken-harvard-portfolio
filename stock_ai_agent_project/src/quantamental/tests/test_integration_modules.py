"""
INTEGRATION TESTS - Module Interactions
Tests how different modules work together
"""

import sys
import os

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_collect import FMPDataCollector
from data_process import DataProcessor
from utils import load_config


class TestModuleImports:
    """Integration tests for module imports and basic structure."""

    @pytest.mark.integration
    def test_all_modules_import_successfully(self):
        """Test that all modules can be imported."""
        import utils
        import data_collect
        import data_process
        import model_train
        import model_predict
        import backtest
        import main

        # All modules should import without errors
        assert utils is not None
        assert data_collect is not None
        assert data_process is not None
        assert model_train is not None
        assert model_predict is not None
        assert backtest is not None
        assert main is not None

    @pytest.mark.integration
    def test_utils_module_structure(self):
        """Test utils module has expected functions."""
        import utils

        assert hasattr(utils, "load_config")
        assert hasattr(utils, "get_feature_list")
        assert hasattr(utils, "ensure_dir")
        assert hasattr(utils, "get_timestamp_suffix")
        assert hasattr(utils, "GCSHandler")

    @pytest.mark.integration
    def test_data_collect_module_structure(self):
        """Test data_collect module has expected classes."""
        import data_collect

        assert hasattr(data_collect, "FMPDataCollector")

    @pytest.mark.integration
    def test_data_process_module_structure(self):
        """Test data_process module has expected classes."""
        import data_process

        assert hasattr(data_process, "DataProcessor")
        assert hasattr(data_process, "main")

    @pytest.mark.integration
    def test_backtest_module_structure(self):
        """Test backtest module has main function."""
        import backtest

        assert hasattr(backtest, "main")


class TestPythonPackages:
    """Integration tests for required Python packages."""

    @pytest.mark.integration
    def test_pandas_installed_and_working(self):
        """Test pandas is installed and works."""
        import pandas as pd

        assert pd.__version__ is not None

        # Test basic DataFrame creation
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert len(df) == 3

    @pytest.mark.integration
    def test_numpy_installed_and_working(self):
        """Test numpy is installed and works."""
        import numpy as np

        assert np.__version__ is not None

        # Test basic array operations
        arr = np.array([1, 2, 3])
        assert len(arr) == 3
        assert arr.mean() == 2.0

    @pytest.mark.integration
    def test_sklearn_installed(self):
        """Test scikit-learn is installed."""
        import sklearn

        assert sklearn.__version__ is not None

    @pytest.mark.integration
    def test_wandb_installed(self):
        """Test W&B is installed."""
        import wandb

        assert wandb.__version__ is not None


class TestConfigToModules:
    """Integration tests for config loading and module initialization."""

    @pytest.mark.integration
    def test_config_loads_and_creates_collector(self):
        """Test that config loads and can initialize FMPDataCollector."""
        config = load_config()
        collector = FMPDataCollector(config)

        # Collector should be properly initialized from config
        assert collector.api_key is not None
        assert collector.base_url is not None
        assert collector.start_date is not None
        assert collector.end_date is not None
        assert collector.data_dir is not None

    @pytest.mark.integration
    def test_config_loads_and_creates_processor(self):
        """Test that config loads and can initialize DataProcessor."""
        config = load_config()
        processor = DataProcessor(config)

        # Processor should be properly initialized from config
        assert processor.config is not None
        assert processor.data_dir is not None
        assert len(processor.fund_cols) > 0

    @pytest.mark.integration
    def test_config_provides_all_required_keys_for_collector(self):
        """Test that config has all keys required by FMPDataCollector."""
        config = load_config()

        # Required for FMPDataCollector
        assert "api" in config
        assert "fmp_api_key" in config["api"]
        assert "base_url" in config["api"]
        assert "concurrency" in config["api"]
        assert "timeout" in config["api"]

        assert "data" in config
        assert "start_date" in config["data"]
        assert "end_date" in config["data"]
        assert "data_dir" in config["data"]

    @pytest.mark.integration
    def test_config_provides_all_required_keys_for_processor(self):
        """Test that config has all keys required by DataProcessor."""
        config = load_config()

        # Required for DataProcessor
        assert "features" in config
        assert "technical" in config["features"]
        assert "fundamental" in config["features"]

        assert "processing" in config
        assert isinstance(config["processing"], dict)

    @pytest.mark.integration
    def test_data_directory_consistency_across_modules(self):
        """Test that data directory is consistent across modules."""
        config = load_config()

        collector = FMPDataCollector(config)
        processor = DataProcessor(config)

        # Should use same data directory
        assert collector.data_dir == processor.data_dir


class TestDataStructureCompatibility:
    """Integration tests for data structure compatibility between modules."""

    @pytest.mark.integration
    def test_ohlcv_structure_matches_processor_expectations(self):
        """Test that OHLCV data structure from collector matches processor expectations."""
        # Create mock OHLCV data as collector would produce
        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 30,
                "date": pd.date_range("2023-01-01", periods=30),
                "open": np.random.uniform(140, 160, 30),
                "high": np.random.uniform(145, 165, 30),
                "low": np.random.uniform(135, 155, 30),
                "close": np.random.uniform(140, 160, 30),
                "adj_close": np.random.uniform(140, 160, 30),
                "volume": np.random.uniform(1000000, 2000000, 30),
            }
        )

        # Processor should be able to compute technicals
        config = load_config()
        processor = DataProcessor(config)

        result = processor.compute_technicals(ohlcv)

        # Should successfully add technical indicators
        assert len(result) == 30
        assert "return_1d" in result.columns
        assert "ema_12" in result.columns
        assert "macd" in result.columns

    @pytest.mark.integration
    def test_fundamentals_structure_compatible_with_merge(self):
        """Test fundamentals data structure is compatible with merging."""
        config = load_config()
        processor = DataProcessor(config)

        # Create compatible datasets
        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 60,
                "date": pd.date_range("2023-01-01", periods=60),
                "close": np.random.uniform(140, 160, 60),
                "return_1m": np.random.uniform(-0.05, 0.05, 60),
            }
        )

        fundamentals = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 4,
                "date": pd.to_datetime(
                    ["2023-01-01", "2023-01-15", "2023-01-30", "2023-02-15"]
                ),
                "revenue": [100000, 105000, 103000, 108000],
            }
        )

        processor.fund_cols = ["revenue"]

        # Should merge successfully
        result = processor.merge_fundamentals(ohlcv, fundamentals)

        assert len(result) > 0
        assert "symbol" in result.columns
        assert "revenue" in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
