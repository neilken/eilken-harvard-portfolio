"""
Data Processing Module
- Compute technical indicators
- Merge OHLCV with fundamentals
- Clean and validate data
- Create monthly snapshots
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
import logging
import matplotlib.pyplot as plt

from utils import load_config, ensure_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """Process raw data into model-ready features"""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = ensure_dir(config["data"]["data_dir"])
        self.fund_cols = config["features"]["fundamental"]

    def compute_technicals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute technical indicators per symbol:
        - Returns (1M, 1D)
        - EMA (12, 26), MACD, Signal, Histogram
        - RSI (14)
        - Volatility (21D)
        """
        logger.info("🔧 Computing technical indicators...")

        df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
        g = df.groupby("symbol", group_keys=False)

        # Returns
        df["return_1m"] = g["close"].transform(
            lambda x: x.pct_change(21, fill_method=None)
        )
        df["return_1d"] = g["close"].transform(
            lambda x: x.pct_change(1, fill_method=None)
        )

        # EMAs & MACD
        df["ema_12"] = g["close"].transform(
            lambda x: x.ewm(span=12, adjust=False).mean()
        )
        df["ema_26"] = g["close"].transform(
            lambda x: x.ewm(span=26, adjust=False).mean()
        )
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = g["macd"].transform(
            lambda x: x.ewm(span=9, adjust=False).mean()
        )
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # RSI (14-day)
        delta = g["close"].transform(lambda x: x.diff())
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = g["symbol"].transform(
            lambda x: gain.rolling(14, min_periods=5).mean()
        )
        avg_loss = g["symbol"].transform(
            lambda x: loss.rolling(14, min_periods=5).mean()
        )
        rs = avg_gain / (avg_loss + 1e-9)
        df["RSI_14"] = 100 - (100 / (1 + rs))

        # Volatility (21-day)
        df["volatility_21d"] = g["close"].transform(
            lambda x: x.pct_change(fill_method=None).rolling(21, min_periods=5).std()
        )

        # Forward-fill to handle gaps
        df[["RSI_14", "volatility_21d"]] = g[["RSI_14", "volatility_21d"]].ffill()

        logger.info("✅ Technical indicators computed")

        return df

    def merge_fundamentals(
        self, ohlcv_ta: pd.DataFrame, fundamentals: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge OHLCV + technicals with fundamentals using asof merge
        """
        logger.info("🔗 Merging OHLCV with fundamentals...")

        merged = []
        symbols = sorted(set(ohlcv_ta["symbol"]) & set(fundamentals["symbol"]))

        for sym in tqdm(symbols, desc="Merging"):
            left = ohlcv_ta.query("symbol == @sym").sort_values("date")
            right = fundamentals.query("symbol == @sym").sort_values("date")

            if len(left) == 0:
                continue

            if len(right) == 0:
                # No fundamentals available
                for col in self.fund_cols:
                    left[col] = np.nan
                merged.append(left)
                continue

            # Merge asof (backward looking)
            m = pd.merge_asof(
                left, right, on="date", direction="backward", allow_exact_matches=True
            )

            # Forward-fill fundamentals (quarterly updates)
            m[self.fund_cols] = m[self.fund_cols].ffill().bfill(limit=1)
            merged.append(m)

        merged = pd.concat(merged, ignore_index=True)

        # Clean up column names
        if "symbol_x" in merged.columns:
            merged.rename(columns={"symbol_x": "symbol"}, inplace=True)
        if "symbol_y" in merged.columns:
            merged.drop(columns=["symbol_y"], inplace=True, errors="ignore")

        logger.info(
            f"✅ Merged data: {len(merged):,} rows, {merged['symbol'].nunique()} symbols"
        )

        return merged

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean merged data:
        - Drop columns with >80% NaN
        - Forward-fill fundamentals
        - Remove symbols with no fundamentals
        - Replace inf with 0
        """
        logger.info("🧹 Cleaning data...")

        initial_rows = len(df)
        initial_symbols = df["symbol"].nunique()

        # Drop columns with >80% missing
        drop_cols = df.columns[df.isna().mean() > 0.8]
        if len(drop_cols) > 0:
            logger.info(f"   Dropping {len(drop_cols)} high-NaN columns")
            df.drop(columns=drop_cols, inplace=True)

        # Forward-fill fundamentals per symbol
        df = df.sort_values(["symbol", "date"])
        forward_limit = self.config["processing"]["forward_fill_limit"]
        df[self.fund_cols] = df.groupby("symbol")[self.fund_cols].ffill(
            limit=forward_limit
        )

        # Optional: backfill once at the start
        backfill_limit = self.config["processing"]["backfill_limit"]
        df[self.fund_cols] = df.groupby("symbol")[self.fund_cols].bfill(
            limit=backfill_limit
        )

        # Drop symbols with 100% NaN in fundamentals
        drop_syms = df.groupby("symbol")[self.fund_cols].apply(
            lambda g: g.isna().all().all()
        )
        drop_syms = drop_syms[drop_syms].index.tolist()

        if drop_syms:
            logger.info(f"   Dropping {len(drop_syms)} symbols with no fundamentals")
            df = df[~df["symbol"].isin(drop_syms)]

        # Replace inf with 0
        if self.config["processing"]["remove_inf"]:
            df.replace([np.inf, -np.inf], 0, inplace=True)

        logger.info(
            f"✅ Cleaned: {len(df):,} rows ({initial_rows-len(df):,} removed), "
            f"{df['symbol'].nunique()} symbols ({initial_symbols-df['symbol'].nunique()} removed)"
        )

        return df

    def validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate data coverage and filter low-coverage symbols
        """
        logger.info("✅ Validating data coverage...")

        coverage = df.groupby("symbol")["date"].count().sort_values()
        median_rows = coverage.median()
        threshold = median_rows * self.config["processing"]["coverage_threshold_ratio"]

        # Plot coverage distribution
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(range(len(coverage)), coverage.values)
            plt.axhline(
                y=threshold,
                color="r",
                linestyle="--",
                label=f"Threshold: {threshold:.0f}",
            )
            plt.title("Data Coverage per Symbol")
            plt.xlabel("Symbol Index")
            plt.ylabel("Row Count")
            plt.legend()
            plt.grid(alpha=0.3)
            plt.savefig(f"{self.data_dir}/coverage_distribution.png")
            plt.close()
            logger.info(
                f"   Saved coverage plot → {self.data_dir}/coverage_distribution.png"
            )
        except Exception as e:
            logger.warning(f"Could not create plot: {e}")

        # Filter low-coverage symbols
        low_cov = coverage[coverage < threshold]
        if len(low_cov) > 0:
            logger.info(f"   Filtering {len(low_cov)} low-coverage symbols")
            df = df[~df["symbol"].isin(low_cov.index)]

        logger.info(
            f"✅ Final dataset: {df['symbol'].nunique()} symbols, {len(df):,} rows"
        )

        return df

    def create_monthly_snapshot(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create end-of-month snapshots
        """
        if not self.config["processing"]["monthly_snapshot"]:
            return df

        logger.info("📅 Creating monthly snapshots...")

        df_monthly = (
            df.groupby(["symbol", pd.Grouper(key="date", freq="ME")])
            .tail(1)
            .reset_index(drop=True)
        )

        logger.info(f"✅ Monthly snapshots: {len(df_monthly):,} rows")

        return df_monthly

    def process_all(
        self, ohlcv: pd.DataFrame, fundamentals: pd.DataFrame, sp500_index: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Complete processing pipeline

        Returns:
            Processed DataFrame ready for modeling
        """
        logger.info("🚀 Starting data processing pipeline...")

        # Step 1: Compute technicals
        cache_path = f"{self.data_dir}/ohlcv_with_technicals.parquet"
        try:
            if self.config["data"]["cache_enabled"]:
                ohlcv_ta = pd.read_parquet(cache_path)
                logger.info("💾 Using cached technicals")
            else:
                raise FileNotFoundError
        except Exception:
            ohlcv_ta = self.compute_technicals(ohlcv)
            ohlcv_ta.to_parquet(cache_path, index=False)

        # Step 2: Merge with fundamentals
        merged = self.merge_fundamentals(ohlcv_ta, fundamentals)

        # Step 3: Clean data
        cleaned = self.clean_data(merged)

        # Save intermediate result
        cleaned.to_parquet(f"{self.data_dir}/quantamental_cleaned.parquet", index=False)
        logger.info("💾 Saved → quantamental_cleaned.parquet")

        # Step 4: Validate and filter
        validated = self.validate_data(cleaned)
        validated.to_parquet(
            f"{self.data_dir}/quantamental_filtered.parquet", index=False
        )
        validated.to_csv(f"{self.data_dir}/quantamental_filtered.csv", index=False)
        logger.info("💾 Saved → quantamental_filtered.parquet & .csv")

        # Step 5: Merge with S&P 500 benchmark
        sp500_index = sp500_index.rename(columns={"close": "sp500_close"})
        validated = pd.merge(
            validated, sp500_index[["date", "sp500_close"]], on="date", how="left"
        )
        validated["sp500_return_1m"] = validated["sp500_close"].pct_change(21)

        # Step 6: Create monthly snapshots
        df_monthly = self.create_monthly_snapshot(validated)

        # Save final processed data
        df_monthly.to_parquet(
            f"{self.data_dir}/quantamental_monthly.parquet", index=False
        )
        logger.info("💾 Saved → quantamental_monthly.parquet")

        logger.info("✅ Data processing pipeline complete!")

        return df_monthly


def main():
    """Test data processing"""
    config = load_config()
    processor = DataProcessor(config)

    # Load raw data
    logger.info("📂 Loading raw data...")
    ohlcv = pd.read_parquet(f"{config['data']['data_dir']}/ohlcv_raw.parquet")
    fundamentals = pd.read_parquet(
        f"{config['data']['data_dir']}/fundamentals_combined.parquet"
    )
    sp500_index = pd.read_parquet(f"{config['data']['data_dir']}/sp500_index.parquet")

    # Process
    df_processed = processor.process_all(ohlcv, fundamentals, sp500_index)

    print("\n✅ Processing complete!")
    print(f"   Final shape: {df_processed.shape}")
    print(f"   Symbols: {df_processed['symbol'].nunique()}")
    print(f"   Date range: {df_processed['date'].min()} → {df_processed['date'].max()}")


if __name__ == "__main__":
    main()
