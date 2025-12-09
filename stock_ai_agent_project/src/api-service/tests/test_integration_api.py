"""
Integration tests for API endpoints.

Tests the FastAPI routers with mocked external dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestChatbotEndpoints:
    """Integration tests for chatbot router endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, sample_quant_data, sample_company_profile, sample_stocks_data):
        """Set up test client with mocked dependencies."""
        self.sample_quant = sample_quant_data
        self.sample_company = sample_company_profile
        self.sample_stocks = sample_stocks_data

        with (
            patch("api.utils.get_gcs_bucket.storage"),
            patch("api.utils.get_gcs_bucket.get_gcs_data") as mock_gcs,
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI") as mock_llm_class,
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent_class,
            patch("api.routers.chatbot_final.memory"),
            patch("api.routers.stock_details.get_gcs_data") as mock_gcs_details,
            patch("api.routers.stock_details.df_quant_model", sample_quant_data),
            patch("api.routers.stock_details.df_company_profile", sample_company_profile),
            patch("api.routers.stock_details.df_stocks", sample_stocks_data),
        ):

            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()

            mock_agent = MagicMock()
            mock_agent.graph.invoke.return_value = {
                "messages": [MagicMock(content="Hello! I'm here to help.")],
                "user_pref": {},
            }
            mock_agent_class.return_value = mock_agent

            from api.routers import chatbot_final

            chatbot_final.chat_sessions.clear()
            chatbot_final.abot = mock_agent

            from api.service import app

            self.client = TestClient(app)
            self.mock_agent = mock_agent
            yield

    # GET /chats tests
    def test_get_chats_requires_session_header(self):
        """Test that X-Session-ID header is required."""
        response = self.client.get("/gemini/chats")
        assert response.status_code == 400
        assert "X-Session-ID" in response.json()["detail"]

    def test_get_chats_empty_for_new_session(self):
        """Test empty chats list for new session."""
        response = self.client.get("/gemini/chats", headers={"X-Session-ID": "new-session-123"})
        assert response.status_code == 200
        assert response.json() == {"chats": []}

    def test_get_chats_with_limit(self):
        """Test chats list respects limit parameter."""
        response = self.client.get("/gemini/chats?limit=5", headers={"X-Session-ID": "test-session"})
        assert response.status_code == 200

    # POST /chats (start chat) tests
    def test_start_chat_requires_session_header(self):
        """Test that starting chat requires session header."""
        response = self.client.post("/gemini/chats", json={"message": "Hello"})
        assert response.status_code == 400

    def test_start_chat_requires_message(self):
        """Test that starting chat requires message content."""
        response = self.client.post("/gemini/chats", json={}, headers={"X-Session-ID": "test-session"})
        assert response.status_code == 400

    def test_start_chat_success(self):
        """Test successful chat start."""
        response = self.client.post(
            "/gemini/chats",
            json={"message": "My name is John"},
            headers={"X-Session-ID": "test-session-456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "chat_id" in data
        assert "message" in data
        assert data["completed"] is False

    def test_start_chat_returns_valid_chat_id(self):
        """Test that chat_id is a valid UUID format."""
        response = self.client.post(
            "/gemini/chats",
            json={"message": "Hello"},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        chat_id = response.json()["chat_id"]
        assert len(chat_id) == 36  # UUID format

    # GET /chats/{chat_id} tests
    def test_get_specific_chat_not_found(self):
        """Test 404 for non-existent chat."""
        response = self.client.get("/gemini/chats/non-existent-id", headers={"X-Session-ID": "test-session"})
        assert response.status_code == 404

    def test_get_specific_chat_requires_session(self):
        """Test getting specific chat requires session header."""
        response = self.client.get("/gemini/chats/some-chat-id")
        assert response.status_code == 400

    # POST /chats/{chat_id} (continue chat) tests
    def test_continue_chat_not_found(self):
        """Test continuing non-existent chat returns 404."""
        response = self.client.post(
            "/gemini/chats/non-existent-id",
            json={"message": "Continue"},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 404

    def test_continue_chat_requires_session(self):
        """Test continuing chat requires session header."""
        response = self.client.post("/gemini/chats/some-id", json={"message": "Continue"})
        assert response.status_code == 400


class TestStockDetailsEndpoints:
    """Integration tests for stock details router endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, sample_quant_data, sample_company_profile, sample_stocks_data):
        """Set up test client with mocked dependencies."""
        with (
            patch("api.utils.get_gcs_bucket.storage"),
            patch("api.utils.get_gcs_bucket.get_gcs_data"),
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI"),
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent_class,
            patch("api.routers.chatbot_final.memory"),
            patch("api.routers.stock_details.df_quant_model", sample_quant_data),
            patch("api.routers.stock_details.df_company_profile", sample_company_profile),
            patch("api.routers.stock_details.df_stocks", sample_stocks_data),
        ):

            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()
            mock_agent = MagicMock()
            mock_agent.graph.invoke.return_value = {
                "messages": [MagicMock(content="Test")],
                "user_pref": {},
            }
            mock_agent_class.return_value = mock_agent

            from api.service import app

            self.client = TestClient(app)
            yield

    # GET /details/{ticker} tests
    def test_get_details_existing_ticker(self):
        """Test getting details for existing ticker."""
        response = self.client.get("/details/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert "company_profile" in data
        assert "stocks_data" in data
        assert "quant_model" in data

    def test_get_details_lowercase_ticker(self):
        """Test getting details with lowercase ticker."""
        response = self.client.get("/details/aapl")
        assert response.status_code == 200

    def test_get_details_nonexistent_ticker(self):
        """Test getting details for non-existent ticker."""
        response = self.client.get("/details/INVALID")
        assert response.status_code == 200
        data = response.json()
        assert data["company_profile"] == 0
        assert data["quant_model"] == 0

    def test_get_details_returns_all_sections(self):
        """Test that response contains all required sections."""
        response = self.client.get("/details/GOOGL")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    # GET /report tests
    def test_get_report_with_preferences(self):
        """Test get recommended stocks with user preferences."""
        user_pref = "{'long_term': True, 'short_term': False, 'high_risk': False, 'low_risk': True}"
        response = self.client.get(f"/report?user_pref={user_pref}")
        assert response.status_code == 200
        assert "stocks" in response.json()

    # GET /reports tests
    def test_get_reports_empty_for_new_session(self):
        """Test get reports returns empty for new session."""
        response = self.client.get("/gemini/reports", headers={"X-Session-ID": "new-session"})
        assert response.status_code == 200
        assert response.json() == []


class TestReportGenerationEndpoints:
    """Integration tests for report generation endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, sample_quant_data, sample_company_profile, sample_stocks_data):
        """Set up test client with mocked dependencies."""
        with (
            patch("api.utils.get_gcs_bucket.storage"),
            patch("api.utils.get_gcs_bucket.get_gcs_data"),
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI"),
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent_class,
            patch("api.routers.chatbot_final.memory"),
            patch("api.routers.stock_details.df_quant_model", sample_quant_data),
            patch("api.routers.stock_details.df_company_profile", sample_company_profile),
            patch("api.routers.stock_details.df_stocks", sample_stocks_data),
        ):

            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()
            mock_agent = MagicMock()
            mock_agent.graph.invoke.return_value = {
                "messages": [MagicMock(content="Test")],
                "user_pref": {},
            }
            mock_agent_class.return_value = mock_agent

            from api.service import app
            from api.routers import stock_details

            stock_details.reports_storage.clear()

            self.client = TestClient(app)
            yield

    def test_generate_report_long_term_preferences(self):
        """Test generating report with long-term preferences."""
        response = self.client.post(
            "/gemini/chats/test-chat-id/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report" in data
        assert "recommendations" in data["report"]

    def test_generate_report_short_term_preferences(self):
        """Test generating report with short-term preferences."""
        response = self.client.post(
            "/gemini/chats/test-chat-id/report",
            json={
                "user_pref": {
                    "long_term": False,
                    "short_term": True,
                    "high_risk": True,
                    "low_risk": False,
                }
            },
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_generate_report_balanced_preferences(self):
        """Test generating report with balanced preferences."""
        response = self.client.post(
            "/gemini/chats/test-chat-id/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": True,
                    "high_risk": True,
                    "low_risk": True,
                }
            },
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data["report"]

    def test_generate_report_contains_report_id(self):
        """Test that generated report contains report_id."""
        response = self.client.post(
            "/gemini/chats/test-chat-id/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        assert "report_id" in response.json()["report"]

    def test_generate_report_stored_in_session(self):
        """Test that generated report is stored in session."""
        session_id = "persistent-session"

        self.client.post(
            "/gemini/chats/chat-1/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
            headers={"X-Session-ID": session_id},
        )

        response = self.client.get("/gemini/reports", headers={"X-Session-ID": session_id})
        assert response.status_code == 200
        reports = response.json()
        assert len(reports) == 1

    def test_generate_multiple_reports_same_session(self):
        """Test generating multiple reports in same session."""
        session_id = "multi-report-session"

        # Generate first report
        self.client.post(
            "/gemini/chats/chat-1/report",
            json={
                "user_pref": {
                    "long_term": True,
                    "short_term": False,
                    "high_risk": False,
                    "low_risk": True,
                }
            },
            headers={"X-Session-ID": session_id},
        )

        # Generate second report
        self.client.post(
            "/gemini/chats/chat-2/report",
            json={
                "user_pref": {
                    "long_term": False,
                    "short_term": True,
                    "high_risk": True,
                    "low_risk": False,
                }
            },
            headers={"X-Session-ID": session_id},
        )

        response = self.client.get("/gemini/reports", headers={"X-Session-ID": session_id})
        assert len(response.json()) == 2

    def test_reports_sorted_by_date(self):
        """Test that reports are sorted by generated_at descending."""
        session_id = "sorted-reports-session"

        # Generate multiple reports
        for i in range(3):
            self.client.post(
                f"/gemini/chats/chat-{i}/report",
                json={
                    "user_pref": {
                        "long_term": True,
                        "short_term": False,
                        "high_risk": False,
                        "low_risk": True,
                    }
                },
                headers={"X-Session-ID": session_id},
            )

        response = self.client.get("/gemini/reports", headers={"X-Session-ID": session_id})
        reports = response.json()

        # Verify sorted by date descending
        for i in range(len(reports) - 1):
            assert reports[i]["generated_at"] >= reports[i + 1]["generated_at"]
