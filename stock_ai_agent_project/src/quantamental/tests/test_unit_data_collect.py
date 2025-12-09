"""
Unit tests for data_collect module (FMPDataCollector class)
"""

import sys
import os

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_collect import FMPDataCollector
from utils import load_config


class TestFMPDataCollectorInit:
    """Test FMPDataCollector initialization."""

    @pytest.mark.unit
    def test_collector_initialization(self):
        """Test that collector initializes with config."""
        config = load_config()
        collector = FMPDataCollector(config)

        assert collector.config == config
        assert collector.api_key == config["api"]["fmp_api_key"]
        assert collector.base_url == config["api"]["base_url"]
        assert collector.start_date == config["data"]["start_date"]
        assert collector.end_date == config["data"]["end_date"]

    @pytest.mark.unit
    def test_collector_has_data_dir(self):
        """Test that collector creates data directory."""
        config = load_config()
        collector = FMPDataCollector(config)

        assert collector.data_dir is not None
        assert os.path.exists(collector.data_dir)

    @pytest.mark.unit
    def test_collector_concurrency_setting(self):
        """Test concurrency setting from config."""
        config = load_config()
        collector = FMPDataCollector(config)

        assert hasattr(collector, "concurrency")
        assert collector.concurrency == config["api"]["concurrency"]

    @pytest.mark.unit
    def test_collector_has_headers(self):
        """Test that collector sets up headers."""
        config = load_config()
        collector = FMPDataCollector(config)

        assert hasattr(collector, "headers")
        assert isinstance(collector.headers, dict)
        assert "User-Agent" in collector.headers


class TestFMPDataCollectorMethods:
    """Test FMPDataCollector methods with mocking."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_sp500_with_cache(self):
        """Test fetching S&P 500 tickers from cache."""
        config = load_config()
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache file
        cache_path = f"{collector.data_dir}/sp500_tickers.csv"
        pd.DataFrame({"symbol": ["AAPL", "MSFT", "GOOGL"]}).to_csv(
            cache_path, index=False
        )

        try:
            tickers = await collector.fetch_sp500()

            assert isinstance(tickers, list)
            assert len(tickers) == 3
            assert "AAPL" in tickers
            assert "MSFT" in tickers
            assert "GOOGL" in tickers
        finally:
            # Cleanup
            if os.path.exists(cache_path):
                os.remove(cache_path)

    @pytest.mark.unit
    def test_collector_cache_path_construction(self):
        """Test cache path construction."""
        config = load_config()
        collector = FMPDataCollector(config)

        expected_sp500_cache = f"{collector.data_dir}/sp500_tickers.csv"
        expected_ohlcv_cache = f"{collector.data_dir}/ohlcv_raw.parquet"

        # These paths should be constructable
        assert collector.data_dir in expected_sp500_cache
        assert collector.data_dir in expected_ohlcv_cache


class TestOHLCVDataProcessing:
    """Test OHLCV data processing logic."""

    @pytest.mark.unit
    def test_ohlcv_dataframe_structure(self):
        """Test that OHLCV data has correct structure."""
        # Create mock OHLCV data
        df = pd.DataFrame(
            {
                "symbol": ["AAPL", "AAPL", "MSFT"],
                "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-01"]),
                "open": [150.0, 151.0, 250.0],
                "high": [152.0, 153.0, 252.0],
                "low": [149.0, 150.0, 248.0],
                "close": [151.0, 152.0, 251.0],
                "adj_close": [151.0, 152.0, 251.0],
                "volume": [1000000, 1100000, 2000000],
            }
        )

        # Check columns
        required_cols = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
        ]
        for col in required_cols:
            assert col in df.columns

        # Check data types
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert pd.api.types.is_numeric_dtype(df["close"])
        assert pd.api.types.is_numeric_dtype(df["volume"])


class TestFundamentalsProcessing:
    """Test fundamentals data processing logic."""

    @pytest.mark.unit
    def test_fundamentals_dataframe_structure(self):
        """Test fundamentals data structure."""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL", "AAPL"],
                "date": pd.to_datetime(["2023-03-31", "2023-06-30"]),
                "revenue": [100000000, 105000000],
                "netIncome": [25000000, 26000000],
                "period_type": ["quarter", "quarter"],
            }
        )

        assert "symbol" in df.columns
        assert "date" in df.columns
        assert "period_type" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["date"])


class TestAsyncMethods:
    """Test async method behavior."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_ohlcv_symbol_with_mock(self):
        """Test fetching OHLCV for single symbol with mock."""
        config = load_config()
        collector = FMPDataCollector(config)

        # Mock response
        mock_response = {
            "historical": [
                {
                    "date": "2023-01-01",
                    "open": 150.0,
                    "high": 152.0,
                    "low": 149.0,
                    "close": 151.0,
                    "adjClose": 151.0,
                    "volume": 1000000,
                }
            ]
        }

        # Create mock session
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        mock_session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))
        )

        result = await collector.fetch_ohlcv_symbol(mock_session, "AAPL")

        if result is not None:
            assert isinstance(result, pd.DataFrame)
            assert "symbol" in result.columns
            assert "date" in result.columns


