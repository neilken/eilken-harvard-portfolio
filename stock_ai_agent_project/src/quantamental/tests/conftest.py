"""
Pytest configuration and shared fixtures for Quantamental tests.

CRITICAL: This file patches GCS at module level to prevent test hangs.
The patches are applied when conftest.py is imported, which happens
BEFORE any test files are loaded.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import pandas as pd
import numpy as np

# Add quantamental src to path for imports
_quantamental_src_path = Path(__file__).parent.parent
if str(_quantamental_src_path) not in sys.path:
    sys.path.insert(0, str(_quantamental_src_path))

# ============================================================================
# CRITICAL: Patch storage.Client at module level BEFORE any test imports
# ============================================================================
# This runs when conftest.py is imported, which happens before test files
# This prevents real GCS connections that cause test hangs

# Create mock storage client that won't hang
_mock_storage_client = MagicMock()
_mock_storage_bucket = MagicMock()
_mock_storage_blob = MagicMock()

# Configure mock bucket behavior
_mock_storage_client.bucket.return_value = _mock_storage_bucket
_mock_storage_client.list_blobs.return_value = []
_mock_storage_bucket.blob.return_value = _mock_storage_blob
_mock_storage_blob.upload_from_filename.return_value = None
_mock_storage_blob.download_to_filename.return_value = None
_mock_storage_blob.exists.return_value = False
_mock_storage_blob.name = "test-blob"

# Patch storage.Client globally before any imports
_storage_patcher = patch(
    "google.cloud.storage.Client", return_value=_mock_storage_client
)
_storage_patcher.start()

# Also patch from_service_account_json
_storage_sa_patcher = patch(
    "google.cloud.storage.Client.from_service_account_json",
    return_value=_mock_storage_client,
)
_storage_sa_patcher.start()

# Patch in utils module specifically (in case it's already imported)
_patch_utils_storage = patch("utils.storage.Client", return_value=_mock_storage_client)
_patch_utils_storage.start()

_patch_utils_storage_sa = patch(
    "utils.storage.Client.from_service_account_json", return_value=_mock_storage_client
)
_patch_utils_storage_sa.start()


def pytest_configure(config):
    """Configure pytest - verify modules can be imported."""
    # Verify that utils can be imported without hanging
    try:
        import utils

        assert hasattr(utils, "GCSHandler")
    except Exception as e:
        print(f"Warning: Could not import utils: {e}")


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def sample_config():
    """Sample configuration dictionary for tests."""
    return {
        "api": {
            "fmp_api_key": "test-api-key",
            "base_url": "https://financialmodelingprep.com/api/v3",
            "concurrency": 5,
        },
        "data": {
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "data_dir": "./data",
        },
        "features": {
            "technical": ["RSI_14", "MACD", "EMA_12", "EMA_26"],
            "fundamental": ["roe", "roic", "peRatio", "debtToEquity"],
        },
        "wandb": {"project": "test-project", "api_key": "test-wandb-key"},
        "gcs": {
            "bucket_name": "test-bucket",
            "output_folder": "model_output",
            "credentials_path": None,
        },
        "processing": {"forward_fill_limit": 5, "backfill_limit": 5, "min_periods": 20},
    }


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV DataFrame for tests."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="D")

    return pd.DataFrame(
        {
            "symbol": ["AAPL"] * 100,
            "date": dates,
            "open": np.random.uniform(150, 200, 100),
            "high": np.random.uniform(200, 250, 100),
            "low": np.random.uniform(100, 150, 100),
            "close": np.random.uniform(150, 200, 100),
            "volume": np.random.randint(1000000, 10000000, 100),
            "adjClose": np.random.uniform(150, 200, 100),
        }
    )


@pytest.fixture
def sample_fundamentals_data():
    """Sample fundamentals DataFrame for tests."""
    return pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "date": ["2024-01-01"] * 3,
            "roe": [0.25, 0.30, 0.20],
            "roic": [0.15, 0.18, 0.12],
            "peRatio": [20.0, 25.0, 18.0],
            "debtToEquity": [1.5, 1.2, 0.8],
            "currentRatio": [2.0, 2.5, 3.0],
            "dividendYield": [0.02, 0.015, 0.01],
            "freeCashFlowYield": [0.05, 0.04, 0.06],
        }
    )


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client fixture."""
    return _mock_storage_client


@pytest.fixture
def mock_gcs_handler():
    """Mock GCSHandler instance."""
    from utils import GCSHandler

    return GCSHandler("test-bucket")


@pytest.fixture
def mock_async_session():
    """Mock aiohttp ClientSession for async tests."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"data": []})
    response.text = AsyncMock(return_value='{"data": []}')
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    session.get = AsyncMock(return_value=response)
    return session


@pytest.fixture
def mock_async_response():
    """Mock aiohttp response for async tests."""
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"data": []})
    response.text = AsyncMock(return_value='{"data": []}')
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.fixture(autouse=True)
def mock_time_sleep():
    """Auto-mock time.sleep to speed up tests."""
    with patch("time.sleep", return_value=None):
        yield


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary directory for test data."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return str(data_dir)


def _filtered_print(*args, **kwargs):
    """Filter out GCS-related error messages during tests."""
    msg = " ".join(str(arg) for arg in args)
    if (
        "google.cloud" in msg.lower()
        or "gcs" in msg.lower()
        or "credentials" in msg.lower()
    ):
        return  # Suppress GCS-related messages
    print(*args, **kwargs)
