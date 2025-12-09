"""
Test suite for hybrid_scoring.py
Tests hybrid score calculation and backtest metrics
"""

import pytest
import pandas as pd
import numpy as np
from hybrid_scoring import calculate_hybrid_scores, calculate_backtest_metrics


@pytest.fixture
def sample_data():
    """Create sample data for testing"""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    symbols = ["AAPL", "GOOGL", "MSFT"] * 34  # 102 rows, trim to 100

    df = pd.DataFrame(
        {
            "symbol": symbols[:100],
            "date": dates,
            "return_1m": np.random.randn(100) * 0.1,
            "ema_12": np.random.randn(100) * 10 + 100,
            "ema_26": np.random.randn(100) * 10 + 100,
            "macd": np.random.randn(100) * 2,
            "macd_signal": np.random.randn(100) * 2,
            "macd_hist": np.random.randn(100),
            "RSI_14": np.random.uniform(30, 70, 100),
            "volatility_21d": np.random.uniform(0.1, 0.3, 100),
            "roe": np.random.uniform(0.05, 0.25, 100),
            "roic": np.random.uniform(0.05, 0.20, 100),
            "peRatio": np.random.uniform(10, 30, 100),
            "freeCashFlowYield": np.random.uniform(0.02, 0.08, 100),
            "debtToEquity": np.random.uniform(0.1, 2.0, 100),
            "currentRatio": np.random.uniform(1.0, 3.0, 100),
            "dividendYield": np.random.uniform(0.01, 0.05, 100),
            "earningsYield": np.random.uniform(0.03, 0.10, 100),
            "payoutRatio": np.random.uniform(0.2, 0.6, 100),
            "cashPerShare": np.random.uniform(5, 20, 100),
            "revenuePerShare": np.random.uniform(50, 150, 100),
        }
    )

    return df


@pytest.fixture
def sample_data_with_fwd_returns(sample_data):
    """Add forward returns for backtest testing"""
    df = sample_data.copy()
    df["fwd_return_1m"] = df.groupby("symbol")["return_1m"].shift(-1)
    df["fwd_sp500_return_1m"] = np.random.randn(len(df)) * 0.08
    return df


class TestHybridScoring:
    """Test hybrid score calculations"""

    @pytest.mark.unit
    def test_calculate_hybrid_scores_basic(self, sample_data):
        """Test basic hybrid score calculation"""
        result = calculate_hybrid_scores(sample_data)

        # Check new columns exist
        assert "Hybrid_Score" in result.columns
        assert "Technical_Score" in result.columns
        assert "Fundamental_Score" in result.columns
        assert "Hybrid_CS_Pct" in result.columns
        assert "Hybrid_Rank" in result.columns
        assert "H_Score Recommendation" in result.columns

    @pytest.mark.unit
    def test_hybrid_scores_in_valid_range(self, sample_data):
        """Test scores are in valid range [0, 1]"""
        result = calculate_hybrid_scores(sample_data)

        assert result["Hybrid_Score"].min() >= 0
        assert result["Hybrid_Score"].max() <= 1
        assert result["Technical_Score"].min() >= 0
        assert result["Technical_Score"].max() <= 1
        assert result["Fundamental_Score"].min() >= 0
        assert result["Fundamental_Score"].max() <= 1

    @pytest.mark.unit
    def test_hybrid_cs_pct_percentile(self, sample_data):
        """Test Hybrid_CS_Pct is a valid percentile"""
        result = calculate_hybrid_scores(sample_data)

        assert result["Hybrid_CS_Pct"].min() >= 0
        assert result["Hybrid_CS_Pct"].max() <= 1

    @pytest.mark.unit
    def test_recommendations_are_valid(self, sample_data):
        """Test recommendations are from valid set"""
        result = calculate_hybrid_scores(sample_data)

        valid_recs = [
            "Short-Term Buy (Momentum)",
            "Long-Term Buy (Fundamental)",
            "Balanced Buy / Hold",
            "Hold / Neutral",
            "Avoid / Bearish",
        ]

        assert result["H_Score Recommendation"].isin(valid_recs).all()

    @pytest.mark.unit
    def test_hybrid_score_is_average(self, sample_data):
        """Test Hybrid_Score = 50% Tech + 50% Fund"""
        result = calculate_hybrid_scores(sample_data)

        expected = 0.5 * result["Technical_Score"] + 0.5 * result["Fundamental_Score"]

        np.testing.assert_array_almost_equal(
            result["Hybrid_Score"].values, expected.values, decimal=5
        )

    @pytest.mark.unit
    def test_handles_missing_date_column(self):
        """Test error handling for missing date column"""
        df = pd.DataFrame({"symbol": ["AAPL"] * 10, "return_1m": np.random.randn(10)})

        result = calculate_hybrid_scores(df)

        # Should return original df if date is missing
        assert len(result) == len(df)