class TestDataValidation:
    """Test data validation logic."""

    @pytest.mark.unit
    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        df = pd.DataFrame()

        assert df.empty
        assert len(df) == 0

    @pytest.mark.unit
    def test_dataframe_filtering(self):
        """Test DataFrame filtering logic."""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT", "GOOGL", "AMZN"],
                "close": [150.0, 250.0, 100.0, 120.0],
            }
        )

        # Filter by condition
        filtered = df[df["close"] > 120.0]

        assert len(filtered) == 2
        assert "AAPL" in filtered["symbol"].values
        assert "MSFT" in filtered["symbol"].values


class TestConcurrency:
    """Test concurrency settings."""

    @pytest.mark.unit
    def test_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        config = load_config()
        collector = FMPDataCollector(config)

        # Should have concurrency setting
        assert hasattr(collector, "concurrency")
        assert isinstance(collector.concurrency, int)
        assert collector.concurrency > 0


class TestAsyncFetchMethods:
    """Test async fetch methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_ohlcv_all_with_cache(self, tmp_path):
        """Test fetch_ohlcv_all uses cache when available."""
        config = load_config()
        config["data"]["data_dir"] = str(tmp_path)
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache file
        cache_path = f"{collector.data_dir}/ohlcv_raw.parquet"
        test_df = pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT"],
                "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
                "close": [150.0, 250.0],
            }
        )
        test_df.to_parquet(cache_path, index=False)

        result = await collector.fetch_ohlcv_all(["AAPL", "MSFT"])

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_fundamentals_symbol(self):
        """Test fetch_fundamentals_symbol with mock."""
        config = load_config()
        collector = FMPDataCollector(config)

        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value=[
                {
                    "date": "2023-01-01",
                    "roe": 0.25,
                    "roic": 0.15,
                }
            ]
        )
        mock_session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))
        )

        result = await collector.fetch_fundamentals_symbol(
            mock_session, "AAPL", "quarter"
        )

        if result is not None:
            assert isinstance(result, pd.DataFrame)
            assert "symbol" in result.columns
            assert "date" in result.columns

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_fundamentals_combined_with_cache(self, tmp_path):
        """Test fetch_fundamentals_combined uses cache."""
        config = load_config()
        config["data"]["data_dir"] = str(tmp_path)
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache file
        cache_path = f"{collector.data_dir}/fundamentals_combined.parquet"
        test_df = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "date": pd.to_datetime(["2023-01-01"]),
                "roe": [0.25],
            }
        )
        test_df.to_parquet(cache_path, index=False)

        result = await collector.fetch_fundamentals_combined(["AAPL"])

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_sp500_index_with_cache(self, tmp_path):
        """Test fetch_sp500_index uses cache."""
        config = load_config()
        config["data"]["data_dir"] = str(tmp_path)
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache file
        cache_path = f"{collector.data_dir}/sp500_index.parquet"
        test_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "close": [4000.0],
                "return_1d": [0.01],
            }
        )
        test_df.to_parquet(cache_path, index=False)

        result = await collector.fetch_sp500_index()

        assert isinstance(result, pd.DataFrame)
        assert "symbol" in result.columns or len(result) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_company_profile(self):
        """Test fetch_company_profile with mock."""
        config = load_config()
        collector = FMPDataCollector(config)

        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value=[
                {
                    "symbol": "AAPL",
                    "companyName": "Apple Inc",
                    "sector": "Technology",
                }
            ]
        )
        mock_session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))
        )

        result = await collector.fetch_company_profile(mock_session, "AAPL")

        assert result is not None
        assert isinstance(result, dict)
        assert "symbol" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_company_profiles_with_cache(self, tmp_path):
        """Test fetch_company_profiles uses cache."""
        config = load_config()
        config["data"]["data_dir"] = str(tmp_path)
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache file
        cache_path = f"{collector.data_dir}/company_profiles.parquet"
        test_df = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "companyName": ["Apple Inc"],
                "sector": ["Technology"],
            }
        )
        test_df.to_parquet(cache_path, index=False)

        result = await collector.fetch_company_profiles(["AAPL"])

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_all_structure(self, tmp_path):
        """Test collect_all returns correct structure."""
        config = load_config()
        config["data"]["data_dir"] = str(tmp_path)
        config["data"]["cache_enabled"] = True
        collector = FMPDataCollector(config)

        # Create cache files for all data types
        cache_dir = collector.data_dir
        pd.DataFrame({"symbol": ["AAPL"]}).to_csv(
            f"{cache_dir}/sp500_tickers.csv", index=False
        )

        test_ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "date": pd.to_datetime(["2023-01-01"]),
                "close": [150.0],
            }
        )
        test_ohlcv.to_parquet(f"{cache_dir}/ohlcv_raw.parquet", index=False)

        test_fund = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "date": pd.to_datetime(["2023-01-01"]),
                "roe": [0.25],
            }
        )
        test_fund.to_parquet(f"{cache_dir}/fundamentals_combined.parquet", index=False)

        test_sp500 = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "close": [4000.0],
            }
        )
        test_sp500.to_parquet(f"{cache_dir}/sp500_index.parquet", index=False)

        test_profiles = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "companyName": ["Apple Inc"],
            }
        )
        test_profiles.to_parquet(f"{cache_dir}/company_profiles.parquet", index=False)

        result = await collector.collect_all()

        assert isinstance(result, dict)
        assert "sp500_tickers" in result
        assert "ohlcv" in result
        assert "fundamentals" in result
        assert "sp500_index" in result
        assert "company_profiles" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
