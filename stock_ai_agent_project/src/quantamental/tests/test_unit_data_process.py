"""
Unit tests for data_process module (DataProcessor class)
"""

import sys
import os

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_process import DataProcessor
from utils import load_config


class TestDataProcessorInit:
    """Test DataProcessor initialization."""

    @pytest.mark.unit
    def test_processor_initialization(self):
        """Test that processor initializes with config."""
        config = load_config()
        processor = DataProcessor(config)

        assert processor.config == config
        assert hasattr(processor, "data_dir")
        assert hasattr(processor, "fund_cols")

    @pytest.mark.unit
    def test_processor_fundamental_columns(self):
        """Test fundamental columns are loaded from config."""
        config = load_config()
        processor = DataProcessor(config)

        assert processor.fund_cols == config["features"]["fundamental"]
        assert isinstance(processor.fund_cols, list)
        assert len(processor.fund_cols) > 0


class TestTechnicalIndicators:
    """Test technical indicator computation."""

    @pytest.mark.unit
    def test_compute_technicals_with_sample_data(self):
        """Test computing technical indicators with sample data."""
        config = load_config()
        processor = DataProcessor(config)

        # Create sample OHLCV data
        dates = pd.date_range("2023-01-01", periods=50)
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 50,
                "date": dates,
                "close": np.random.uniform(140, 160, 50),
                "volume": np.random.uniform(1000000, 2000000, 50),
            }
        )

        # Compute technicals
        result = processor.compute_technicals(df)

        # Check that new columns were added
        assert "return_1m" in result.columns
        assert "return_1d" in result.columns
        assert "ema_12" in result.columns
        assert "ema_26" in result.columns
        assert "macd" in result.columns
        assert "RSI_14" in result.columns
        assert "volatility_21d" in result.columns

    @pytest.mark.unit
    def test_return_calculation(self):
        """Test return calculation logic."""
        # Simple price series
        prices = pd.Series([100, 105, 103, 108])

        # Calculate 1-day returns
        returns = prices.pct_change()

        assert len(returns) == 4
        assert pd.isna(returns.iloc[0])  # First value is NaN
        assert abs(returns.iloc[1] - 0.05) < 0.01  # (105-100)/100 = 5%

    @pytest.mark.unit
    def test_ema_calculation(self):
        """Test EMA calculation."""
        prices = pd.Series([100, 102, 101, 105, 103, 107, 106, 110])

        # Calculate 3-period EMA
        ema = prices.ewm(span=3, adjust=False).mean()

        assert len(ema) == len(prices)
        assert not pd.isna(ema.iloc[0])

        # EMA should follow price trends
        assert ema.iloc[-1] > ema.iloc[0]

    @pytest.mark.unit
    def test_macd_calculation(self):
        """Test MACD calculation logic."""
        prices = pd.Series(np.random.uniform(100, 120, 50))

        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26

        assert len(macd) == len(prices)
        assert isinstance(macd, pd.Series)

    @pytest.mark.unit
    def test_rsi_calculation_logic(self):
        """Test RSI calculation logic."""
        # Create price series with mixed movements (gains and losses)
        prices = pd.Series(
            [
                100,
                102,
                101,
                103,
                102,
                104,
                103,
                105,
                104,
                106,
                105,
                107,
                106,
                108,
                107,
                109,
                108,
                110,
                109,
                111,
            ]
        )

        # Calculate simple RSI
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14, min_periods=5).mean()
        avg_loss = loss.rolling(14, min_periods=5).mean()

        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        # RSI should be between 0 and 100 (excluding NaN)
        rsi_valid = rsi.dropna()
        assert len(rsi_valid) > 0
        assert (rsi_valid >= 0).all()
        assert (rsi_valid <= 100).all()


