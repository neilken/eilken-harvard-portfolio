"""
Backtest Module
- Rank stocks by prediction probability
- Generate final output reports
- Upload results to GCS
- Log results to W&B
"""

import pandas as pd
import numpy as np
from datetime import datetime
import wandb
import logging

from utils import load_config, GCSHandler, get_timestamp_suffix
from model_predict import QuantamentalPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuantamentalBacktester:
    """Generate backtest reports and upload to GCS"""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = config["data"]["data_dir"]

        # Initialize GCS handler
        self.gcs = GCSHandler(
            bucket_name=config["gcs"]["bucket_name"],
            credentials_path=config["gcs"].get("credentials_path"),
        )

        self.output_folder = config["gcs"]["output_folder"]

        logger.info(" Quantamental Backtester initialized")
        logger.info(f"   GCS Bucket: {config['gcs']['bucket_name']}")
        logger.info(f"   Output Folder: {self.output_folder}")

    def create_ranked_output(
        self, df_predict: pd.DataFrame, top_n: int = None
    ) -> pd.DataFrame:
        """
        Create ranked output report

        Args:
            df_predict: DataFrame with predictions
            top_n: Optional - only return top N stocks

        Returns:
            Ranked DataFrame
        """
        logger.info(" Creating ranked output report...")

        # Select columns
        output_cols = [
            "symbol",
            "date",
            "close",
            "pred_prob",
            "pred_rank",
            "return_1m",
            "volatility_21d",
            "RSI_14",
            "peRatio",
            "roe",
            "debtToEquity",
        ]

        # Keep only available columns
        available_cols = [col for col in output_cols if col in df_predict.columns]
        df_ranked = df_predict[available_cols].copy()

        # Sort by rank
        df_ranked = df_ranked.sort_values("pred_rank")

        # Limit to top N if specified
        if top_n:
            df_ranked = df_ranked.head(top_n)

        # Add metadata
        df_ranked["generated_at"] = datetime.now().isoformat()
        df_ranked["model_version"] = "quantamental-v1"

        logger.info(f" Ranked output created: {len(df_ranked)} stocks")

        return df_ranked

    def run_backtest(self, df: pd.DataFrame, use_wandb_logging: bool = True) -> dict:
        """
        Run complete backtest pipeline

        Args:
            df: DataFrame with processed data
            use_wandb_logging: Whether to log to W&B

        Returns:
            Dictionary with results and file paths
        """
        logger.info("=" * 60)
        logger.info(" RUNNING BACKTEST PIPELINE")
        logger.info("=" * 60)

        # Step 1: Generate predictions (if not already present)
        if "pred_prob" not in df.columns:
            logger.info(" Generating predictions...")
            predictor = QuantamentalPredictor(self.config)
            df_predict, _ = predictor.predict_next_month(df)
        else:
            df_predict = df.copy()

        logger.info(f"   Prediction data: {len(df_predict):,} rows")

        # Step 2: Create agent output files (with hybrid scoring)
        output_files = self.create_agent_output_files(df_predict)

        # Step 3: Upload to GCS
        logger.info("\n Uploading to GCS...")
        gcs_paths = {}

        for file_type, local_path in output_files.items():
            try:
                gcs_path = (
                    f"{self.output_folder}/{file_type}_{get_timestamp_suffix()}.csv"
                )
                success = self.gcs.upload_file(local_path, gcs_path)

                if success:
                    gcs_paths[file_type] = gcs_path
                    logger.info(
                        f"    {file_type}: gs://{self.gcs.bucket_name}/{gcs_path}"
                    )
                else:
                    logger.warning(f"     {file_type}: Upload failed")

            except Exception as e:
                logger.error(f"    {file_type}: {e}")

        # Step 4: Log to W&B (optional)
        if use_wandb_logging:
            try:
                logger.info("\n Logging to W&B...")

                # Read the combined output
                df_output = pd.read_csv(output_files["combined"])

                # Initialize W&B run
                run = wandb.init(
                    project=self.config["wandb"]["project"],
                    job_type="backtest",
                    name=f"backtest_{get_timestamp_suffix()}",
                    config={
                        "output_rows": len(df_output),
                        "output_columns": len(df_output.columns),
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Log summary statistics
                if "Hybrid_Score" in df_output.columns:
                    run.summary["avg_hybrid_score"] = df_output["Hybrid_Score"].mean()

                if "sharpe_1m_annual" in df_output.columns:
                    run.summary["avg_sharpe"] = df_output["sharpe_1m_annual"].mean()

                if "cagr" in df_output.columns:
                    run.summary["avg_cagr"] = df_output["cagr"].mean()

                # Create artifact
                artifact = wandb.Artifact(
                    name="backtest_output",
                    type="model_output",
                    description="Backtest results with hybrid scoring",
                )

                artifact.add_file(output_files["combined"])
                run.log_artifact(artifact)

                run.finish()
                logger.info("    W&B logging complete")

            except Exception as e:
                logger.warning(f"     W&B logging failed: {e}")

        # Step 5: Return results
        results = {
            "local_files": output_files,
            "gcs_paths": gcs_paths,
            "num_stocks": (
                len(df_predict["symbol"].unique())
                if "symbol" in df_predict.columns
                else 0
            ),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("\n" + "=" * 60)
        logger.info(" BACKTEST COMPLETE!")
        logger.info(f"   Stocks analyzed: {results['num_stocks']}")
        logger.info(f"   Local files: {len(output_files)}")
        logger.info(f"   GCS uploads: {len(gcs_paths)}")
        logger.info("=" * 60)

        return results

    def create_agent_output_files(self, df_predict: pd.DataFrame) -> dict:
        """
        Create the 3 specific files needed by agents with hybrid scoring and backtest metrics

        Pipeline:
        1. Calculate Hybrid Scores (from hybrid_scoring.py)
        2. Calculate Backtest Metrics (from hybrid_scoring.py)
        3. Select exactly 40 columns
        4. Save output files

        Args:
            df_predict: DataFrame with predictions (91 columns from model_predict.py)

        Returns:
            Dictionary with paths to created files
        """
        logger.info(" Creating agent output files with hybrid scoring...")

        output_files = {}

        logger.info(
            f"    Input: {len(df_predict):,} rows × {len(df_predict.columns)} columns"
        )

        # ============================================
        # Import scoring functions
        # ============================================
        try:
            from hybrid_scoring import (
                calculate_hybrid_scores,
                calculate_backtest_metrics,
            )
        except ImportError:
            logger.error("    Failed to import hybrid_scoring module!")
            logger.error("   Make sure hybrid_scoring.py is in the same directory")
            raise

        # ============================================
        # STEP 1: Calculate Hybrid Scores
        # ============================================
        logger.info("    Calculating Hybrid Quantamental Scores...")
        df_combined = calculate_hybrid_scores(df_predict)
        logger.info("    Hybrid scores calculated")

        # ============================================
        # STEP 1.5: Calculate fwd_return_1m if missing
        # ============================================
        if "fwd_return_1m" not in df_combined.columns:
            logger.info("   🔧 Calculating fwd_return_1m for backtest metrics...")

            # Sort by symbol and date
            df_combined = df_combined.sort_values(["symbol", "date"])

            # Calculate forward return (shift -1 within each symbol group)
            df_combined["fwd_return_1m"] = df_combined.groupby("symbol")[
                "return_1m"
            ].shift(-1)

            # Calculate forward S&P500 return if sp500_return_1m exists
            if "sp500_return_1m" in df_combined.columns:
                df_combined["fwd_sp500_return_1m"] = df_combined.groupby("symbol")[
                    "sp500_return_1m"
                ].shift(-1)
                logger.info("    Added 'fwd_return_1m' and 'fwd_sp500_return_1m'")
            else:
                logger.info("    Added 'fwd_return_1m' (no S&P500 benchmark)")

            # Log stats
            valid_fwd = df_combined["fwd_return_1m"].notna().sum()
            logger.info(f"    {valid_fwd} rows have forward returns for backtest")

        # ============================================
        # STEP 2: Calculate Backtest Metrics
        # ============================================
        logger.info("    Calculating backtest metrics...")
        df_combined = calculate_backtest_metrics(df_combined)
        logger.info("    Backtest metrics calculated")

        # ============================================
        # STEP 3: Handle column name mappings
        # ============================================
        # Rename pred_prob to pred_prob_next_month if needed
        if (
            "pred_prob" in df_combined.columns
            and "pred_prob_next_month" not in df_combined.columns
        ):
            df_combined["pred_prob_next_month"] = df_combined["pred_prob"]
            logger.info("    Renamed 'pred_prob' → 'pred_prob_next_month'")

        # Generate signal if not present
        if (
            "signal" not in df_combined.columns
            and "pred_prob_next_month" in df_combined.columns
        ):
            prod_threshold = 0.50
            df_combined["signal"] = np.where(
                df_combined["pred_prob_next_month"] > prod_threshold,
                "LONG-Outperform",
                np.where(
                    df_combined["pred_prob_next_month"] < (prod_threshold - 0.05),
                    "SHORT-Underperform",
                    "NEUTRAL",
                ),
            )
            logger.info("    Generated 'signal' column")

        # equity_chart_path placeholder
        if "equity_chart_path" not in df_combined.columns:
            df_combined["equity_chart_path"] = ""
            logger.info("    Added empty 'equity_chart_path'")

        # ============================================
        # STEP 3.5: Add sector/industry if missing
        # ============================================
        if "sector" not in df_combined.columns or "industry" not in df_combined.columns:
            logger.info("    Adding sector/industry from company profiles...")

            try:
                # Try to load company profiles with sector/industry
                profiles = pd.read_parquet(f"{self.data_dir}/company_profiles.parquet")

                if "sector" not in df_combined.columns and "sector" in profiles.columns:
                    sector_map = profiles.set_index("symbol")["sector"]
                    df_combined["sector"] = (
                        df_combined["symbol"].map(sector_map).fillna("Unknown")
                    )
                    logger.info("    Added 'sector' from company profiles")

                if (
                    "industry" not in df_combined.columns
                    and "industry" in profiles.columns
                ):
                    industry_map = profiles.set_index("symbol")["industry"]
                    df_combined["industry"] = (
                        df_combined["symbol"].map(industry_map).fillna("Unknown")
                    )
                    logger.info("    Added 'industry' from company profiles")

            except Exception as e:
                logger.warning(f"     Could not load company profiles: {e}")

                # Fallback: set as Unknown
                if "sector" not in df_combined.columns:
                    df_combined["sector"] = "Unknown"
                    logger.info("    Added 'sector' as 'Unknown'")

                if "industry" not in df_combined.columns:
                    df_combined["industry"] = "Unknown"
                    logger.info("    Added 'industry' as 'Unknown'")

        # ============================================
        # STEP 4: Define the EXACT 40 columns
        # ============================================
        required_columns = [
            # Core identifiers (3)
            "symbol",
            "pred_prob_next_month",
            "signal",
            # Hybrid scoring columns (6)
            "Hybrid_Score",
            "Fundamental_Score",
            "Technical_Score",
            "Hybrid_Rank",
            "Hybrid_CS_Pct",
            "H_Score Recommendation",
            # Date (1)
            "date",
            # Selected fundamental metrics (11)
            "roe",
            "roic",
            "peRatio",
            "freeCashFlowYield",
            "debtToEquity",
            "currentRatio",
            "dividendYield",
            "earningsYield",
            "payoutRatio",
            "cashPerShare",
            "revenuePerShare",
            # Technical indicators (8)
            "return_1m",
            "ema_12",
            "ema_26",
            "macd",
            "macd_signal",
            "macd_hist",
            "RSI_14",
            "volatility_21d",
            # Backtest metrics (9)
            "n_periods",
            "avg_fwd_1m_ret",
            "vol_1m",
            "sharpe_1m_annual",
            "max_drawdown",
            "hit_rate_pos",
            "hit_rate_vs_sp500",
            "cagr",
            "equity_chart_path",
            # Sector/Industry (2)
            "sector",
            "industry",
        ]
        # Total: 3 + 6 + 1 + 11 + 8 + 9 + 2 = 40 columns

        # ============================================
        # STEP 5: Select ONLY the 40 required columns
        # ============================================
        final_columns = []
        missing_columns = []

        for col in required_columns:
            if col in df_combined.columns:
                final_columns.append(col)
            else:
                missing_columns.append(col)
                logger.warning(f"     Required column missing: {col}")

        # Create output with only selected columns
        df_output = df_combined[final_columns].copy()

        logger.info(
            f"    Output: {len(df_output):,} rows × {len(df_output.columns)} columns"
        )
        logger.info(
            f"    Selected {len(final_columns)}/{len(required_columns)} required columns"
        )

        if missing_columns:
            logger.error(
                f"    Missing {len(missing_columns)} columns: {missing_columns}"
            )

        # ============================================
        # STEP 6: Save combined file
        # ============================================
        combined_path = f"{self.data_dir}/combined_quantamental_hybrid_with_factors_and_backtest.csv"
        df_output.to_csv(combined_path, index=False)
        output_files["combined"] = combined_path

        logger.info(f"    Created: {combined_path}")
        logger.info(f"      Rows: {len(df_output):,}")
        logger.info(
            f"      Columns: {len(df_output.columns)} {' CORRECT!' if len(df_output.columns) == 40 else '⚠️ WRONG!'}"
        )

        # Verify column count
        if len(df_output.columns) == 40:
            logger.info("    SUCCESS: Output has exactly 40 columns as required!")
        else:
            logger.warning(
                f"     WARNING: Output has {len(df_output.columns)} columns, expected 40!"
            )

        # Show first few columns
        logger.info(f"    First 10 columns: {list(df_output.columns[:10])}")

        # ============================================
        # STEP 7: Company profiles
        # ============================================
        profiles_path = f"{self.data_dir}/company_profiles.csv"
        try:
            # Try to load cached profiles
            profiles = pd.read_parquet(f"{self.data_dir}/company_profiles.parquet")
            profiles.to_csv(profiles_path, index=False)
            logger.info(
                f"    Loaded cached company profiles ({len(profiles)} companies)"
            )
        except Exception:
            # Create minimal profiles
            profiles = df_predict[["symbol"]].drop_duplicates().copy()
            profiles["companyName"] = profiles["symbol"]

            if "sector" in df_output.columns:
                sector_map = df_output.groupby("symbol")["sector"].first()
                profiles["sector"] = (
                    profiles["symbol"].map(sector_map).fillna("Unknown")
                )
            else:
                profiles["sector"] = "Unknown"

            if "industry" in df_output.columns:
                industry_map = df_output.groupby("symbol")["industry"].first()
                profiles["industry"] = (
                    profiles["symbol"].map(industry_map).fillna("Unknown")
                )
            else:
                profiles["industry"] = "Unknown"

            profiles["description"] = profiles["companyName"] + " company"
            profiles.to_csv(profiles_path, index=False)
            logger.info(
                f"     Created minimal company profiles ({len(profiles)} companies)"
            )

        output_files["profiles"] = profiles_path

        # ============================================
        # STEP 8: Equity curves
        # ============================================
        equity_data = []
        symbols = (
            df_predict["symbol"].unique()[:100]
            if "symbol" in df_predict.columns
            else []
        )

        for symbol in symbols:
            df_sym = (
                df_predict[df_predict["symbol"] == symbol].sort_values("date")
                if "date" in df_predict.columns
                else df_predict[df_predict["symbol"] == symbol]
            )

            if "return_1m" in df_sym.columns:
                df_sym = df_sym.copy()
                df_sym["cumulative_return"] = (
                    1 + df_sym["return_1m"].fillna(0)
                ).cumprod()
            else:
                df_sym = df_sym.copy()
                df_sym["cumulative_return"] = 1.0

            for _, row in df_sym.iterrows():
                equity_data.append(
                    {
                        "symbol": symbol,
                        "date": row["date"] if "date" in row else pd.Timestamp.now(),
                        "equity_value": row.get("cumulative_return", 1.0) * 100,
                        "return": row.get("return_1m", 0),
                    }
                )

        df_equity = pd.DataFrame(equity_data)
        equity_path = f"{self.data_dir}/all_equity_curves.csv"
        df_equity.to_csv(equity_path, index=False)
        output_files["equity"] = equity_path

        logger.info(f"    Created: {equity_path}")
        logger.info(f"      Equity curves for {len(symbols)} stocks")

        # ============================================
        # STEP 9: Summary
        # ============================================
        logger.info("=" * 60)
        logger.info(" Agent Output Files Summary:")
        logger.info(
            f"   1. Combined CSV: {len(df_output):,} rows × {len(df_output.columns)} columns"
        )
        logger.info("      Target: 40 columns")
        logger.info(
            f"      Status: {' PERFECT MATCH!' if len(df_output.columns) == 40 else '⚠️ COUNT MISMATCH'}"
        )
        logger.info(f"   2. Company Profiles: {len(profiles):,} companies")
        logger.info(f"   3. Equity Curves: {len(df_equity):,} data points")

        # Show column breakdown
        logger.info("\n    Column breakdown:")
        logger.info("      Core (3): symbol, pred_prob_next_month, signal")
        logger.info(
            "      Hybrid Scores (6): Hybrid_Score, Fundamental_Score, Technical_Score, etc."
        )
        logger.info("      Fundamentals (11): roe, roic, peRatio, etc.")
        logger.info("      Technicals (8): return_1m, RSI_14, MACD, etc.")
        logger.info("      Backtest (9): sharpe_1m_annual, cagr, hit_rates, etc.")
        logger.info("      Other (3): date, sector, industry")
        logger.info("=" * 60)

        return output_files


def main():
    """Run backtest pipeline"""
    config = load_config()
    backtester = QuantamentalBacktester(config)

    # Load processed data
    logger.info(" Loading processed data...")
    df = pd.read_parquet(f"{config['data']['data_dir']}/quantamental_monthly.parquet")

    # Run backtest
    backtester.run_backtest(df, use_wandb_logging=True)

    print("\n Backtest complete!")
    print(f"   Results saved to GCS bucket: {config['gcs']['bucket_name']}")


if __name__ == "__main__":
    main()