class TestBacktestMetrics:
    """Test backtest metrics calculations"""

    @pytest.mark.unit
    def test_calculate_backtest_metrics_basic(self, sample_data_with_fwd_returns):
        """Test basic backtest metrics calculation"""
        result = calculate_backtest_metrics(sample_data_with_fwd_returns)

        # Check columns exist
        assert "n_periods" in result.columns
        assert "avg_fwd_1m_ret" in result.columns
        assert "vol_1m" in result.columns
        assert "sharpe_1m_annual" in result.columns
        assert "max_drawdown" in result.columns
        assert "hit_rate_pos" in result.columns
        assert "cagr" in result.columns

    @pytest.mark.unit
    def test_metrics_with_no_forward_returns(self, sample_data):
        """Test handling of missing forward returns"""
        result = calculate_backtest_metrics(sample_data)

        # Should add NaN columns
        assert "sharpe_1m_annual" in result.columns
        assert result["sharpe_1m_annual"].isna().all()

    @pytest.mark.unit
    def test_sharpe_ratio_calculation(self, sample_data_with_fwd_returns):
        """Test Sharpe ratio is calculated correctly"""
        result = calculate_backtest_metrics(sample_data_with_fwd_returns)

        # Sharpe should be finite or NaN
        sharpe = result["sharpe_1m_annual"].dropna()
        assert np.isfinite(sharpe).all() or sharpe.isna().all()

    @pytest.mark.unit
    def test_hit_rate_in_valid_range(self, sample_data_with_fwd_returns):
        """Test hit rates are between 0 and 1"""
        result = calculate_backtest_metrics(sample_data_with_fwd_returns)

        hit_pos = result["hit_rate_pos"].dropna()
        assert (hit_pos >= 0).all()
        assert (hit_pos <= 1).all()

    @pytest.mark.unit
    def test_max_drawdown_is_negative(self, sample_data_with_fwd_returns):
        """Test max drawdown is negative or zero"""
        result = calculate_backtest_metrics(sample_data_with_fwd_returns)

        dd = result["max_drawdown"].dropna()
        assert (dd <= 0).all()

    @pytest.mark.unit
    def test_cagr_calculation(self, sample_data_with_fwd_returns):
        """Test CAGR is calculated"""
        result = calculate_backtest_metrics(sample_data_with_fwd_returns)

        cagr = result["cagr"].dropna()
        # CAGR should be finite
        assert np.isfinite(cagr).all() or cagr.isna().all()


class TestIntegration:
    """Integration tests for hybrid scoring pipeline"""

    @pytest.mark.unit
    def test_full_pipeline(self, sample_data):
        """Test complete pipeline: scores → metrics"""
        # Calculate scores
        df_scored = calculate_hybrid_scores(sample_data)

        # Add forward returns
        df_scored["fwd_return_1m"] = df_scored.groupby("symbol")["return_1m"].shift(-1)

        # Calculate metrics
        result = calculate_backtest_metrics(df_scored)

        # Check all expected columns exist
        expected_cols = [
            "Hybrid_Score",
            "Technical_Score",
            "Fundamental_Score",
            "Hybrid_CS_Pct",
            "Hybrid_Rank",
            "H_Score Recommendation",
            "n_periods",
            "sharpe_1m_annual",
            "cagr",
            "max_drawdown",
        ]

        for col in expected_cols:
            assert col in result.columns

    @pytest.mark.unit
    def test_preserves_original_columns(self, sample_data):
        """Test original columns are preserved"""
        original_cols = set(sample_data.columns)

        result = calculate_hybrid_scores(sample_data)

        # All original columns should still exist
        assert original_cols.issubset(set(result.columns))

    @pytest.mark.unit
    def test_handles_single_symbol(self):
        """Test with single symbol"""
        df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 50,
                "date": pd.date_range("2024-01-01", periods=50, freq="D"),
                "return_1m": np.random.randn(50) * 0.1,
                "RSI_14": np.random.uniform(30, 70, 50),
                "roe": np.random.uniform(0.1, 0.3, 50),
                "peRatio": np.random.uniform(15, 25, 50),
            }
        )

        result = calculate_hybrid_scores(df)

        assert "Hybrid_Score" in result.columns
        assert len(result) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