class TestDataMerging:
    """Test data merging functionality."""

    @pytest.mark.unit
    def test_merge_fundamentals_structure(self):
        """Test merge_fundamentals output structure."""
        config = load_config()
        processor = DataProcessor(config)

        # Create sample OHLCV data
        ohlcv = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 10,
                "date": pd.date_range("2023-01-01", periods=10),
                "close": np.random.uniform(140, 160, 10),
                "return_1m": np.random.uniform(-0.05, 0.05, 10),
                "ema_12": np.random.uniform(140, 160, 10),
            }
        )

        # Create sample fundamentals
        fundamentals = pd.DataFrame(
            {
                "symbol": ["AAPL", "AAPL"],
                "date": pd.to_datetime(["2023-01-01", "2023-01-05"]),
                "revenue": [100000, 105000],
            }
        )

        # Add fundamental columns to config
        processor.fund_cols = ["revenue"]

        # Merge
        result = processor.merge_fundamentals(ohlcv, fundamentals)

        assert "symbol" in result.columns
        assert "date" in result.columns
        assert len(result) > 0

    @pytest.mark.unit
    def test_asof_merge_logic(self):
        """Test asof merge behavior."""
        left = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01", "2023-01-05", "2023-01-10"]),
                "price": [100, 105, 110],
            }
        )

        right = pd.DataFrame(
            {"date": pd.to_datetime(["2023-01-01", "2023-01-08"]), "metric": [1.5, 1.8]}
        )

        merged = pd.merge_asof(left, right, on="date", direction="backward")

        assert len(merged) == 3
        assert "metric" in merged.columns
        # Jan 5 should get metric from Jan 1
        assert merged.iloc[1]["metric"] == 1.5


class TestDataCleaning:
    """Test data cleaning functionality."""

    @pytest.mark.unit
    def test_clean_data_removes_high_nan_columns(self):
        """Test that columns with >80% NaN are dropped."""
        config = load_config()
        processor = DataProcessor(config)
        processor.fund_cols = ["revenue"]

        # Create data with high-NaN column
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 10,
                "date": pd.date_range("2023-01-01", periods=10),
                "close": np.random.uniform(100, 120, 10),
                "revenue": [100] * 10,
                "bad_column": [np.nan] * 10,  # 100% NaN
            }
        )

        result = processor.clean_data(df)

        # Bad column should be dropped
        assert "bad_column" not in result.columns
        assert "close" in result.columns

    @pytest.mark.unit
    def test_clean_data_handles_inf(self):
        """Test that inf values are replaced."""
        config = load_config()
        config["processing"]["remove_inf"] = True
        processor = DataProcessor(config)
        processor.fund_cols = ["revenue"]

        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 5,
                "date": pd.date_range("2023-01-01", periods=5),
                "close": [100, np.inf, 105, -np.inf, 110],
                "revenue": [100, 100, 100, 100, 100],
            }
        )

        result = processor.clean_data(df)

        # Should not have any inf values
        assert not np.isinf(result["close"]).any()

    @pytest.mark.unit
    def test_forward_fill_logic(self):
        """Test forward fill behavior."""
        df = pd.DataFrame(
            {"symbol": ["AAPL"] * 5, "value": [100, np.nan, np.nan, 105, np.nan]}
        )

        # Group by symbol and forward fill
        df["value_filled"] = df.groupby("symbol")["value"].ffill()

        assert df["value_filled"].iloc[1] == 100  # Filled from previous
        assert df["value_filled"].iloc[2] == 100  # Still filled


class TestDataValidation:
    """Test data validation functionality."""

    @pytest.mark.unit
    def test_coverage_calculation(self):
        """Test coverage calculation per symbol."""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 10 + ["MSFT"] * 5 + ["GOOGL"] * 8,
                "date": pd.date_range("2023-01-01", periods=23),
            }
        )

        coverage = df.groupby("symbol")["date"].count()

        assert coverage["AAPL"] == 10
        assert coverage["MSFT"] == 5
        assert coverage["GOOGL"] == 8

        median = coverage.median()
        assert median == 8

    @pytest.mark.unit
    def test_filtering_low_coverage_symbols(self):
        """Test filtering symbols with low coverage."""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 100 + ["MSFT"] * 10 + ["GOOGL"] * 95,
                "value": range(205),
            }
        )

        coverage = df.groupby("symbol").size()
        threshold = coverage.median() * 0.5  # 50% of median

        low_cov = coverage[coverage < threshold]
        filtered = df[~df["symbol"].isin(low_cov.index)]

        # MSFT should be filtered (only 10 rows vs median ~95)
        assert "MSFT" not in filtered["symbol"].values


class TestMonthlySnapshot:
    """Test monthly snapshot creation."""

    @pytest.mark.unit
    def test_create_monthly_snapshot(self):
        """Test creating monthly snapshots."""
        config = load_config()
        config["processing"]["monthly_snapshot"] = True
        processor = DataProcessor(config)

        # Create daily data for 3 months
        dates = pd.date_range("2023-01-01", "2023-03-31", freq="D")
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * len(dates),
                "date": dates,
                "close": np.random.uniform(140, 160, len(dates)),
            }
        )

        result = processor.create_monthly_snapshot(df)

        # Should have ~3 rows (one per month end)
        assert len(result) <= 4
        assert len(result) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
