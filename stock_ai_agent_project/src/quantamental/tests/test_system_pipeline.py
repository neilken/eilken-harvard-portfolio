"""
SYSTEM TESTS - End-to-End Pipeline
Tests complete pipeline execution from start to finish
"""

import sys
import os

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_collect import FMPDataCollector
from data_process import DataProcessor
from utils import load_config


class TestFullPipelineExecution:
    """System test for complete pipeline execution."""

    @pytest.mark.system
    @pytest.mark.slow
    def test_end_to_end_pipeline_with_mock_data(self):
        """
        SYSTEM TEST: Complete end-to-end pipeline execution

        Simulates full quantamental pipeline:
        1. Load configuration
        2. Initialize collector and processor
        3. Create mock data (simulates data collection)
        4. Process data with technical indicators
        5. Merge with fundamentals
        6. Clean and validate data
        7. Verify outputs

        This test validates that all components work together
        in a complete production-like workflow.
        """
        # ===============================================
        # STEP 1: Configuration Loading
        # ===============================================
        config = load_config()

        assert config is not None
        assert "data" in config
        assert "features" in config

        # ===============================================
        # STEP 2: Initialize Pipeline Components
        # ===============================================
        collector = FMPDataCollector(config)
        processor = DataProcessor(config)

        assert collector.data_dir == processor.data_dir

        # ===============================================
        # STEP 3: Create Mock Data (Simulates Collection)
        # ===============================================
        # Simulate 6 months of daily data for 3 stocks
        n_days = 180
        symbols = ["AAPL", "MSFT", "GOOGL"]

        # Create OHLCV data
        all_ohlcv = []
        for symbol in symbols:
            base_price = np.random.uniform(100, 200)
            prices = base_price + np.cumsum(np.random.randn(n_days) * 2)

            ohlcv = pd.DataFrame(
                {
                    "symbol": [symbol] * n_days,
                    "date": pd.date_range("2023-01-01", periods=n_days),
                    "open": prices + np.random.randn(n_days),
                    "high": prices + np.abs(np.random.randn(n_days)) + 1,
                    "low": prices - np.abs(np.random.randn(n_days)) - 1,
                    "close": prices,
                    "adj_close": prices * 0.98,  # Simulate dividend adjustment
                    "volume": np.random.uniform(1e6, 5e6, n_days),
                }
            )
            all_ohlcv.append(ohlcv)

        ohlcv_combined = pd.concat(all_ohlcv, ignore_index=True)

        assert len(ohlcv_combined) == n_days * len(symbols)
        assert ohlcv_combined["symbol"].nunique() == len(symbols)

        # Create fundamentals data (quarterly)
        all_fundamentals = []
        for symbol in symbols:
            fundamentals = pd.DataFrame(
                {
                    "symbol": [symbol] * 6,
                    "date": pd.to_datetime(
                        [
                            "2023-01-01",
                            "2023-02-01",
                            "2023-03-01",
                            "2023-04-01",
                            "2023-05-01",
                            "2023-06-01",
                        ]
                    ),
                    "revenue": np.random.uniform(1e8, 2e8, 6),
                    "netIncome": np.random.uniform(1e7, 5e7, 6),
                    "totalAssets": np.random.uniform(5e8, 1e9, 6),
                }
            )
            all_fundamentals.append(fundamentals)

        fundamentals_combined = pd.concat(all_fundamentals, ignore_index=True)

        # Create S&P 500 benchmark
        sp500_index = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-01", periods=n_days),
                "close": 4000 + np.cumsum(np.random.randn(n_days) * 10),
                "return_1d": None,
            }
        )
        sp500_index["return_1d"] = sp500_index["close"].pct_change()

        # ===============================================
        # STEP 4: Compute Technical Indicators
        # ===============================================
        ohlcv_with_technicals = processor.compute_technicals(ohlcv_combined)

        # Verify technical indicators were added
        assert "return_1m" in ohlcv_with_technicals.columns
        assert "return_1d" in ohlcv_with_technicals.columns
        assert "ema_12" in ohlcv_with_technicals.columns
        assert "ema_26" in ohlcv_with_technicals.columns
        assert "macd" in ohlcv_with_technicals.columns
        assert "RSI_14" in ohlcv_with_technicals.columns
        assert "volatility_21d" in ohlcv_with_technicals.columns

        # ===============================================
        # STEP 5: Merge with Fundamentals
        # ===============================================
        processor.fund_cols = ["revenue", "netIncome", "totalAssets"]

        merged_data = processor.merge_fundamentals(
            ohlcv_with_technicals, fundamentals_combined
        )

        # Verify merge was successful
        assert len(merged_data) > 0
        assert "revenue" in merged_data.columns
        assert "netIncome" in merged_data.columns
        assert "totalAssets" in merged_data.columns
        assert merged_data["symbol"].nunique() == len(symbols)

        # ===============================================
        # STEP 6: Clean and Validate Data
        # ===============================================
        cleaned_data = processor.clean_data(merged_data)

        # Verify cleaning
        assert len(cleaned_data) > 0
        assert len(cleaned_data) <= len(merged_data)  # Some rows may be dropped

        # Should not have inf values
        numeric_cols = cleaned_data.select_dtypes(include=[np.number]).columns
        assert not np.isinf(cleaned_data[numeric_cols]).any().any()

        # ===============================================
        # STEP 7: Verify Final Output Structure
        # ===============================================
        # Final data should have all required columns
        required_columns = [
            "symbol",
            "date",
            "close",
            "return_1m",
            "return_1d",
            "ema_12",
            "macd",
            "RSI_14",
            "revenue",
            "netIncome",
        ]

        for col in required_columns:
            assert col in cleaned_data.columns, f"Missing column: {col}"

        # Should have data for all symbols
        assert cleaned_data["symbol"].nunique() >= 2  # At least 2 symbols remain

        # Date range should be reasonable
        date_range = (cleaned_data["date"].max() - cleaned_data["date"].min()).days
        assert date_range > 30  # At least 1 month of data

        # ===============================================
        # STEP 8: Verify Data Quality Metrics
        # ===============================================
        # Technical indicators should be within reasonable bounds
        # RSI should be between 0 and 100 for valid values
        rsi_valid = cleaned_data["RSI_14"].dropna()
        if len(rsi_valid) > 0:
            assert (rsi_valid >= 0).all() and (rsi_valid <= 100).all()

        # Returns should be reasonable (not extreme)
        returns = cleaned_data["return_1d"].dropna()
        if len(returns) > 0:
            assert returns.abs().max() < 0.5  # No more than 50% daily return

        # Volume should be positive
        assert (cleaned_data["volume"] > 0).all()

        print("\n SYSTEM TEST PASSED - Complete Pipeline Execution")
        print(f"   Processed {len(symbols)} stocks")
        print(f"   {len(cleaned_data):,} final data points")
        print(f"   {len(cleaned_data.columns)} features")
        print(
            f"   Date range: {cleaned_data['date'].min()} to {cleaned_data['date'].max()}"
        )


