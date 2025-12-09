"""
Pytest configuration and shared fixtures for API service tests.

CRITICAL: This file patches GCS and LLM dependencies at module level to prevent test hangs.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import pandas as pd
from io import BytesIO
import uuid

# Add api-service src to path for imports
_api_src_path = Path(__file__).parent.parent
if str(_api_src_path) not in sys.path:
    sys.path.insert(0, str(_api_src_path))

# ============================================================================
# CRITICAL: Patch storage.Client at module level BEFORE any test imports
# ============================================================================
_mock_storage_client = MagicMock()
_mock_storage_bucket = MagicMock()
_mock_storage_blob = MagicMock()

# Configure mock bucket behavior
_mock_storage_client.bucket.return_value = _mock_storage_bucket
_mock_storage_bucket.blob.return_value = _mock_storage_blob
_mock_storage_blob.download_as_bytes.return_value = b"test,data\n1,2\n3,4"
_mock_storage_blob.exists.return_value = True

# Patch storage.Client globally before any imports
_storage_patcher = patch("google.cloud.storage.Client", return_value=_mock_storage_client)
_storage_patcher.start()

_storage_sa_patcher = patch(
    "google.cloud.storage.Client.from_service_account_json",
    return_value=_mock_storage_client,
)
_storage_sa_patcher.start()

# Patch service account credentials - must be before any imports that use it
_credentials_patcher = patch(
    "google.oauth2.service_account.Credentials.from_service_account_file",
    return_value=MagicMock(),
)
_credentials_patcher.start()

# Also patch at the module level for chatbot_final and stock_details
_chatbot_credentials_patcher = patch(
    "api.routers.chatbot_final.service_account.Credentials.from_service_account_file",
    return_value=MagicMock(),
)
_chatbot_credentials_patcher.start()

# Patch ChatVertexAI
_llm_patcher = patch(
    "langchain_google_vertexai.ChatVertexAI",
    return_value=MagicMock(),
)
_llm_patcher.start()

# Patch MemorySaver
_memory_patcher = patch(
    "langgraph.checkpoint.memory.MemorySaver",
    return_value=MagicMock(),
)
_memory_patcher.start()

# Note: The storage.Client.from_service_account_json patch above ensures that
# when get_gcs_bucket.py initializes storage_client at module level, it gets
# the mocked client. Individual tests may need to patch get_gcs_data or
# provide mock dataframes for stock_details.py module-level calls.


def pytest_configure(config):
    """Configure pytest - verify modules can be imported."""
    try:
        # Verify that api modules can be imported without hanging
        pass
    except Exception as e:
        print(f"Warning: Could not import api modules: {e}")


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client fixture returning (client, bucket, blob)."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_bytes.return_value = b"symbol,value\nAAPL,100\nMSFT,200"

    return mock_client, mock_bucket, mock_blob


@pytest.fixture
def sample_quant_data():
    """Sample quantamental model DataFrame."""
    return pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOGL", "TSLA"],
            "Hybrid_Score": [0.85, 0.75, 0.65, 0.55],
            "Technical_Score": [0.80, 0.70, 0.60, 0.50],
            "Fundamental_Score": [0.90, 0.80, 0.70, 0.60],
            "H_Score Recommendation": [
                "Long-Term Buy (Fundamental)",
                "Short-Term Buy (Momentum)",
                "Long-Term Buy (Fundamental)",
                "Short-Term Buy (Momentum)",
            ],
            "volatility_21d": [0.02, 0.025, 0.03, 0.08],  # TSLA has high volatility
            "max_drawdown": [-0.05, -0.08, -0.10, -0.15],
            "sharpe_1m_annual": [1.5, 1.2, 1.0, 0.8],
            "cagr": [0.15, 0.12, 0.10, 0.08],
            "sector": ["Technology", "Technology", "Technology", "Consumer Cyclical"],
        }
    )


@pytest.fixture
def sample_company_profile():
    """Sample company profile DataFrame."""
    return pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "companyName": ["Apple Inc.", "Microsoft Corporation", "Alphabet Inc."],
            "industry": [
                "Consumer Electronics",
                "Software",
                "Internet Content & Information",
            ],
            "sector": ["Technology", "Technology", "Technology"],
            "country": ["United States", "United States", "United States"],
            "exchange": ["NASDAQ", "NASDAQ", "NASDAQ"],
            "marketCap": [3000000000000, 2500000000000, 2000000000000],
            "description": [
                "Test description for Apple Inc.",
                "Test description for Microsoft Corporation",
                "Test description for Alphabet Inc.",
            ],
        }
    )


@pytest.fixture
def sample_stocks_data():
    """Sample stocks OHLCV DataFrame."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.DataFrame(
        {
            "symbol": ["AAPL"] * 30 + ["MSFT"] * 30 + ["GOOGL"] * 30,
            "date": list(dates) * 3,
            "open": [150.0] * 90,
            "high": [155.0] * 90,
            "low": [148.0] * 90,
            "close": [152.0] * 90,
            "volume": [1000000] * 90,
        }
    )


@pytest.fixture
def user_preferences_long_term():
    """User preferences for long-term, low-risk investment."""
    return {
        "long_term": True,
        "short_term": False,
        "high_risk": False,
        "low_risk": True,
    }


@pytest.fixture
def user_preferences_short_term():
    """User preferences for short-term, high-risk investment."""
    return {
        "long_term": False,
        "short_term": True,
        "high_risk": True,
        "low_risk": False,
    }


@pytest.fixture
def user_preferences_balanced():
    """User preferences for balanced investment."""
    return {"long_term": True, "short_term": True, "high_risk": True, "low_risk": True}


@pytest.fixture
def mock_model():
    """Mock ChatVertexAI LLM."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Test AI response")
    llm.with_structured_output.return_value.invoke.return_value = MagicMock(
        model_dump=lambda: {
            "long_term": True,
            "short_term": False,
            "high_risk": False,
            "low_risk": True,
            "completed": True,
            "confirmation": False,
        }
    )
    return llm


@pytest.fixture
def mock_checkpointer():
    """Mock MemorySaver checkpointer."""
    return MagicMock()


@pytest.fixture
def api_base_url():
    """API base URL for system tests."""
    import os

    return os.environ.get("API_BASE_URL", "http://localhost:9000")


@pytest.fixture
def test_session_id():
    """Generate a unique test session ID."""
    return f"test-session-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def mock_time_sleep():
    """Auto-mock time.sleep to speed up tests."""
    with patch("time.sleep", return_value=None):
        yield
