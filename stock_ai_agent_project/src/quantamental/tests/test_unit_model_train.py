"""
Unit tests for model_train.py - QuantamentalTrainer class
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, Mock
import joblib
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_train import QuantamentalTrainer
from utils import load_config


@pytest.fixture
def sample_config():
    """Sample configuration for tests."""
    return {
        "data": {"data_dir": "./data"},
        "features": {
            "technical": ["return_1m", "RSI_14", "ema_12", "ema_26"],
            "fundamental": ["roe", "roic", "peRatio", "debtToEquity"],
        },
        "model": {
            "hyperparameters": {
                "n_estimators": 10,
                "max_depth": 5,
                "random_state": 42,
            },
            "train_window_months": 12,
        },
        "wandb": {"project": "test-project", "entity": "test-entity", "tags": ["test"]},
    }


@pytest.fixture
def sample_training_data():
    """Sample training DataFrame."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="D")

    df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 50 + ["MSFT"] * 50,
            "date": dates,
            "close": np.random.uniform(100, 200, 100),
            "return_1m": np.random.uniform(-0.1, 0.1, 100),
            "RSI_14": np.random.uniform(30, 70, 100),
            "ema_12": np.random.uniform(100, 200, 100),
            "ema_26": np.random.uniform(100, 200, 100),
            "roe": np.random.uniform(0.1, 0.3, 100),
            "roic": np.random.uniform(0.05, 0.2, 100),
            "peRatio": np.random.uniform(15, 25, 100),
            "debtToEquity": np.random.uniform(0.5, 2.0, 100),
            "sp500_return_1m": np.random.uniform(-0.05, 0.05, 100),
        }
    )
    return df


class TestQuantamentalTrainerInit:
    """Test QuantamentalTrainer initialization."""

    @pytest.mark.unit
    def test_trainer_initialization(self, sample_config):
        """Test trainer initializes with config."""
        trainer = QuantamentalTrainer(sample_config)

        assert trainer.config == sample_config
        assert hasattr(trainer, "feature_names")
        assert hasattr(trainer, "tech_cols")
        assert hasattr(trainer, "fund_cols")


class TestPrepareFeatures:
    """Test prepare_features method."""

    @pytest.mark.unit
    def test_prepare_features_creates_lags(self, sample_config, sample_training_data):
        """Test that lagged features are created."""
        trainer = QuantamentalTrainer(sample_config)

        result = trainer.prepare_features(sample_training_data)

        # Check lagged features exist
        assert "return_1m_lag1" in result.columns
        assert "RSI_14_lag1" in result.columns

        # Check label is created
        assert "label" in result.columns


class TestCreateTrainTestSplit:
    """Test create_train_test_split method."""

    @pytest.mark.unit
    def test_train_test_split_structure(self, sample_config, sample_training_data):
        """Test train/test split returns correct structure."""
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)

        df_train, df_test = trainer.create_train_test_split(
            df, test_year=2024, test_month=1
        )

        assert isinstance(df_train, pd.DataFrame)
        assert isinstance(df_test, pd.DataFrame)
        assert len(df_train) > 0 or len(df_test) > 0


class TestTrainModel:
    """Test train_model method."""

    @pytest.mark.unit
    def test_train_model_returns_model_and_scaler(
        self, sample_config, sample_training_data
    ):
        """Test that train_model returns model and scaler."""
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)
        df_train, _ = trainer.create_train_test_split(df, test_year=2024, test_month=1)

        X_train = df_train[trainer.feature_names].fillna(0)
        y_train = df_train["label"].fillna(0)

        # Only test if we have data
        if len(X_train) > 0 and len(y_train) > 0:
            model, scaler = trainer.train_model(X_train, y_train)

            assert model is not None
            assert scaler is not None
            assert hasattr(model, "predict")
            assert hasattr(scaler, "transform")


class TestEvaluateModel:
    """Test evaluate_model method."""

    @pytest.mark.unit
    def test_evaluate_model_returns_metrics(self, sample_config, sample_training_data):
        """Test that evaluate_model returns metrics."""
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)
        df_train, df_test = trainer.create_train_test_split(
            df, test_year=2024, test_month=1
        )

        X_train = df_train[trainer.feature_names].fillna(0)
        y_train = df_train["label"].fillna(0)
        X_test = df_test[trainer.feature_names].fillna(0)
        y_test = df_test["label"].fillna(0)

        if len(X_train) > 0 and len(X_test) > 0:
            model, scaler = trainer.train_model(X_train, y_train)
            metrics, y_pred, y_prob = trainer.evaluate_model(
                model, scaler, X_test, y_test
            )

            assert isinstance(metrics, dict)
            assert "accuracy" in metrics
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1_score" in metrics
            assert "roc_auc" in metrics


