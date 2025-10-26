r"""
Finance Data Download & Upload Pipeline (Cloud-Only Version)
------------------------------------------------------------

This script:
1. Downloads the S&P 500 ticker list from GCS
2. Fetches OHLCV data for all tickers using yfinance (chunked)
3. Adds technical indicators per ticker using the `ta` library
4. Keeps only core features (trend, momentum, volatility, etc.)
5. Uploads results directly to GCS — no local CSV/Parquet stored
6. Writes a lightweight JSON summary locally for verification

Usage (example):
  $env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\secrets\stock-busters-service-account.json"
  & python src/fin_data_download/data_download.py
"""

import os
import sys
import json
import time
import traceback
from io import BytesIO
from typing import List

import pandas as pd
import numpy as np
import yfinance as yf
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError
from ta import add_all_ta_features

# ---------------------------
#  Configuration
# ---------------------------
BUCKET_NAME = os.environ.get("GCP_BUCKET", "fin-data-bucket-115")
TICKER_FILE_GCS = os.environ.get("GCP_TICKER_PATH", "SP500_list.csv")

START_DATE = os.environ.get("START_DATE", "2019-01-01")
END_DATE = os.environ.get("END_DATE", "2025-09-30")
YF_CHUNK_SIZE = int(os.environ.get("YF_CHUNK_SIZE", "50"))
YF_SLEEP_SEC = float(os.environ.get("YF_SLEEP_SEC", "1.0"))

# Output GCS paths
RAW_GCS_PATH = "sp500_raw_data.csv"
LONG_GCS_PATH = "sp500_long_data.csv"
LONG_TA_GCS_PATH = "sp500_long_data_with_complete_ta.csv"
TA_CORE_CSV_GCS = "sp500_long_data_with_ta_core.csv"
TA_CORE_PQ_GCS = "sp500_long_data_with_ta_core.parquet"

# Columns to keep
CORE_COLUMNS = [
    "Date", "Ticker", "Open", "High", "Low", "Close", "Volume",
    "trend_sma_fast", "trend_sma_slow", "trend_macd", "trend_macd_signal", "trend_adx",
    "momentum_rsi", "momentum_stoch_k", "momentum_wr",
    "volatility_bbm", "volatility_bbh", "volatility_bbl", "volatility_atr",
    "volume_obv", "volume_mfi", "others_dlr"
]

# ---------------------------
#  Helpers: GCS
# ---------------------------
def _cred_hint():
    return (
        " GCP credentials not found.\n"
        "Set GOOGLE_APPLICATION_CREDENTIALS env var, e.g.:\n"
        "  -v '<ABS_PATH_TO_REPO>\\secrets:/app/secrets'\n"
        "  -e GOOGLE_APPLICATION_CREDENTIALS='/app/secrets/stock-busters-service-account.json'\n"
    )

def ensure_gcp_client() -> storage.Client:
    try:
        return storage.Client()
    except DefaultCredentialsError:
        print(_cred_hint())
        raise

def download_from_gcs(bucket_name: str, source_blob: str) -> pd.DataFrame:
    """Download CSV from GCS into a Pandas DataFrame (no local file)."""
    client = ensure_gcp_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(source_blob)
    print(f"⬇️  Downloading {source_blob} from bucket {bucket_name} ...")
    data = blob.download_as_bytes()
    return pd.read_csv(BytesIO(data))

def upload_df_to_gcs(bucket_name: str, dataframe: pd.DataFrame, dest_blob: str, fmt="csv"):
    """Upload a Pandas DataFrame directly to GCS."""
    client = ensure_gcp_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    buffer = BytesIO()

    if fmt == "csv":
        dataframe.to_csv(buffer, index=False)
        content_type = "text/csv"
    elif fmt == "parquet":
        dataframe.to_parquet(buffer, index=False)
        content_type = "application/octet-stream"
    else:
        raise ValueError("Unsupported format (use 'csv' or 'parquet').")

    buffer.seek(0)
    blob.upload_from_file(buffer, content_type=content_type)
    print(f" Uploaded {fmt.upper()} dataframe → gs://{bucket_name}/{dest_blob}")

# ---------------------------
#  yfinance download (chunked)
# ---------------------------
def chunk_list(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i+size] for i in range(0, len(items), size)]

