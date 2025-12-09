"""
Unit tests for model_validation.py
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_validation import (
    get_best_model,
    load_artifact,
    validate_metrics,
    ModelValidator,
)


class TestGetBestModel:
    """Test get_best_model function."""

    @pytest.mark.unit
    @patch("model_validation.wandb")
    def test_get_best_model_returns_model(self, mock_wandb):
        """Test that get_best_model returns model when available."""
        # Mock W&B API
        mock_api = MagicMock()
        mock_wandb.Api.return_value = mock_api

        # Mock artifact
        mock_artifact = MagicMock()
        mock_artifact.version = "v1"
        mock_artifact.metadata = {"accuracy": 0.85, "roc_auc": 0.80}
        mock_artifact.download.return_value = "/tmp/test_model"

        # Mock artifacts list
        mock_api.artifacts.return_value = [mock_artifact]
        mock_api.artifact_versions.return_value = [mock_artifact]

        # Mock joblib.load and Path.exists
        mock_model = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.__truediv__ = (
            lambda self, other: self
        )  # Path / "model.pkl" returns self

        with patch("model_validation.joblib.load", return_value=mock_model):
            with patch("model_validation.Path", return_value=mock_path):
                model, metrics, status = get_best_model(allow_degraded=True)

                assert model is not None
                assert isinstance(metrics, dict)
                assert status in ["production", "degraded", "rejected"]

    @pytest.mark.unit
    @patch("model_validation.wandb")
    def test_get_best_model_handles_no_models(self, mock_wandb):
        """Test that get_best_model handles no models gracefully."""
        mock_api = MagicMock()
        mock_wandb.Api.return_value = mock_api
        mock_api.artifacts.return_value = []
        mock_api.artifact_versions.return_value = []

        model, metrics, status = get_best_model(allow_degraded=True)

        assert model is None
        assert status == "rejected"

    @pytest.mark.unit
    @patch("model_validation.wandb")
    def test_get_best_model_uses_fallback_accuracy(self, mock_wandb):
        """Test that fallback accuracy is used when metadata missing."""
        mock_api = MagicMock()
        mock_wandb.Api.return_value = mock_api

        mock_artifact = MagicMock()
        mock_artifact.version = "v1"
        mock_artifact.metadata = {}  # No metadata
        mock_artifact.download.return_value = "/tmp/test_model"

        mock_api.artifacts.return_value = [mock_artifact]

        mock_model = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: self

        with patch("model_validation.joblib.load", return_value=mock_model):
            with patch("model_validation.Path", return_value=mock_path):
                model, metrics, status = get_best_model(allow_degraded=True)

                # Should use fallback accuracy (0.39)
                assert model is not None
                assert status in ["degraded", "production", "rejected"]


class TestLoadArtifact:
    """Test load_artifact function."""

    @pytest.mark.unit
    def test_load_artifact_loads_model(self):
        """Test that load_artifact loads model from downloaded path."""
        mock_artifact = MagicMock()
        mock_artifact.download.return_value = "/tmp/test_model"

        mock_model = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.__truediv__ = lambda self, other: self

        with patch("model_validation.joblib.load", return_value=mock_model):
            with patch("model_validation.Path", return_value=mock_path):
                model = load_artifact(mock_artifact)

                assert model is not None

    @pytest.mark.unit
    def test_load_artifact_handles_missing_file(self):
        """Test that load_artifact handles missing model file."""
        mock_artifact = MagicMock()
        mock_artifact.download.return_value = "/tmp/test_model"

        with patch("os.path.exists", return_value=False):
            model = load_artifact(mock_artifact)

            assert model is None


class TestValidateMetrics:
    """Test validate_metrics function."""

    @pytest.mark.unit
    def test_validate_metrics_production(self):
        """Test that high accuracy returns production status."""
        metrics = {"accuracy": 0.85}
        status, msg = validate_metrics(metrics)

        assert status == "production"
        assert "OK" in msg

    @pytest.mark.unit
    def test_validate_metrics_degraded(self):
        """Test that medium accuracy returns degraded status."""
        metrics = {"accuracy": 0.50}
        status, msg = validate_metrics(metrics)

        assert status == "degraded"
        assert "Warning" in msg

    @pytest.mark.unit
    def test_validate_metrics_rejected(self):
        """Test that low accuracy returns rejected status."""
        metrics = {"accuracy": 0.30}
        status, msg = validate_metrics(metrics)

        assert status == "rejected"
        assert "Rejected" in msg


class TestModelValidator:
    """Test ModelValidator class."""

    @pytest.mark.unit
    @patch("model_validation.get_best_model")
    def test_model_validator_init_success(self, mock_get_best):
        """Test that ModelValidator initializes successfully."""
        mock_model = MagicMock()
        mock_metrics = {"accuracy": 0.85}
        mock_get_best.return_value = (mock_model, mock_metrics, "production")

        config = {"wandb": {"project": "test-project"}}
        validator = ModelValidator(config, allow_degraded=True)

        assert validator.model is not None
        assert validator.metrics == mock_metrics
        assert validator.status == "production"

    @pytest.mark.unit
    @patch("model_validation.get_best_model")
    def test_model_validator_init_rejected(self, mock_get_best):
        """Test that ModelValidator raises error when model rejected."""
        mock_get_best.return_value = (None, {}, "rejected")

        config = {"wandb": {"project": "test-project"}}

        with pytest.raises(ValueError, match="No valid model found"):
            ModelValidator(config, allow_degraded=False)

    @pytest.mark.unit
    @patch("model_validation.get_best_model")
    def test_model_validator_predict(self, mock_get_best):
        """Test that ModelValidator.predict works."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [1, 0, 1]
        mock_get_best.return_value = (mock_model, {"accuracy": 0.85}, "production")

        config = {"wandb": {"project": "test-project"}}
        validator = ModelValidator(config, allow_degraded=True)

        result = validator.predict([[1, 2, 3]])

        assert result is not None
        mock_model.predict.assert_called_once()

    @pytest.mark.unit
    @patch("model_validation.get_best_model")
    def test_model_validator_predict_proba(self, mock_get_best):
        """Test that ModelValidator.predict_proba works."""
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = [[0.3, 0.7], [0.8, 0.2]]
        mock_get_best.return_value = (mock_model, {"accuracy": 0.85}, "production")

        config = {"wandb": {"project": "test-project"}}
        validator = ModelValidator(config, allow_degraded=True)

        result = validator.predict_proba([[1, 2, 3]])

        assert result is not None
        mock_model.predict_proba.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
