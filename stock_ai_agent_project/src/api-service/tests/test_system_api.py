"""
System tests for the API service running in a Docker container.

These tests run against a live container and verify end-to-end functionality.
Requires the container to be running on the specified API_BASE_URL.

Run with:
    API_BASE_URL=http://localhost:9000 pytest tests/system/ -v
"""

import os
import pytest
import httpx
import uuid


# Mark as system tests and skip if container is not running
pytestmark = [
    pytest.mark.system,
    pytest.mark.skipif(
        os.environ.get("RUN_SYSTEM_TESTS", "false").lower() != "true",
        reason="System tests require RUN_SYSTEM_TESTS=true and running container",
    ),
]


class TestSystemHealth:
    """System tests for health and basic connectivity."""

    @pytest.fixture(autouse=True)
    def setup(self, api_base_url):
        """Set up HTTP client."""
        self.base_url = api_base_url
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def teardown_method(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def test_root_endpoint_accessible(self):
        """Test that root endpoint is accessible."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to Stockbusters"}

    def test_square_root_endpoint_works(self):
        """Test that square root calculation works."""
        response = self.client.get("/square_root/?x=3&y=4")
        assert response.status_code == 200
        assert response.json() == 5.0

    def test_api_response_time(self):
        """Test that API responds within acceptable time."""
        import time

        start = time.time()
        response = self.client.get("/")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond within 2 seconds


class TestSystemChatWorkflow:
    """System tests for complete chat workflow."""

    @pytest.fixture(autouse=True)
    def setup(self, api_base_url, test_session_id):
        """Set up HTTP client and session."""
        self.base_url = api_base_url
        self.session_id = test_session_id
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=60.0,
            headers={"X-Session-ID": self.session_id},
        )

    def teardown_method(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def test_start_new_chat(self):
        """Test starting a new chat conversation."""
        response = self.client.post("/gemini/chats", json={"message": "My name is Test User"})

        assert response.status_code == 200
        data = response.json()
        assert "chat_id" in data
        assert "message" in data
        assert len(data["message"]) > 0

    def test_complete_chat_workflow(self):
        """Test complete chat workflow from start to preferences."""
        # Start chat
        start_response = self.client.post("/gemini/chats", json={"message": "My name is Integration Test"})
        assert start_response.status_code == 200
        chat_id = start_response.json()["chat_id"]

        # Continue with investment horizon
        response = self.client.post(
            f"/gemini/chats/{chat_id}",
            json={"message": "I prefer long term investments"},
        )
        assert response.status_code == 200

        # Continue with risk appetite
        response = self.client.post(f"/gemini/chats/{chat_id}", json={"message": "I have low risk appetite"})
        assert response.status_code == 200

    def test_get_chat_history(self):
        """Test retrieving chat history."""
        # Start a chat first
        start_response = self.client.post("/gemini/chats", json={"message": "Hello, testing history"})
        chat_id = start_response.json()["chat_id"]

        # Get chat history
        response = self.client.get(f"/gemini/chats/{chat_id}")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) >= 2  # At least welcome + user message

    def test_list_chats_for_session(self):
        """Test listing all chats for a session."""
        # Start a chat
        self.client.post("/gemini/chats", json={"message": "Test for listing"})

        # List chats
        response = self.client.get("/gemini/chats")
        assert response.status_code == 200
        data = response.json()
        assert "chats" in data
        assert len(data["chats"]) >= 1


class TestSystemStockDetails:
    """System tests for stock details endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, api_base_url):
        """Set up HTTP client."""
        self.base_url = api_base_url
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def teardown_method(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def test_get_stock_details(self):
        """Test getting stock details for a ticker."""
        response = self.client.get("/details/AAPL")
        assert response.status_code == 200
        data = response.json()

        # Should have all three sections
        assert "company_profile" in data
        assert "stocks_data" in data
        assert "quant_model" in data

    def test_get_stock_details_multiple_tickers(self):
        """Test getting details for multiple tickers."""
        tickers = ["AAPL", "GOOGL", "MSFT"]

        for ticker in tickers:
            response = self.client.get(f"/details/{ticker}")
            assert response.status_code == 200


class TestSystemReportGeneration:
    """System tests for report generation."""

    @pytest.fixture(autouse=True)
    def setup(self, api_base_url):
        """Set up HTTP client."""
        self.base_url = api_base_url
        self.session_id = f"system-test-{uuid.uuid4()}"
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=60.0,
            headers={"X-Session-ID": self.session_id},
        )

    def teardown_method(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def test_generate_investment_report(self):
        """Test generating an investment report."""
        response = self.client.post(
            "/gemini/chats/system-test-chat/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report" in data
        assert "recommendations" in data["report"]

    def test_report_contains_stock_recommendations(self):
        """Test that report contains stock recommendations."""
        response = self.client.post(
            "/gemini/chats/system-test-chat/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": True,
                    "high_risk": True,
                    "low_risk": True,
                }
            },
        )

        assert response.status_code == 200
        recommendations = response.json()["report"]["recommendations"]

        if len(recommendations) > 0:
            rec = recommendations[0]
            assert "symbol" in rec
            assert "ai_score" in rec

    def test_get_generated_reports(self):
        """Test retrieving generated reports."""
        # Generate a report first
        self.client.post(
            "/gemini/chats/test-chat/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
        )

        # Get reports
        response = self.client.get("/gemini/reports")
        assert response.status_code == 200
        reports = response.json()
        assert len(reports) >= 1