def yf_download_chunked(tickers: List[str], start: str, end: str) -> pd.DataFrame:
    """Download OHLCV data for tickers in chunks."""
    frames = []
    chunks = chunk_list(tickers, YF_CHUNK_SIZE)
    print(f" Downloading {len(tickers)} tickers in {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks, 1):
        print(f"  Chunk {i}/{len(chunks)}: {chunk[:3]}... ({len(chunk)} tickers)")
        try:
            df = yf.download(
                tickers=chunk,
                start=start,
                end=end,
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
            )
            if not isinstance(df.columns, pd.MultiIndex) and len(chunk) == 1:
                df.columns = pd.MultiIndex.from_product([chunk, df.columns])
            frames.append(df)
        except Exception as e:
            print(f"  Error in chunk {i}: {e}")
        time.sleep(YF_SLEEP_SEC)
    return pd.concat(frames, axis=1).sort_index()

# ---------------------------
#  Transformations
# ---------------------------
def wide_to_long(wide: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Convert wide-format MultiIndex DF to long-format."""
    all_frames = []
    for t in tickers:
        try:
            df = wide[t].copy()
            df["Ticker"] = t
            df["Date"] = df.index
            all_frames.append(df)
        except KeyError:
            continue
    out = pd.concat(all_frames, axis=0).reset_index(drop=True)
    cols = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
    return out[cols].dropna(subset=["Close"]).sort_values(["Ticker", "Date"])

def add_ta_per_ticker(long_df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators per ticker."""
    out = []
    for t, group in long_df.groupby("Ticker", sort=False):
        g = group.copy()
        try:
            g = add_all_ta_features(
                df=g, open="Open", high="High", low="Low",
                close="Close", volume="Volume", fillna=True
            )
        except Exception as e:
            print(f"  TA error for {t}: {e}")
        out.append(g)
    df = pd.concat(out, axis=0).reset_index(drop=True)
    print(f" TA features added — total columns: {df.shape[1]}")
    return df

def filter_core(df_ta: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in CORE_COLUMNS if c not in df_ta.columns]
    for c in missing:
        df_ta[c] = np.nan
    return df_ta[CORE_COLUMNS].copy()

# ---------------------------
#  Main
# ---------------------------
def main():
    print("\n Starting StockBusters Data Pipeline (Cloud Mode)")
    print(f"Bucket: gs://{BUCKET_NAME}")
    print(f"Credentials: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
    print(f"Date range: {START_DATE} → {END_DATE}")

    try:
        # Step 1: Load ticker list
        sp500 = download_from_gcs(BUCKET_NAME, TICKER_FILE_GCS)
        tickers = sp500["Symbol"].dropna().astype(str).str.replace(".", "-").unique().tolist()
        print(f"✅ Loaded {len(tickers)} tickers")

        # Step 2: Download OHLCV
        wide = yf_download_chunked(tickers, START_DATE, END_DATE)
        upload_df_to_gcs(BUCKET_NAME, wide, RAW_GCS_PATH, fmt="csv")

        # Step 3: Convert to long
        long_df = wide_to_long(wide, tickers)
        upload_df_to_gcs(BUCKET_NAME, long_df, LONG_GCS_PATH, fmt="csv")

        # Step 4: Add TA per ticker
        df_ta = add_ta_per_ticker(long_df)
        upload_df_to_gcs(BUCKET_NAME, df_ta, LONG_TA_GCS_PATH, fmt="csv")

        # Step 5: Keep only core features
        df_core = filter_core(df_ta)
        upload_df_to_gcs(BUCKET_NAME, df_core, TA_CORE_CSV_GCS, fmt="csv")
        #upload_df_to_gcs(BUCKET_NAME, df_core, TA_CORE_PQ_GCS, fmt="parquet")

        # Step 6: Write summary locally (tiny JSON)
        summary = {
            "tickers": len(tickers),
            "rows": len(df_core),
            "columns": len(df_core.columns),
            "bucket": BUCKET_NAME,
            "upload_time": pd.Timestamp.now().isoformat()
        }
        with open("upload_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print("📄 Created upload_summary.json (local only)")

        print("\n🎉🎉 Pipeline completed successfully! 🎉🎉")

    except Exception as e:
        print("\n[ERROR] Pipeline failed.")
        print(type(e).__name__, ":", e)
        traceback.print_exc()
        print(_cred_hint())
        sys.exit(1)

if __name__ == "__main__":
    main()

