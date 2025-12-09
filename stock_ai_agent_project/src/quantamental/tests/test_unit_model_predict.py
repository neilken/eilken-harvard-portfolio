"""
Unit tests for model_predict.py - QuantamentalPredictor class
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, Mock
import joblib
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_predict import QuantamentalPredictor
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
        "wandb": {"project": "test-project"},
    }


@pytest.fixture
def sample_prediction_data():
    """Sample data for prediction."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="D")

    df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 25 + ["MSFT"] * 25,
            "date": dates,
            "close": np.random.uniform(100, 200, 50),
            "return_1m": np.random.uniform(-0.1, 0.1, 50),
            "RSI_14": np.random.uniform(30, 70, 50),
            "ema_12": np.random.uniform(100, 200, 50),
            "ema_26": np.random.uniform(100, 200, 50),
            "roe": np.random.uniform(0.1, 0.3, 50),
            "roic": np.random.uniform(0.05, 0.2, 50),
            "peRatio": np.random.uniform(15, 25, 50),
            "debtToEquity": np.random.uniform(0.5, 2.0, 50),
        }
    )
    return df


@pytest.fixture
def mock_model():
    """Mock trained model."""
    model = MagicMock()

    # Return predictions that match DataFrame length dynamically
    def predict_proba_side_effect(X):
        n_samples = len(X) if hasattr(X, "__len__") else 3
        return np.array([[0.3, 0.7]] * n_samples)

    model.predict_proba.side_effect = predict_proba_side_effect
    return model


@pytest.fixture
def mock_scaler():
    """Mock scaler."""
    scaler = MagicMock()

    # Return scaled data that matches input length
    def transform_side_effect(X):
        return X  # Return as-is for simplicity

    scaler.transform.side_effect = transform_side_effect
    return scaler


class TestQuantamentalPredictorInit:
    """Test QuantamentalPredictor initialization."""

    @pytest.mark.unit
    def test_predictor_initialization(self, sample_config):
        """Test predictor initializes with config."""
        predictor = QuantamentalPredictor(sample_config)

        assert predictor.config == sample_config
        assert predictor.model is None
        assert predictor.scaler is None


class TestLoadModelFromWandb:
    """Test load_model_from_wandb method."""

    @pytest.mark.unit
    @patch("model_predict.wandb")
    def test_load_model_from_wandb_success(
        self, mock_wandb, sample_config, mock_model, mock_scaler
    ):
        """Test loading model from W&B."""
        # Mock W&B API
        mock_api = MagicMock()
        mock_wandb.Api.return_value = mock_api

        # Mock artifact
        mock_artifact = MagicMock()
        mock_artifact.download.return_value = "/tmp/test_model"
        mock_api.artifact.return_value = mock_artifact

        # Mock joblib.load
        with patch("model_predict.joblib.load") as mock_load:
            mock_load.side_effect = [mock_model, mock_scaler]

            predictor = QuantamentalPredictor(sample_config)
            model, scaler = predictor.load_model_from_wandb()

            assert model is not None
            assert scaler is not None
            assert predictor.model is not None
            assert predictor.scaler is not None


class TestLoadModelLocal:
    """Test load_model_local method."""

    @pytest.mark.unit
    def test_load_model_local_success(self, sample_config, mock_model, mock_scaler):
        """Test loading model from local files."""
        # Use joblib.load mock instead of trying to pickle MagicMock
        with patch("model_predict.joblib.load") as mock_load:
            mock_load.side_effect = [mock_model, mock_scaler]

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = f"{tmpdir}/model.pkl"
                scaler_path = f"{tmpdir}/scaler.pkl"

                # Create empty files
                with open(model_path, "w") as f:
                    f.write("")
                with open(scaler_path, "w") as f:
                    f.write("")

                predictor = QuantamentalPredictor(sample_config)
                model, scaler = predictor.load_model_local(model_path, scaler_path)

                assert model is not None
                assert scaler is not None
                assert predictor.model is not None
                assert predictor.scaler is not None


class TestPreparePredictionData:
    """Test prepare_prediction_data method."""

    @pytest.mark.unit
    def test_prepare_prediction_data_creates_lags(
        self, sample_config, sample_prediction_data
    ):
        """Test that lagged features are created."""
        predictor = QuantamentalPredictor(sample_config)

        result = predictor.prepare_prediction_data(sample_prediction_data)

        # Check lagged features exist
        assert "return_1m_lag1" in result.columns
        assert "RSI_14_lag1" in result.columns
        assert len(result) > 0


class TestPredict:
    """Test predict method."""

    @pytest.mark.unit
    def test_predict_adds_probabilities(
        self, sample_config, sample_prediction_data, mock_model, mock_scaler
    ):
        """Test that predict adds probabilities and ranks."""
        predictor = QuantamentalPredictor(sample_config)
        predictor.model = mock_model
        predictor.scaler = mock_scaler

        df_prepared = predictor.prepare_prediction_data(sample_prediction_data)

        result = predictor.predict(df_prepared)

        assert "pred_prob" in result.columns
        assert "pred_rank" in result.columns
        assert len(result) > 0


class TestGetTopStocks:
    """Test get_top_stocks method."""

    @pytest.mark.unit
    def test_get_top_stocks_returns_top_n(
        self, sample_config, sample_prediction_data, mock_model, mock_scaler
    ):
        """Test that get_top_stocks returns top N stocks."""
        predictor = QuantamentalPredictor(sample_config)
        predictor.model = mock_model
        predictor.scaler = mock_scaler

        df_prepared = predictor.prepare_prediction_data(sample_prediction_data)
        df_with_pred = predictor.predict(df_prepared)

        top_stocks = predictor.get_top_stocks(df_with_pred, top_n=5)

        assert len(top_stocks) <= 5
        assert "symbol" in top_stocks.columns
        assert "pred_prob" in top_stocks.columns
        assert "pred_rank" in top_stocks.columns


class TestPredictNextMonth:
    """Test predict_next_month method."""

    @pytest.mark.unit
    @patch("model_predict.QuantamentalPredictor.load_model_from_wandb")
    def test_predict_next_month_with_wandb(
        self, mock_load, sample_config, sample_prediction_data, mock_model, mock_scaler
    ):
        """Test predict_next_month with W&B model loading."""
        mock_load.return_value = (mock_model, mock_scaler)

        predictor = QuantamentalPredictor(sample_config)
        predictor.model = mock_model
        predictor.scaler = mock_scaler

        df_predict, top_stocks = predictor.predict_next_month(
            sample_prediction_data, top_n=5, use_wandb=True
        )

        assert df_predict is not None
        assert top_stocks is not None
        assert "pred_prob" in df_predict.columns


class TestSavePredictions:
    """Test save_predictions method."""

    @pytest.mark.unit
    def test_save_predictions_creates_file(
        self, sample_config, sample_prediction_data, mock_model, mock_scaler, tmp_path
    ):
        """Test that predictions are saved to file."""
        sample_config["data"]["data_dir"] = str(tmp_path)
        predictor = QuantamentalPredictor(sample_config)
        predictor.model = mock_model
        predictor.scaler = mock_scaler

        df_prepared = predictor.prepare_prediction_data(sample_prediction_data)
        df_with_pred = predictor.predict(df_prepared)

        output_path = predictor.save_predictions(df_with_pred)

        assert os.path.exists(output_path)
        assert output_path.endswith(".csv")

        # Verify file contents
        saved_df = pd.read_csv(output_path)
        assert "symbol" in saved_df.columns
        assert "pred_prob" in saved_df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