class TestPipelinePerformance:
    """System tests for pipeline performance."""

    @pytest.mark.system
    def test_pipeline_handles_reasonable_data_volume(self):
        """Test that pipeline can handle reasonable data volume."""
        config = load_config()
        processor = DataProcessor(config)

        # Create moderate data volume (30 days, 5 stocks)
        n_days = 30
        n_stocks = 5

        df = pd.DataFrame(
            {
                "symbol": (
                    ["AAPL"] * n_days
                    + ["MSFT"] * n_days
                    + ["GOOGL"] * n_days
                    + ["AMZN"] * n_days
                    + ["META"] * n_days
                ),
                "date": pd.date_range("2023-01-01", periods=n_days).tolist() * n_stocks,
                "close": np.random.uniform(100, 200, n_days * n_stocks),
                "volume": np.random.uniform(1e6, 5e6, n_days * n_stocks),
            }
        )

        # Should process without errors
        result = processor.compute_technicals(df)

        assert len(result) == n_days * n_stocks
        assert result["symbol"].nunique() == n_stocks

    @pytest.mark.system
    def test_pipeline_handles_missing_data_gracefully(self):
        """Test that pipeline handles missing data appropriately."""
        config = load_config()
        processor = DataProcessor(config)

        # Create data with some missing values
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 50,
                "date": pd.date_range("2023-01-01", periods=50),
                "close": [100 if i % 5 != 0 else np.nan for i in range(50)],
                "volume": np.random.uniform(1e6, 2e6, 50),
            }
        )

        # Should handle NaN values
        result = processor.compute_technicals(df)

        # Should still produce output
        assert len(result) > 0
        assert "return_1d" in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
