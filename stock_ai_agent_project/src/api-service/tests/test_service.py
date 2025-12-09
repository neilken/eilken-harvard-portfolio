"""
Unit tests for the main FastAPI service module.
"""

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


class TestServiceEndpoints:
    """Tests for basic service endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Set up test client with mocked dependencies."""
        with (
            patch("api.utils.get_gcs_bucket.storage") as mock_storage,
            patch("api.utils.get_gcs_bucket.get_gcs_data") as mock_gcs,
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI") as mock_llm,
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent,
            patch("api.routers.stock_details.get_gcs_data") as mock_gcs_details,
        ):

            mock_gcs.return_value = MagicMock()
            mock_gcs_details.return_value = MagicMock()
            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()

            from fastapi.testclient import TestClient
            from api.service import app

            self.client = TestClient(app)
            yield

    def test_root_endpoint_returns_welcome(self):
        """Test the root endpoint returns welcome message."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to Stockbusters"}

    def test_root_endpoint_method_not_allowed(self):
        """Test that POST to root returns method not allowed."""
        response = self.client.post("/")
        assert response.status_code == 405

    def test_square_root_default_values(self):
        """Test square root endpoint with default values (x=1, y=2)."""
        response = self.client.get("/square_root/")
        assert response.status_code == 200
        result = response.json()
        # sqrt(1^2 + 2^2) = sqrt(5) ≈ 2.236
        assert abs(result - 2.236) < 0.01

    def test_square_root_pythagorean_triple(self):
        """Test square root with 3-4-5 Pythagorean triple."""
        response = self.client.get("/square_root/?x=3&y=4")
        assert response.status_code == 200
        assert response.json() == 5.0

    def test_square_root_zero_values(self):
        """Test square root with zero values."""
        response = self.client.get("/square_root/?x=0&y=0")
        assert response.status_code == 200
        assert response.json() == 0.0

    def test_square_root_negative_values(self):
        """Test square root with negative values (squares eliminate negatives)."""
        response = self.client.get("/square_root/?x=-3&y=-4")
        assert response.status_code == 200
        assert response.json() == 5.0

    def test_square_root_float_values(self):
        """Test square root with float values."""
        response = self.client.get("/square_root/?x=1.5&y=2.5")
        assert response.status_code == 200
        result = response.json()
        # sqrt(2.25 + 6.25) = sqrt(8.5) ≈ 2.915
        assert abs(result - 2.915) < 0.01

    def test_square_root_large_values(self):
        """Test square root with large values."""
        response = self.client.get("/square_root/?x=100&y=100")
        assert response.status_code == 200
        result = response.json()
        # sqrt(10000 + 10000) = sqrt(20000) ≈ 141.42
        assert abs(result - 141.42) < 0.01
