"""
INTEGRATION TESTS - Data Pipeline Flow
Tests complete data processing pipeline with multiple modules
"""

import sys
import os

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_process import DataProcessor
from utils import load_config


class TestDataProcessingPipeline:
    """Integration tests for complete data processing pipeline."""

    @pytest.mark.integration
    def test_complete_processing_pipeline_with_mock_data(self):
        """Test entire processing pipeline with mock data."""
        config = load_config()
        processor = DataProcessor(config)

        # Create comprehensive mock data
        n_days = 100
        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * n_days + ["MSFT"] * n_days,
                "date": pd.date_range("2023-01-01", periods=n_days).tolist() * 2,
                "open": np.random.uniform(140, 160, n_days * 2),
                "high": np.random.uniform(145, 165, n_days * 2),
                "low": np.random.uniform(135, 155, n_days * 2),
                "close": np.random.uniform(140, 160, n_days * 2),
                "volume": np.random.uniform(1000000, 2000000, n_days * 2),
            }
        )

        fundamentals = pd.DataFrame(
            {
                "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
                "date": pd.to_datetime(
                    ["2023-01-01", "2023-02-01", "2023-01-01", "2023-02-01"]
                ),
                "revenue": [100000, 105000, 200000, 205000],
                "netIncome": [25000, 26000, 50000, 51000],
            }
        )

        _sp500_index = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-01", periods=n_days),
                "close": np.random.uniform(4000, 4200, n_days),
            }
        )

        processor.fund_cols = ["revenue", "netIncome"]

        # Run pipeline steps
        ohlcv_ta = processor.compute_technicals(ohlcv)
        assert len(ohlcv_ta) == n_days * 2
        assert "return_1d" in ohlcv_ta.columns
        assert "ema_12" in ohlcv_ta.columns
        assert "macd" in ohlcv_ta.columns

        merged = processor.merge_fundamentals(ohlcv_ta, fundamentals)
        assert len(merged) > 0
        assert "revenue" in merged.columns

        cleaned = processor.clean_data(merged)
        assert len(cleaned) > 0

    @pytest.mark.integration
    def test_technical_indicators_flow(self):
        """Test technical indicator computation with realistic data flow."""
        config = load_config()
        processor = DataProcessor(config)

        # Create price data with trend
        dates = pd.date_range("2023-01-01", periods=100)
        base_prices = 100 + np.cumsum(np.random.randn(100) * 2)

        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 100,
                "date": dates,
                "open": base_prices + np.random.randn(100),
                "high": base_prices + np.random.randn(100) + 2,
                "low": base_prices + np.random.randn(100) - 2,
                "close": base_prices,
                "volume": np.random.uniform(1000000, 2000000, 100),
            }
        )

        result = processor.compute_technicals(ohlcv)

        # Verify all technical indicators are computed
        assert "return_1m" in result.columns
        assert "return_1d" in result.columns
        assert "ema_12" in result.columns
        assert "ema_26" in result.columns
        assert "macd" in result.columns
        assert "macd_signal" in result.columns
        assert "macd_hist" in result.columns
        assert "RSI_14" in result.columns
        assert "volatility_21d" in result.columns

    @pytest.mark.integration
    def test_merge_and_clean_pipeline(self):
        """Test merging fundamentals and cleaning data together."""
        config = load_config()
        processor = DataProcessor(config)

        # Create data with some issues to clean
        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 50,
                "date": pd.date_range("2023-01-01", periods=50),
                "close": np.random.uniform(140, 160, 50),
                "return_1m": np.random.uniform(-0.05, 0.05, 50),
            }
        )

        fundamentals = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 2,
                "date": pd.to_datetime(["2023-01-01", "2023-02-01"]),
                "revenue": [100000, 105000],
                "netIncome": [25000, 26000],
            }
        )

        processor.fund_cols = ["revenue", "netIncome"]

        # Merge
        merged = processor.merge_fundamentals(ohlcv, fundamentals)
        assert "revenue" in merged.columns

        # Clean
        cleaned = processor.clean_data(merged)
        assert len(cleaned) > 0

        # Should not have inf values
        assert not np.isinf(cleaned.select_dtypes(include=[np.number])).any().any()


class TestDataFrameOperations:
    """Integration tests for DataFrame operations used throughout pipeline."""

    @pytest.mark.integration
    def test_groupby_operations_used_in_technicals(self):
        """Test groupby operations as used in technical indicators."""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 10 + ["MSFT"] * 10,
                "date": pd.date_range("2023-01-01", periods=10).tolist() * 2,
                "close": np.random.uniform(100, 150, 20),
            }
        )

        # Test groupby and transform as used in compute_technicals
        df["return_1d"] = df.groupby("symbol")["close"].transform(
            lambda x: x.pct_change(1)
        )

        assert "return_1d" in df.columns
        assert not df["return_1d"].isna().all()

    @pytest.mark.integration
    def test_rolling_operations_used_in_indicators(self):
        """Test rolling operations as used in technical indicators."""
        prices = pd.Series(np.random.uniform(100, 120, 50))

        # Test rolling mean (used for EMAs and averages)
        sma_20 = prices.rolling(20).mean()

        assert len(sma_20) == 50
        assert not pd.isna(sma_20.iloc[-1])

    @pytest.mark.integration
    def test_merge_asof_used_in_fundamentals(self):
        """Test merge_asof as used in fundamental merging."""
        left = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2023-01-01", "2023-01-15", "2023-02-01", "2023-02-15"]
                ),
                "price": [100, 105, 110, 115],
            }
        )

        right = pd.DataFrame(
            {"date": pd.to_datetime(["2023-01-01", "2023-02-01"]), "metric": [50, 55]}
        )

        # This is how fundamentals are merged
        merged = pd.merge_asof(left, right, on="date", direction="backward")

        assert len(merged) == 4
        assert "metric" in merged.columns
        # Jan 15 should get metric from Jan 1
        assert merged.iloc[1]["metric"] == 50
        # Feb 15 should get metric from Feb 1
        assert merged.iloc[3]["metric"] == 55

    @pytest.mark.integration
    def test_concat_operations_for_combining_data(self):
        """Test concat operations used to combine ticker data."""
        df1 = pd.DataFrame({"symbol": ["AAPL"] * 10, "value": range(10)})

        df2 = pd.DataFrame({"symbol": ["MSFT"] * 10, "value": range(10, 20)})

        # This is how ticker data is combined
        combined = pd.concat([df1, df2], ignore_index=True)

        assert len(combined) == 20
        assert combined["symbol"].nunique() == 2


class TestGCSIntegration:
    """Integration tests for GCS operations (if configured)."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("GCS_BUCKET_NAME") is None, reason="GCS_BUCKET_NAME not set"
    )
    def test_gcs_handler_from_config(self):
        """Test creating GCS handler from config."""
        config = load_config()

        # Should be able to create handler from config
        if "gcs" in config and "bucket_name" in config["gcs"]:
            # GCS integration is configured
            assert config["gcs"]["bucket_name"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
