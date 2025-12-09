"""
Additional tests to boost coverage to 50%+.
Based on actual code structure.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestModelTrainCoverage:
    """Tests for model_train.py"""

    @pytest.mark.unit
    def test_trainer_init(self):
        """Test QuantamentalTrainer initialization"""
        from model_train import QuantamentalTrainer

        config = {
            "data": {"data_dir": "./data"},
            "model": {
                "hyperparameters": {
                    "n_estimators": 10,
                    "max_depth": 3,
                    "random_state": 42,
                    "class_weight": "balanced",
                },
                "train_window_months": 12,
            },
            "wandb": {"project": "test", "entity": None, "tags": []},
            "features": {"technical": ["return_1m"], "fundamental": ["roe"]},
        }

        trainer = QuantamentalTrainer(config)
        assert trainer is not None
        assert trainer.config == config
        assert trainer.data_dir == "./data"

    @pytest.mark.unit
    def test_trainer_feature_names(self):
        """Test trainer has feature names"""
        from model_train import QuantamentalTrainer

        config = {
            "data": {"data_dir": "./data"},
            "model": {
                "hyperparameters": {
                    "n_estimators": 100,
                    "max_depth": 5,
                    "random_state": 42,
                    "class_weight": "balanced",
                },
                "train_window_months": 12,
            },
            "wandb": {"project": "test", "entity": None, "tags": []},
            "features": {
                "technical": ["return_1m", "RSI_14"],
                "fundamental": ["roe", "peRatio"],
            },
        }

        trainer = QuantamentalTrainer(config)
        assert hasattr(trainer, "feature_names")
        assert hasattr(trainer, "tech_cols")
        assert hasattr(trainer, "fund_cols")


class TestModelPredictCoverage:
    """Tests for model_predict.py"""

    @pytest.mark.unit
    def test_predictor_init(self):
        """Test QuantamentalPredictor initialization"""
        from model_predict import QuantamentalPredictor

        config = {
            "data": {"data_dir": "./data"},
            "model": {"hyperparameters": {}, "train_window_months": 12},
            "wandb": {"project": "test", "entity": None},
            "features": {"technical": ["return_1m"], "fundamental": ["roe"]},
        }

        predictor = QuantamentalPredictor(config)
        assert predictor is not None

    @pytest.mark.unit
    def test_predictor_has_config(self):
        """Test predictor stores config"""
        from model_predict import QuantamentalPredictor

        config = {
            "data": {"data_dir": "./test_data"},
            "model": {"hyperparameters": {}, "train_window_months": 6},
            "wandb": {"project": "test-project", "entity": None},
            "features": {"technical": ["return_1m"], "fundamental": ["roe"]},
        }

        predictor = QuantamentalPredictor(config)
        assert predictor.config["data"]["data_dir"] == "./test_data"


class TestDataCollectCoverage:
    """Tests for data_collect.py"""

    @pytest.mark.unit
    def test_collector_init(self):
        """Test FMPDataCollector initialization"""
        from data_collect import FMPDataCollector

        config = {
            "api": {
                "fmp_api_key": "test_key",
                "base_url": "https://test.com",
                "concurrency": 2,
                "timeout": 30,
            },
            "data": {
                "data_dir": "./data",
                "start_date": "2023-01-01",
                "end_date": "2024-01-01",
                "cache_enabled": True,
            },
        }

        collector = FMPDataCollector(config)
        assert collector is not None
        assert collector.api_key == "test_key"
        assert collector.base_url == "https://test.com"

    @pytest.mark.unit
    def test_collector_dates(self):
        """Test collector stores dates"""
        from data_collect import FMPDataCollector

        config = {
            "api": {
                "fmp_api_key": "my_api_key",
                "base_url": "https://api.example.com",
                "concurrency": 4,
                "timeout": 60,
            },
            "data": {
                "data_dir": "./my_data",
                "start_date": "2022-06-01",
                "end_date": "2023-06-01",
                "cache_enabled": False,
            },
        }

        collector = FMPDataCollector(config)
        assert collector.start_date == "2022-06-01"
        assert collector.end_date == "2023-06-01"


class TestDataVersioningCoverage:
    """Tests for data_versioning.py"""

    @pytest.mark.unit
    @patch("data_versioning.wandb")
    def test_version_manager_init(self, mock_wandb):
        """Test DataVersionManager initialization"""
        from data_versioning import DataVersionManager

        config = {
            "data": {"data_dir": "./data"},
            "wandb": {"project": "test", "api_key": "test_key", "entity": None},
            "gcs": {"bucket_name": "test-bucket", "output_folder": "output"},
        }

        manager = DataVersionManager(config)
        assert manager is not None
        assert manager.data_dir == "./data"


class TestUtilsCoverage:
    """Tests for utils.py"""

    @pytest.mark.unit
    def test_load_config_returns_dict(self):
        """Test config loading returns dict"""
        from utils import load_config

        config = load_config()
        assert isinstance(config, dict)

    @pytest.mark.unit
    def test_load_config_has_keys(self):
        """Test config has expected keys"""
        from utils import load_config

        config = load_config()
        possible_keys = ["api", "data", "model", "wandb", "gcs", "features"]
        assert any(key in config for key in possible_keys)

    @pytest.mark.unit
    def test_get_feature_list_returns_list(self):
        """Test feature list is a list"""
        from utils import get_feature_list, load_config

        config = load_config()
        features = get_feature_list(config)
        assert isinstance(features, list)
        assert len(features) > 0


class TestBacktestCoverage:
    """Tests for backtest.py - with mocked GCS"""

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    def test_backtester_init(self, mock_gcs_class):
        """Test QuantamentalBacktester initialization"""
        # Mock GCSHandler to avoid credentials error
        mock_gcs_class.return_value = MagicMock()

        from backtest import QuantamentalBacktester

        config = {
            "data": {"data_dir": "./data"},
            "backtest": {
                "top_n_stocks": 10,
                "output_format": "csv",
                "include_metrics": True,
            },
            "gcs": {
                "bucket_name": "test-bucket",
                "output_folder": "output",
                "credentials_path": None,
            },
            "wandb": {"project": "test"},
        }

        backtester = QuantamentalBacktester(config)
        assert backtester is not None
        assert backtester.data_dir == "./data"

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    def test_backtester_output_folder(self, mock_gcs_class):
        """Test backtester stores output folder"""
        mock_gcs_class.return_value = MagicMock()

        from backtest import QuantamentalBacktester

        config = {
            "data": {"data_dir": "./test_data"},
            "backtest": {
                "top_n_stocks": 20,
                "output_format": "parquet",
                "include_metrics": False,
            },
            "gcs": {
                "bucket_name": "my-bucket",
                "output_folder": "results",
                "credentials_path": None,
            },
            "wandb": {"project": "my-project"},
        }

        backtester = QuantamentalBacktester(config)
        assert backtester.output_folder == "results"


class TestDataProcessCoverage:
    """Tests for data_process.py"""

    @pytest.mark.unit
    def test_processor_init(self):
        """Test DataProcessor initialization"""
        from data_process import DataProcessor

        config = {
            "data": {"data_dir": "./data"},
            "features": {"technical": ["return_1m"], "fundamental": ["roe"]},
            "processing": {
                "monthly_snapshot": True,
                "forward_fill_limit": 5,
                "coverage_threshold_ratio": 0.9,
            },
        }

        processor = DataProcessor(config)
        assert processor is not None

    @pytest.mark.unit
    def test_processor_has_config(self):
        """Test processor stores config"""
        from data_process import DataProcessor

        config = {
            "data": {"data_dir": "./my_data"},
            "features": {
                "technical": ["return_1m", "RSI_14"],
                "fundamental": ["roe", "peRatio"],
            },
            "processing": {
                "monthly_snapshot": False,
                "forward_fill_limit": 3,
                "coverage_threshold_ratio": 0.8,
            },
        }

        processor = DataProcessor(config)
        assert processor.config["data"]["data_dir"] == "./my_data"