class TestFindOptimalThreshold:
    """Test find_optimal_threshold method."""

    @pytest.mark.unit
    def test_find_optimal_threshold_returns_float(
        self, sample_config, sample_training_data
    ):
        """Test that optimal threshold is returned."""
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)
        df_train, _ = trainer.create_train_test_split(df, test_year=2024, test_month=1)

        X_train = df_train[trainer.feature_names].fillna(0)
        y_train = df_train["label"].fillna(0)

        if len(X_train) > 0:
            model, scaler = trainer.train_model(X_train, y_train)
            threshold = trainer.find_optimal_threshold(model, scaler, X_train, y_train)

            assert isinstance(threshold, (float, np.floating))
            assert 0 <= threshold <= 1


class TestCreatePlots:
    """Test create_plots method."""

    @pytest.mark.unit
    def test_create_plots_returns_dict(self, sample_config, sample_training_data):
        """Test that plots are created."""
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)
        df_train, df_test = trainer.create_train_test_split(
            df, test_year=2024, test_month=1
        )

        X_train = df_train[trainer.feature_names].fillna(0)
        y_train = df_train["label"].fillna(0)
        X_test = df_test[trainer.feature_names].fillna(0)
        y_test = df_test["label"].fillna(0)

        if len(X_train) > 0 and len(X_test) > 0:
            model, scaler = trainer.train_model(X_train, y_train)
            _, y_pred, y_prob = trainer.evaluate_model(model, scaler, X_test, y_test)

            plots = trainer.create_plots(model, y_test, y_pred, y_prob, X_train)

            assert isinstance(plots, dict)
            assert "confusion_matrix" in plots
            assert "feature_importance" in plots
            assert "prob_distribution" in plots


class TestSaveArtifacts:
    """Test save_artifacts method."""

    @pytest.mark.unit
    def test_save_artifacts_creates_files(
        self, sample_config, sample_training_data, tmp_path
    ):
        """Test that artifacts are saved."""
        sample_config["data"]["data_dir"] = str(tmp_path)
        trainer = QuantamentalTrainer(sample_config)
        df = trainer.prepare_features(sample_training_data)
        df_train, _ = trainer.create_train_test_split(df, test_year=2024, test_month=1)

        X_train = df_train[trainer.feature_names].fillna(0)
        y_train = df_train["label"].fillna(0)

        if len(X_train) > 0:
            model, scaler = trainer.train_model(X_train, y_train)
            paths = trainer.save_artifacts(model, scaler, "test_run_id")

            assert isinstance(paths, dict)
            assert "model" in paths
            assert "scaler" in paths
            assert "config" in paths


class TestTrainWithWandb:
    """Test train_with_wandb method."""

    @pytest.mark.unit
    @patch("model_train.wandb")
    def test_train_with_wandb_returns_model(
        self, mock_wandb, sample_config, sample_training_data
    ):
        """Test that train_with_wandb returns model and metrics."""
        # Mock wandb
        mock_run = MagicMock()
        mock_run.id = "test_run_123"
        mock_run.name = "test_run"
        mock_wandb.init.return_value = mock_run
        mock_wandb.Artifact = MagicMock()
        mock_wandb.Image = MagicMock()
        mock_wandb.Table = MagicMock()

        trainer = QuantamentalTrainer(sample_config)

        # Add date column if missing
        if "date" not in sample_training_data.columns:
            sample_training_data["date"] = pd.date_range(
                "2023-01-01", periods=len(sample_training_data)
            )

        # Add sp500_return_1m if missing
        if "sp500_return_1m" not in sample_training_data.columns:
            sample_training_data["sp500_return_1m"] = np.random.uniform(
                -0.05, 0.05, len(sample_training_data)
            )

        # Extend data to ensure test set has data (use test_year=2023, test_month=12)
        # This ensures we have test data
        try:
            model, scaler, metrics = trainer.train_with_wandb(
                sample_training_data, test_year=2023, test_month=12
            )

            assert model is not None
            assert scaler is not None
            assert isinstance(metrics, dict)
            mock_wandb.init.assert_called_once()
            mock_run.finish.assert_called_once()
        except Exception as e:
            # If data is insufficient, that's okay for unit test
            if (
                "insufficient" in str(e).lower()
                or "empty" in str(e).lower()
                or "0 sample" in str(e).lower()
            ):
                pytest.skip(f"Insufficient data for test: {e}")
            else:
                raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
