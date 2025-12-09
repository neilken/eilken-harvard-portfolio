"""
Unit tests for API router endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
import pandas as pd

pytestmark = pytest.mark.unit


class TestChatbotRouterUnit:
    """Unit tests for chatbot_final router endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test client with mocked dependencies."""
        with (
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI") as mock_llm_class,
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent_class,
            patch("api.routers.chatbot_final.memory"),
            patch("api.routers.stock_details.get_gcs_data"),
            patch("api.routers.stock_details.df_quant_model"),
            patch("api.routers.stock_details.df_company_profile"),
            patch("api.routers.stock_details.df_stocks"),
        ):

            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()

            mock_agent = MagicMock()
            mock_agent.graph.invoke.return_value = {"messages": [MagicMock(content="Test AI response")], "user_pref": {}}
            mock_agent_class.return_value = mock_agent

            from api.routers import chatbot_final

            chatbot_final.chat_sessions.clear()
            chatbot_final.abot = mock_agent

            from api.service import app

            self.client = TestClient(app)
            self.mock_agent = mock_agent
            yield

    def test_get_chats_with_existing_sessions(self):
        """Test getting chats when sessions exist."""
        from api.routers import chatbot_final

        # Create a test session
        test_chat_id = "test-chat-123"
        chatbot_final.chat_sessions[test_chat_id] = {
            "user_id": "test-session-456",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "user_preferences": None,
        }

        response = self.client.get("/gemini/chats", headers={"X-Session-ID": "test-session-456"})
        assert response.status_code == 200
        data = response.json()
        assert "chats" in data
        assert len(data["chats"]) == 1
        assert data["chats"][0]["chat_id"] == test_chat_id

    def test_get_chats_with_limit(self):
        """Test getting chats with limit parameter."""
        from api.routers import chatbot_final

        # Create multiple test sessions
        for i in range(5):
            chatbot_final.chat_sessions[f"chat-{i}"] = {
                "user_id": "test-session",
                "messages": [{"role": "user", "content": f"Message {i}"}],
                "user_preferences": None,
            }

        response = self.client.get("/gemini/chats?limit=2", headers={"X-Session-ID": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["chats"]) == 2

    def test_get_chats_title_generation(self):
        """Test that chat titles are generated from first user message."""
        from api.routers import chatbot_final

        chatbot_final.chat_sessions["test-chat"] = {
            "user_id": "test-session",
            "messages": [
                {"role": "assistant", "content": "Welcome"},
                {"role": "user", "content": "This is a very long message that should be truncated to 50 characters"},
                {"role": "assistant", "content": "Response"},
            ],
            "user_preferences": None,
        }

        response = self.client.get("/gemini/chats", headers={"X-Session-ID": "test-session"})
        assert response.status_code == 200
        data = response.json()
        # Title should be first 50 chars + "..." if longer (53 chars total)
        title = data["chats"][0]["title"]
        assert title == "This is a very long message that should be truncat..."
        assert len(title) == 53  # 50 chars + "..."

    def test_get_chat_success(self):
        """Test getting a specific chat successfully."""
        from api.routers import chatbot_final

        test_chat_id = "test-chat-id"
        chatbot_final.chat_sessions[test_chat_id] = {
            "user_id": "test-session",
            "messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
            "user_preferences": {"long_term": True},
        }

        response = self.client.get(f"/gemini/chats/{test_chat_id}", headers={"X-Session-ID": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == test_chat_id
        assert len(data["messages"]) == 2
        assert data["user_preferences"] == {"long_term": True}

    def test_get_chat_access_denied(self):
        """Test getting chat with wrong session ID returns 403."""
        from api.routers import chatbot_final

        test_chat_id = "test-chat-id"
        chatbot_final.chat_sessions[test_chat_id] = {"user_id": "owner-session", "messages": [], "user_preferences": None}

        response = self.client.get(f"/gemini/chats/{test_chat_id}", headers={"X-Session-ID": "different-session"})
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    def test_start_chat_with_user_pref(self):
        """Test starting chat that returns user preferences."""
        from api.routers import chatbot_final

        self.mock_agent.graph.invoke.return_value = {
            "messages": [MagicMock(content="Thank you!")],
            "user_pref": {
                "long_term": True,
                "short_term": False,
                "high_risk": False,
                "low_risk": True,
                "completed": True,
                "confirmation": True,
            },
        }

        response = self.client.post(
            "/gemini/chats", json={"message": "My name is John"}, headers={"X-Session-ID": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True
        assert data["user_preferences"] is not None
        assert data["user_preferences"]["long_term"] is True

    def test_continue_chat_success(self):
        """Test continuing a chat successfully."""
        from api.routers import chatbot_final

        test_chat_id = "continue-chat-id"
        chatbot_final.chat_sessions[test_chat_id] = {
            "user_id": "test-session",
            "messages": [{"role": "assistant", "content": "Welcome"}, {"role": "user", "content": "Hello"}],
            "user_preferences": None,
        }

        self.mock_agent.graph.invoke.return_value = {"messages": [MagicMock(content="How can I help?")], "user_pref": {}}

        response = self.client.post(
            f"/gemini/chats/{test_chat_id}", json={"message": "I prefer long term"}, headers={"X-Session-ID": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == test_chat_id
        assert "message" in data

    def test_continue_chat_with_user_pref_update(self):
        """Test continuing chat that updates user preferences."""
        from api.routers import chatbot_final

        test_chat_id = "pref-update-chat"
        chatbot_final.chat_sessions[test_chat_id] = {
            "user_id": "test-session",
            "messages": [{"role": "user", "content": "Hello"}],
            "user_preferences": None,
        }

        self.mock_agent.graph.invoke.return_value = {
            "messages": [MagicMock(content="Got it!")],
            "user_pref": {
                "long_term": True,
                "short_term": False,
                "high_risk": False,
                "low_risk": True,
                "completed": True,
                "confirmation": False,
            },
        }

        response = self.client.post(
            f"/gemini/chats/{test_chat_id}", json={"message": "Long term, low risk"}, headers={"X-Session-ID": "test-session"}
        )
        assert response.status_code == 200
        # Verify preferences were stored
        assert chatbot_final.chat_sessions[test_chat_id]["user_preferences"] is not None

    def test_continue_chat_access_denied(self):
        """Test continuing chat with wrong session ID returns 403."""
        from api.routers import chatbot_final

        test_chat_id = "protected-chat"
        chatbot_final.chat_sessions[test_chat_id] = {"user_id": "owner-session", "messages": [], "user_preferences": None}

        response = self.client.post(
            f"/gemini/chats/{test_chat_id}", json={"message": "Test"}, headers={"X-Session-ID": "wrong-session"}
        )
        assert response.status_code == 403


class TestStockDetailsRouterUnit:
    """Unit tests for stock_details router endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_quant_data, sample_company_profile, sample_stocks_data):
        """Set up test client with mocked dependencies."""
        with (
            patch("api.routers.chatbot_final.service_account") as mock_sa,
            patch("api.routers.chatbot_final.ChatVertexAI"),
            patch("api.routers.chatbot_final.ChatAgent") as mock_agent_class,
            patch("api.routers.chatbot_final.memory"),
            patch("api.routers.stock_details.get_gcs_data") as mock_gcs,
            patch("api.routers.stock_details.df_quant_model", sample_quant_data),
            patch("api.routers.stock_details.df_company_profile", sample_company_profile),
            patch("api.routers.stock_details.df_stocks", sample_stocks_data),
        ):

            mock_sa.Credentials.from_service_account_file.return_value = MagicMock()
            mock_agent = MagicMock()
            mock_agent.graph.invoke.return_value = {"messages": [MagicMock(content="Test")], "user_pref": {}}
            mock_agent_class.return_value = mock_agent

            from api.service import app
            from api.routers import stock_details

            stock_details.reports_storage.clear()

            self.client = TestClient(app)
            self.sample_quant = sample_quant_data
            self.sample_company = sample_company_profile
            self.sample_stocks = sample_stocks_data
            yield

    def test_get_details_success(self):
        """Test getting stock details successfully."""
        response = self.client.get("/details/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert "company_profile" in data
        assert "stocks_data" in data
        assert "quant_model" in data

    def test_get_details_handles_missing_data(self):
        """Test getting details for ticker with missing data."""
        response = self.client.get("/details/INVALID")
        assert response.status_code == 200
        data = response.json()
        # Should handle gracefully even if data is missing
        assert "company_profile" in data

    def test_generate_report_short_term_only(self):
        """Test generating report with short-term only preference."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": False, "short_term": True, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data["report"]

    def test_generate_report_long_term_only(self):
        """Test generating report with long-term only preference."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_generate_report_both_terms(self):
        """Test generating report with both long and short term."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": True, "short_term": True, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_generate_report_neither_term(self):
        """Test generating report with neither long nor short term."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": False, "short_term": False, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_generate_report_handles_empty_recommendations(self):
        """Test generating report when no stocks match criteria."""
        # Create empty quant model
        empty_df = pd.DataFrame(
            columns=["symbol", "Hybrid_Score", "H_Score Recommendation", "volatility_21d", "max_drawdown", "sector"]
        )

        with patch("api.routers.stock_details.df_quant_model", empty_df):
            response = self.client.post(
                "/gemini/chats/test-chat/report",
                json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
                headers={"X-Session-ID": "test-session"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["report"]["recommendations"]) == 0

    def test_generate_report_handles_missing_scores(self):
        """Test generating report when stock data has missing scores."""
        # Create df with missing scores
        df_with_nans = pd.DataFrame(
            {
                "symbol": ["TEST"],
                "Hybrid_Score": [None],
                "Technical_Score": [None],
                "Fundamental_Score": [None],
                "H_Score Recommendation": ["Long-Term Buy (Fundamental)"],
                "volatility_21d": [0.02],
                "max_drawdown": [-0.05],
                "sharpe_1m_annual": [None],
                "cagr": [None],
                "sector": ["Technology"],
            }
        )

        with patch("api.routers.stock_details.df_quant_model", df_with_nans):
            response = self.client.post(
                "/gemini/chats/test-chat/report",
                json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
                headers={"X-Session-ID": "test-session"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_generate_report_sorts_by_score(self):
        """Test that recommendations are sorted by ai_score descending."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        recommendations = data["report"]["recommendations"]

        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i]["ai_score"] >= recommendations[i + 1]["ai_score"]

    def test_generate_report_contains_summary(self):
        """Test that report contains summary information."""
        response = self.client.post(
            "/gemini/chats/test-chat/report",
            json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
            headers={"X-Session-ID": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data["report"]
        assert "total_recommendations" in data["report"]["summary"]
        assert "investment_horizon" in data["report"]["summary"]

    def test_get_reports_empty_initially(self):
        """Test getting reports returns empty list initially."""
        response = self.client.get("/gemini/reports", headers={"X-Session-ID": "new-session"})
        assert response.status_code == 200
        assert response.json() == []

    def test_get_reports_with_limit(self):
        """Test getting reports with limit parameter."""
        from api.routers import stock_details

        # Generate multiple reports
        for i in range(5):
            self.client.post(
                f"/gemini/chats/chat-{i}/report",
                json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
                headers={"X-Session-ID": "limit-test-session"},
            )

        response = self.client.get("/gemini/reports?limit=2", headers={"X-Session-ID": "limit-test-session"})
        assert response.status_code == 200
        reports = response.json()
        assert len(reports) == 2

    def test_get_report_endpoint(self):
        """Test the /report endpoint with user preferences."""
        user_pref = "{'long_term': True, 'short_term': False, 'high_risk': False, 'low_risk': True}"
        response = self.client.get(f"/report?user_pref={user_pref}")
        assert response.status_code == 200
        assert "stocks" in response.json()

    def test_generate_report_error_handling(self):
        """Test that generate_report handles errors gracefully."""
        # Patch user_pref_stock_selection to raise an error
        with patch("api.routers.stock_details.user_pref_stock_selection", side_effect=Exception("Test error")):
            response = self.client.post(
                "/gemini/chats/test-chat/report",
                json={"user_pref": {"long_term": True, "short_term": False, "high_risk": False, "low_risk": True}},
                headers={"X-Session-ID": "test-session"},
            )
            assert response.status_code == 500
