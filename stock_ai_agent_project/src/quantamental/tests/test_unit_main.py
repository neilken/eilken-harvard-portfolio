"""
Unit tests for main.py - Pipeline orchestrator functions
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, Mock, AsyncMock
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import (
    run_data_collection,
    run_data_processing,
    run_model_training,
    run_prediction,
    run_backtest,
    run_rag_reasoning,
    run_data_versioning,
    run_full_pipeline,
)
from utils import load_config


@pytest.fixture
def sample_config():
    """Sample configuration for tests."""
    return {
        "api": {
            "fmp_api_key": "test-key",
            "base_url": "https://test.com/api",
            "concurrency": 5,
        },
        "data": {
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "data_dir": "./data",
        },
        "features": {
            "technical": ["return_1m", "RSI_14"],
            "fundamental": ["roe", "roic"],
        },
        "wandb": {"project": "test-project", "entity": "test", "tags": []},
        "gcs": {"bucket_name": "test-bucket", "output_folder": "output"},
        "processing": {"forward_fill_limit": 5},
        "model": {"hyperparameters": {"n_estimators": 10}, "train_window_months": 12},
    }


@pytest.fixture
def sample_data():
    """Sample data dictionary."""
    return {
        "sp500_tickers": ["AAPL", "MSFT"],
        "ohlcv": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "date": pd.to_datetime(["2023-01-01"]),
                "close": [150.0],
            }
        ),
        "fundamentals": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "date": pd.to_datetime(["2023-01-01"]),
                "roe": [0.25],
            }
        ),
        "sp500_index": pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "close": [4000.0],
            }
        ),
        "company_profiles": pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "companyName": ["Apple Inc"],
            }
        ),
    }


class TestRunDataCollection:
    """Test run_data_collection function."""

    @pytest.mark.unit
    @patch("main.FMPDataCollector")
    def test_run_data_collection_calls_collector(
        self, mock_collector_class, sample_config
    ):
        """Test that run_data_collection calls collector."""
        mock_collector = MagicMock()
        mock_collector.collect_all = AsyncMock(return_value={"sp500_tickers": ["AAPL"]})
        mock_collector_class.return_value = mock_collector

        result = run_data_collection(sample_config, force_refresh=False)

        assert result is not None
        mock_collector_class.assert_called_once()

    @pytest.mark.unit
    @patch("main.FMPDataCollector")
    def test_run_data_collection_force_refresh(
        self, mock_collector_class, sample_config, tmp_path
    ):
        """Test that force_refresh removes cache files."""
        sample_config["data"]["data_dir"] = str(tmp_path)

        # Create cache files
        cache_dir = tmp_path
        (cache_dir / "ohlcv_raw.parquet").touch()
        (cache_dir / "fundamentals_combined.parquet").touch()
        (cache_dir / "sp500_index.parquet").touch()

        mock_collector = MagicMock()
        mock_collector.collect_all = AsyncMock(return_value={"sp500_tickers": ["AAPL"]})
        mock_collector_class.return_value = mock_collector

        run_data_collection(sample_config, force_refresh=True)

        # Cache files should be removed
        assert not (cache_dir / "ohlcv_raw.parquet").exists()
        assert not (cache_dir / "fundamentals_combined.parquet").exists()
        assert not (cache_dir / "sp500_index.parquet").exists()


class TestRunDataProcessing:
    """Test run_data_processing function."""

    @pytest.mark.unit
    @patch("main.DataProcessor")
    @patch("main.pd.read_parquet")
    def test_run_data_processing_with_data(
        self, mock_read, mock_processor_class, sample_config, sample_data
    ):
        """Test run_data_processing with provided data."""
        mock_processor = MagicMock()
        mock_processor.process_all.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        mock_processor_class.return_value = mock_processor

        result = run_data_processing(sample_config, data=sample_data)

        assert result is not None
        mock_processor.process_all.assert_called_once()

    @pytest.mark.unit
    @patch("main.DataProcessor")
    @patch("main.pd.read_parquet")
    def test_run_data_processing_loads_from_cache(
        self, mock_read, mock_processor_class, sample_config
    ):
        """Test run_data_processing loads from cache when data not provided."""
        mock_read.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        mock_processor = MagicMock()
        mock_processor.process_all.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        mock_processor_class.return_value = mock_processor

        result = run_data_processing(sample_config, data=None)

        assert result is not None
        assert mock_read.call_count >= 2  # Should load multiple files


class TestRunModelTraining:
    """Test run_model_training function."""

    @pytest.mark.unit
    @patch("main.QuantamentalTrainer")
    @patch("main.validate_metrics")
    @patch("main.pd.read_parquet")
    def test_run_model_training_with_validation(
        self, mock_read, mock_validate, mock_trainer_class, sample_config
    ):
        """Test run_model_training with validation."""
        mock_trainer = MagicMock()
        mock_trainer.train_with_wandb.return_value = (
            MagicMock(),  # model
            MagicMock(),  # scaler
            {"accuracy": 0.85, "f1_score": 0.80},  # metrics
        )
        mock_trainer_class.return_value = mock_trainer
        mock_read.return_value = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 100,
                "date": pd.date_range("2023-01-01", periods=100),
                "close": np.random.uniform(100, 200, 100),
            }
        )
        mock_validate.return_value = ("production", "OK")

        model, scaler, metrics = run_model_training(
            sample_config, df=None, validate=True
        )

        assert model is not None
        assert scaler is not None
        assert isinstance(metrics, dict)
        mock_validate.assert_called_once()

    @pytest.mark.unit
    @patch("main.QuantamentalTrainer")
    @patch("main.HAS_MODEL_VALIDATION", False)
    def test_run_model_training_without_validation(
        self, mock_trainer_class, sample_config
    ):
        """Test run_model_training without validation module."""
        mock_trainer = MagicMock()
        mock_trainer.train_with_wandb.return_value = (
            MagicMock(),
            MagicMock(),
            {"accuracy": 0.85},
        )
        mock_trainer_class.return_value = mock_trainer

        with patch("main.pd.read_parquet") as mock_read:
            mock_read.return_value = pd.DataFrame(
                {
                    "symbol": ["AAPL"] * 100,
                    "date": pd.date_range("2023-01-01", periods=100),
                }
            )

            model, scaler, metrics = run_model_training(
                sample_config, df=None, validate=False
            )

            assert model is not None
            assert scaler is not None


class TestRunPrediction:
    """Test run_prediction function."""

    @pytest.mark.unit
    @patch("main.QuantamentalPredictor")
    @patch("main.get_best_model")
    @patch("main.HAS_MODEL_VALIDATION", True)
    def test_run_prediction_with_validated_model(
        self, mock_get_best, mock_predictor_class, sample_config
    ):
        """Test run_prediction uses validated model."""
        mock_model = MagicMock()
        mock_get_best.return_value = (mock_model, {"accuracy": 0.85}, "production")

        mock_predictor = MagicMock()
        mock_predictor.predict_next_month.return_value = (
            pd.DataFrame({"symbol": ["AAPL"]}),
            pd.DataFrame({"symbol": ["AAPL"]}),
        )
        mock_predictor_class.return_value = mock_predictor

        with patch("main.pd.read_parquet") as mock_read:
            mock_read.return_value = pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "date": pd.to_datetime(["2023-01-01"]),
                }
            )

            df_predict, top_stocks = run_prediction(
                sample_config, df=None, use_validated_model=True
            )

            assert df_predict is not None
            assert top_stocks is not None

    @pytest.mark.unit
    @patch("main.QuantamentalPredictor")
    def test_run_prediction_without_validated_model(
        self, mock_predictor_class, sample_config
    ):
        """Test run_prediction without validated model."""
        mock_predictor = MagicMock()
        mock_predictor.predict_next_month.return_value = (
            pd.DataFrame({"symbol": ["AAPL"]}),
            pd.DataFrame({"symbol": ["AAPL"]}),
        )
        mock_predictor_class.return_value = mock_predictor

        with patch("main.pd.read_parquet") as mock_read:
            mock_read.return_value = pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "date": pd.to_datetime(["2023-01-01"]),
                }
            )

            df_predict, top_stocks = run_prediction(
                sample_config, df=None, use_validated_model=False
            )

            assert df_predict is not None
            assert top_stocks is not None


class TestRunBacktest:
    """Test run_backtest function."""

    @pytest.mark.unit
    @patch("main.QuantamentalBacktester")
    def test_run_backtest_returns_results(self, mock_backtester_class, sample_config):
        """Test run_backtest returns results."""
        mock_backtester = MagicMock()
        mock_backtester.run_backtest.return_value = {
            "local_files": {"combined": "test.csv"},
            "gcs_paths": {},
            "num_stocks": 10,
        }
        mock_backtester_class.return_value = mock_backtester

        with patch("main.pd.read_parquet") as mock_read:
            mock_read.return_value = pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "date": pd.to_datetime(["2023-01-01"]),
                }
            )

            result = run_backtest(sample_config, df=None)

            assert result is not None
            assert "local_files" in result


class TestRunRagReasoning:
    """Test run_rag_reasoning function."""

    @pytest.mark.unit
    @patch("main.add_reasoning_to_combined_file")
    @patch("main.HAS_RAG", True)
    @patch("main.Path")
    def test_run_rag_reasoning_success(
        self, mock_path, mock_add_reasoning, sample_config, tmp_path
    ):
        """Test run_rag_reasoning when RAG is available."""
        sample_config["data"]["data_dir"] = str(tmp_path)
        csv_path = f"{tmp_path}/combined.csv"

        # Create CSV file
        pd.DataFrame({"symbol": ["AAPL"]}).to_csv(csv_path, index=False)

        mock_path.return_value.exists.return_value = True
        mock_add_reasoning.return_value = f"{tmp_path}/combined_with_reasoning.csv"

        result = run_rag_reasoning(
            sample_config, combined_csv_path=csv_path, sample_size=None
        )

        assert result is not None
        mock_add_reasoning.assert_called_once()

    @pytest.mark.unit
    @patch("main.HAS_RAG", False)
    def test_run_rag_reasoning_no_rag_module(self, sample_config):
        """Test run_rag_reasoning when RAG module not available."""
        result = run_rag_reasoning(
            sample_config, combined_csv_path=None, sample_size=None
        )

        assert result is None


class TestRunDataVersioning:
    """Test run_data_versioning function."""

    @pytest.mark.unit
    @patch("main.DataVersionManager")
    @patch("main.HAS_VERSIONING", True)
    def test_run_data_versioning_success(self, mock_versioner_class, sample_config):
        """Test run_data_versioning when versioning is available."""
        mock_versioner = MagicMock()
        mock_versioner.create_version_snapshot.return_value = {
            "version_tag": "test",
            "methods": ["wandb_artifacts"],
        }
        mock_versioner_class.return_value = mock_versioner

        result = run_data_versioning(sample_config, version_tag="test")

        assert result is not None
        assert "version_tag" in result

    @pytest.mark.unit
    @patch("main.HAS_VERSIONING", False)
    def test_run_data_versioning_no_module(self, sample_config):
        """Test run_data_versioning when versioning module not available."""
        result = run_data_versioning(sample_config, version_tag="test")

        assert result is None


class TestRunFullPipeline:
    """Test run_full_pipeline function."""

    @pytest.mark.unit
    @patch("main.run_data_versioning")
    @patch("main.run_rag_reasoning")
    @patch("main.run_backtest")
    @patch("main.run_prediction")
    @patch("main.run_model_training")
    @patch("main.run_data_processing")
    @patch("main.run_data_collection")
    def test_run_full_pipeline_all_steps(
        self,
        mock_collect,
        mock_process,
        mock_train,
        mock_predict,
        mock_backtest,
        mock_rag,
        mock_version,
        sample_config,
    ):
        """Test run_full_pipeline executes all steps."""
        # Setup mocks
        mock_collect.return_value = {"sp500_tickers": ["AAPL"]}
        mock_process.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        mock_train.return_value = (MagicMock(), MagicMock(), {"accuracy": 0.85})
        mock_predict.return_value = (
            pd.DataFrame({"symbol": ["AAPL"]}),
            pd.DataFrame({"symbol": ["AAPL"]}),
        )
        mock_backtest.return_value = {"local_files": {"combined": "test.csv"}}
        mock_rag.return_value = "test_with_reasoning.csv"
        mock_version.return_value = {"version_tag": "test"}

        result = run_full_pipeline(
            force_refresh=False,
            skip_training=False,
            enable_rag=True,
            version_data=True,
        )

        assert result is not None
        assert "model_metrics" in result
        assert "top_stocks" in result
        assert "backtest" in result
        assert "rag_output" in result
        assert "version_info" in result

    @pytest.mark.unit
    @patch("main.run_data_versioning")
    @patch("main.run_backtest")
    @patch("main.run_prediction")
    @patch("main.run_model_training")
    @patch("main.run_data_processing")
    @patch("main.run_data_collection")
    def test_run_full_pipeline_skip_training(
        self,
        mock_collect,
        mock_process,
        mock_train,
        mock_predict,
        mock_backtest,
        mock_version,
        sample_config,
    ):
        """Test run_full_pipeline skips training when requested."""
        mock_collect.return_value = {"sp500_tickers": ["AAPL"]}
        mock_process.return_value = pd.DataFrame({"symbol": ["AAPL"]})
        mock_predict.return_value = (
            pd.DataFrame({"symbol": ["AAPL"]}),
            pd.DataFrame({"symbol": ["AAPL"]}),
        )
        mock_backtest.return_value = {"local_files": {"combined": "test.csv"}}
        mock_version.return_value = {"version_tag": "test"}

        result = run_full_pipeline(
            force_refresh=False,
            skip_training=True,
            enable_rag=False,
            version_data=True,
        )

        assert result is not None
        mock_train.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
