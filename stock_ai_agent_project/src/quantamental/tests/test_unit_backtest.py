"""
Test suite for backtest.py - FIXED VERSION
Tests backtest output file generation
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config(temp_dir):
    """Create sample configuration"""
    return {
        "data": {"data_dir": temp_dir},
        "gcs": {
            "bucket_name": "test-bucket",
            "output_folder": "model_output",  # Added this!
        },
        "wandb": {"project": "test-project"},
    }


@pytest.fixture
def sample_prediction_data():
    """Create sample prediction data with all required columns"""
    np.random.seed(42)

    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOGL", "MSFT"] * 10,
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "pred_prob": np.random.uniform(0.3, 0.7, 30),
            "close": np.random.uniform(150, 200, 30),
            "return_1m": np.random.randn(30) * 0.1,
            "ema_12": np.random.uniform(90, 110, 30),
            "ema_26": np.random.uniform(90, 110, 30),
            "macd": np.random.randn(30),
            "macd_signal": np.random.randn(30),
            "macd_hist": np.random.randn(30),
            "RSI_14": np.random.uniform(30, 70, 30),
            "volatility_21d": np.random.uniform(0.1, 0.3, 30),
            "roe": np.random.uniform(0.1, 0.3, 30),
            "roic": np.random.uniform(0.05, 0.20, 30),
            "peRatio": np.random.uniform(15, 25, 30),
            "freeCashFlowYield": np.random.uniform(0.02, 0.08, 30),
            "debtToEquity": np.random.uniform(0.1, 2.0, 30),
            "currentRatio": np.random.uniform(1.0, 3.0, 30),
            "dividendYield": np.random.uniform(0.01, 0.05, 30),
            "earningsYield": np.random.uniform(0.03, 0.10, 30),
            "payoutRatio": np.random.uniform(0.2, 0.6, 30),
            "cashPerShare": np.random.uniform(5, 20, 30),
            "revenuePerShare": np.random.uniform(50, 150, 30),
            "sector": ["Technology"] * 30,
            "industry": ["Software"] * 30,
            # Add hybrid scoring columns
            "Hybrid_Score": np.random.uniform(0, 1, 30),
            "Technical_Score": np.random.uniform(0, 1, 30),
            "Fundamental_Score": np.random.uniform(0, 1, 30),
            "Hybrid_Rank": np.arange(1, 31),
            "Hybrid_CS_Pct": np.random.uniform(0, 1, 30),
            "H_Score Recommendation": ["Hold / Neutral"] * 30,
            # Add backtest columns
            "n_periods": [10] * 30,
            "avg_fwd_1m_ret": [0.05] * 30,
            "vol_1m": [0.15] * 30,
            "sharpe_1m_annual": [1.2] * 30,
            "max_drawdown": [-0.10] * 30,
            "hit_rate_pos": [0.6] * 30,
            "hit_rate_vs_sp500": [0.55] * 30,
            "cagr": [0.12] * 30,
        }
    )

    return df


class TestBacktesterInit:
    """Test QuantamentalBacktester initialization"""

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    def test_init_with_config(self, mock_gcs, sample_config):
        """Test backtester initialization"""
        from backtest import QuantamentalBacktester

        backtester = QuantamentalBacktester(sample_config)

        assert backtester.data_dir == sample_config["data"]["data_dir"]
        assert backtester.output_folder == "model_output"


class TestCreateAgentOutputFiles:
    """Test create_agent_output_files method"""

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("hybrid_scoring.calculate_hybrid_scores")  # Fixed: patch from hybrid_scoring
    @patch(
        "hybrid_scoring.calculate_backtest_metrics"
    )  # Fixed: patch from hybrid_scoring
    def test_creates_three_files(
        self,
        mock_metrics,
        mock_scores,
        mock_gcs,
        sample_config,
        sample_prediction_data,
        temp_dir,
    ):
        """Test creates 3 output files"""
        from backtest import QuantamentalBacktester

        # Mock returns data with all columns
        mock_scores.return_value = sample_prediction_data.copy()
        mock_metrics.return_value = sample_prediction_data.copy()

        # Create company profiles file
        profiles = pd.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL", "MSFT"],
                "companyName": ["Apple", "Google", "Microsoft"],
                "sector": ["Technology"] * 3,
                "industry": ["Software"] * 3,
            }
        )
        profiles.to_parquet(f"{temp_dir}/company_profiles.parquet")

        backtester = QuantamentalBacktester(sample_config)

        result = backtester.create_agent_output_files(sample_prediction_data)

        # Should return 3 file paths
        assert len(result) == 3
        assert "combined" in result
        assert "profiles" in result
        assert "equity" in result

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("hybrid_scoring.calculate_hybrid_scores")
    @patch("hybrid_scoring.calculate_backtest_metrics")
    def test_combined_file_exists(
        self,
        mock_metrics,
        mock_scores,
        mock_gcs,
        sample_config,
        sample_prediction_data,
        temp_dir,
    ):
        """Test combined file is created"""
        from backtest import QuantamentalBacktester

        mock_scores.return_value = sample_prediction_data.copy()
        mock_metrics.return_value = sample_prediction_data.copy()

        backtester = QuantamentalBacktester(sample_config)

        result = backtester.create_agent_output_files(sample_prediction_data)

        # Check file exists
        assert Path(result["combined"]).exists()

        # Read and verify
        df_output = pd.read_csv(result["combined"])
        assert len(df_output) > 0
        assert "symbol" in df_output.columns

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("hybrid_scoring.calculate_hybrid_scores")
    @patch("hybrid_scoring.calculate_backtest_metrics")
    def test_combined_file_has_required_columns(
        self,
        mock_metrics,
        mock_scores,
        mock_gcs,
        sample_config,
        sample_prediction_data,
        temp_dir,
    ):
        """Test combined file has key required columns"""
        from backtest import QuantamentalBacktester

        mock_scores.return_value = sample_prediction_data.copy()
        mock_metrics.return_value = sample_prediction_data.copy()

        backtester = QuantamentalBacktester(sample_config)

        result = backtester.create_agent_output_files(sample_prediction_data)

        df_output = pd.read_csv(result["combined"])

        # Check key columns exist
        required = [
            "symbol",
            "pred_prob_next_month",
            "signal",
            "Hybrid_Score",
            "sector",
            "industry",
        ]

        for col in required:
            assert col in df_output.columns, f"Missing column: {col}"

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("hybrid_scoring.calculate_hybrid_scores")
    @patch("hybrid_scoring.calculate_backtest_metrics")
    def test_creates_company_profiles(
        self,
        mock_metrics,
        mock_scores,
        mock_gcs,
        sample_config,
        sample_prediction_data,
        temp_dir,
    ):
        """Test creates company profiles file"""
        from backtest import QuantamentalBacktester

        mock_scores.return_value = sample_prediction_data.copy()
        mock_metrics.return_value = sample_prediction_data.copy()

        backtester = QuantamentalBacktester(sample_config)

        result = backtester.create_agent_output_files(sample_prediction_data)

        # Check profiles file exists
        assert Path(result["profiles"]).exists()

        # Read and check
        df_profiles = pd.read_csv(result["profiles"])
        assert "symbol" in df_profiles.columns
        assert len(df_profiles) > 0

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("hybrid_scoring.calculate_hybrid_scores")
    @patch("hybrid_scoring.calculate_backtest_metrics")
    def test_creates_equity_curves(
        self,
        mock_metrics,
        mock_scores,
        mock_gcs,
        sample_config,
        sample_prediction_data,
        temp_dir,
    ):
        """Test creates equity curves file"""
        from backtest import QuantamentalBacktester

        mock_scores.return_value = sample_prediction_data.copy()
        mock_metrics.return_value = sample_prediction_data.copy()

        backtester = QuantamentalBacktester(sample_config)

        result = backtester.create_agent_output_files(sample_prediction_data)

        # Check equity file exists
        assert Path(result["equity"]).exists()

        # Read and check
        df_equity = pd.read_csv(result["equity"])
        assert "symbol" in df_equity.columns
        assert "date" in df_equity.columns
        assert "equity_value" in df_equity.columns


class TestRunBacktest:
    """Test run_backtest method"""

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    @patch("backtest.QuantamentalPredictor")
    @patch("backtest.wandb")
    def test_run_backtest_returns_results(
        self,
        mock_wandb,
        mock_predictor,
        mock_gcs,
        sample_config,
        sample_prediction_data,
    ):
        """Test run_backtest returns results dict"""
        from backtest import QuantamentalBacktester

        # Mock predictor
        mock_pred_instance = Mock()
        mock_pred_instance.predict_next_month.return_value = (
            sample_prediction_data,
            None,
        )
        mock_predictor.return_value = mock_pred_instance

        # Mock wandb
        mock_run = MagicMock()
        mock_wandb.init.return_value = mock_run

        backtester = QuantamentalBacktester(sample_config)

        # Mock create_agent_output_files
        backtester.create_agent_output_files = Mock(
            return_value={
                "combined": "test.csv",
                "profiles": "profiles.csv",
                "equity": "equity.csv",
            }
        )

        # Mock GCS upload
        backtester.gcs.upload_file = Mock(return_value=True)

        result = backtester.run_backtest(
            sample_prediction_data, use_wandb_logging=False
        )

        # Check result structure
        assert "local_files" in result
        assert "gcs_paths" in result
        assert "num_stocks" in result

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    def test_backtester_has_required_attributes(self, mock_gcs, sample_config):
        """Test backtester has all required attributes"""
        from backtest import QuantamentalBacktester

        backtester = QuantamentalBacktester(sample_config)

        assert hasattr(backtester, "data_dir")
        assert hasattr(backtester, "config")
        assert hasattr(backtester, "gcs")
        assert hasattr(backtester, "output_folder")

    @pytest.mark.unit
    @patch("backtest.GCSHandler")
    def test_create_ranked_output(
        self, mock_gcs, sample_config, sample_prediction_data
    ):
        """Test create_ranked_output creates ranked DataFrame"""
        from backtest import QuantamentalBacktester

        backtester = QuantamentalBacktester(sample_config)

        # Add required columns if missing
        if "pred_prob" not in sample_prediction_data.columns:
            sample_prediction_data["pred_prob"] = np.random.uniform(
                0, 1, len(sample_prediction_data)
            )
        if "pred_rank" not in sample_prediction_data.columns:
            sample_prediction_data["pred_rank"] = range(
                1, len(sample_prediction_data) + 1
            )

        result = backtester.create_ranked_output(sample_prediction_data, top_n=10)

        assert isinstance(result, pd.DataFrame)
        assert "symbol" in result.columns
        assert "pred_prob" in result.columns or "pred_prob_next_month" in result.columns
        assert (
            len(result) <= 10
            if len(sample_prediction_data) > 10
            else len(result) == len(sample_prediction_data)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
