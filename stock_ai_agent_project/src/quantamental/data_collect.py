"""
Data Collection Module
Fetches stock data from Financial Modeling Prep (FMP) API:
- S&P 500 constituent list
- OHLCV (price/volume) data
- Fundamental metrics (quarterly + annual fallback)
"""

import os
import asyncio
import aiohttp
import pandas as pd
from tqdm import tqdm
import logging

from utils import load_config, ensure_dir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FMPDataCollector:
    """Collects stock data from FMP API"""

    def __init__(self, config: dict):
        self.config = config
        self.api_key = config["api"]["fmp_api_key"]
        self.base_url = config["api"]["base_url"]
        self.start_date = config["data"]["start_date"]
        self.end_date = config["data"]["end_date"]
        self.data_dir = ensure_dir(config["data"]["data_dir"])
        self.concurrency = config["api"]["concurrency"]
        self.headers = {"User-Agent": "quantamental/1.0"}

        logger.info("📊 FMP Data Collector initialized")
        logger.info(f"   Date range: {self.start_date} → {self.end_date}")

    async def fetch_sp500(self) -> list:
        """Fetch S&P 500 constituent tickers"""
        cache_path = f"{self.data_dir}/sp500_tickers.csv"

        if os.path.exists(cache_path) and self.config["data"]["cache_enabled"]:
            logger.info("💾 Using cached S&P 500 tickers")
            df = pd.read_csv(cache_path)
            return df["symbol"].tolist()

        url = f"{self.base_url}/sp500_constituent?apikey={self.api_key}"

        async with aiohttp.ClientSession(headers=self.headers) as sess:
            async with sess.get(url) as r:
                if r.status != 200:
                    raise RuntimeError(f"SP500 fetch failed: HTTP {r.status}")
                js = await r.json()

        tickers = [x["symbol"] for x in js if "symbol" in x]

        # Save to cache
        pd.DataFrame({"symbol": tickers}).to_csv(cache_path, index=False)
        logger.info(f"✅ Loaded {len(tickers)} S&P 500 tickers")

        return tickers

    async def fetch_ohlcv_symbol(
        self, sess: aiohttp.ClientSession, symbol: str
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a single symbol"""
        url = (
            f"{self.base_url}/historical-price-full/{symbol}"
            f"?from={self.start_date}&to={self.end_date}&apikey={self.api_key}"
        )

        try:
            async with sess.get(url, timeout=self.config["api"]["timeout"]) as r:
                if r.status != 200:
                    logger.warning(f"⚠️ OHLCV failed for {symbol}: {r.status}")
                    return None
                js = await r.json()
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Timeout for {symbol}")
            return None

        hist = js.get("historical", [])
        if not hist:
            return None

        df = pd.DataFrame(hist)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"])

        return df[
            ["symbol", "date", "open", "high", "low", "close", "adjClose", "volume"]
        ].rename(columns={"adjClose": "adj_close"})

    async def fetch_ohlcv_all(self, symbols: list) -> pd.DataFrame:
        """Fetch OHLCV data for all symbols"""
        cache_path = f"{self.data_dir}/ohlcv_raw.parquet"

        if os.path.exists(cache_path) and self.config["data"]["cache_enabled"]:
            logger.info("💾 Using cached OHLCV data")
            return pd.read_parquet(cache_path)

        connector = aiohttp.TCPConnector(limit_per_host=self.concurrency)
        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector
        ) as sess:
            tasks = [self.fetch_ohlcv_symbol(sess, s) for s in symbols]
            out = []

            for fut in tqdm(
                asyncio.as_completed(tasks), total=len(tasks), desc="Fetching OHLCV"
            ):
                try:
                    df = await fut
                    if df is not None and not df.empty:
                        out.append(df)
                except Exception as e:
                    logger.warning(f"Error fetching OHLCV: {e}")
                    continue

        df_all = pd.concat(out, ignore_index=True)
        df_all.to_parquet(cache_path, index=False)

        logger.info(f"✅ Fetched OHLCV for {df_all['symbol'].nunique()} symbols")
        logger.info(f"   Total rows: {len(df_all):,}")

        return df_all

    async def fetch_fundamentals_symbol(
        self, sess: aiohttp.ClientSession, symbol: str, period: str = "quarter"
    ) -> pd.DataFrame:
        """Fetch fundamental metrics for a single symbol"""
        url = (
            f"{self.base_url}/key-metrics/{symbol}"
            f"?period={period}&limit=12&apikey={self.api_key}"
        )

        try:
            async with sess.get(url, timeout=30) as r:
                if r.status != 200:
                    return None
                js = await r.json()
        except Exception:
            return None

        if not js:
            return None

        df = pd.DataFrame(js)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"])
        df["period_type"] = period

        return df.dropna(subset=["date"])

    async def fetch_fundamentals_combined(self, symbols: list) -> pd.DataFrame:
        """
        Fetch fundamentals with quarterly + annual fallback
        If quarterly data is insufficient, use annual data
        """
        cache_path = f"{self.data_dir}/fundamentals_combined.parquet"

        if os.path.exists(cache_path) and self.config["data"]["cache_enabled"]:
            logger.info("💾 Using cached fundamentals")
            return pd.read_parquet(cache_path)

        connector = aiohttp.TCPConnector(limit_per_host=self.concurrency)
        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector
        ) as sess:
            all_data = []

            for symbol in tqdm(symbols, desc="Fetching Fundamentals"):
                # Try quarterly first
                df_q = await self.fetch_fundamentals_symbol(sess, symbol, "quarter")

                if df_q is not None and len(df_q) >= 4:
                    # Sufficient quarterly data
                    all_data.append(df_q)
                else:
                    # Fallback to annual
                    df_a = await self.fetch_fundamentals_symbol(sess, symbol, "annual")
                    if df_a is not None:
                        all_data.append(df_a)

        if not all_data:
            raise RuntimeError("No fundamental data fetched")

        df_all = pd.concat(all_data, ignore_index=True)
        df_all.to_parquet(cache_path, index=False)

        logger.info(f"✅ Fetched fundamentals for {df_all['symbol'].nunique()} symbols")
        logger.info(f"   Total rows: {len(df_all):,}")

        return df_all

    async def fetch_sp500_index(self) -> pd.DataFrame:
        """Fetch S&P 500 index (^GSPC) for benchmarking"""
        cache_path = f"{self.data_dir}/sp500_index.parquet"

        if os.path.exists(cache_path) and self.config["data"]["cache_enabled"]:
            logger.info("💾 Using cached S&P 500 index")
            return pd.read_parquet(cache_path)

        url = (
            f"{self.base_url}/historical-price-full/%5EGSPC"
            f"?from={self.start_date}&to={self.end_date}&apikey={self.api_key}"
        )

        async with aiohttp.ClientSession(headers=self.headers) as sess:
            async with sess.get(url, timeout=30) as r:
                js = await r.json()

        df = pd.DataFrame(js["historical"])
        df["symbol"] = "^GSPC"
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "open", "high", "low", "close", "adjClose", "volume"]]
        df.rename(columns={"adjClose": "adj_close"}, inplace=True)
        df["return_1d"] = df["close"].pct_change().round(3)
        df = df.sort_values("date")

        df.to_parquet(cache_path, index=False)
        df.to_csv(f"{self.data_dir}/sp500_index.csv", index=False)

        logger.info("✅ Fetched S&P 500 index benchmark")

        return df

    async def fetch_company_profile(
        self, sess: aiohttp.ClientSession, symbol: str
    ) -> dict:
        """Fetch company profile for a single symbol"""
        url = f"{self.base_url}/profile/{symbol}?apikey={self.api_key}"

        try:
            async with sess.get(url, timeout=30) as r:
                if r.status != 200:
                    return None
                js = await r.json()
                if js and len(js) > 0:
                    return js[0]  # Profile returns a list with single item
        except Exception:
            return None

        return None

    async def fetch_company_profiles(self, symbols: list) -> pd.DataFrame:
        """
        Fetch company profiles (sector, industry, etc.) for all symbols
        This is needed for agent integration
        """
        cache_path = f"{self.data_dir}/company_profiles.parquet"

        if os.path.exists(cache_path) and self.config["data"]["cache_enabled"]:
            logger.info("💾 Using cached company profiles")
            return pd.read_parquet(cache_path)

        logger.info("📊 Fetching company profiles...")

        connector = aiohttp.TCPConnector(limit_per_host=self.concurrency)
        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector
        ) as sess:
            profiles = []

            for symbol in tqdm(symbols, desc="Fetching Profiles"):
                profile = await self.fetch_company_profile(sess, symbol)
                if profile:
                    profiles.append(profile)

        if not profiles:
            logger.warning("No company profiles fetched")
            return pd.DataFrame()

        df_profiles = pd.DataFrame(profiles)
        df_profiles.to_parquet(cache_path, index=False)
        df_profiles.to_csv(f"{self.data_dir}/company_profiles.csv", index=False)

        logger.info(f"✅ Fetched profiles for {len(df_profiles)} companies")

        return df_profiles

    async def collect_all(self) -> dict:
        """
        Main collection method - fetches all data

        Returns:
            Dictionary with keys: sp500_tickers, ohlcv, fundamentals, sp500_index, company_profiles
        """
        logger.info("🚀 Starting data collection...")

        # Fetch S&P 500 tickers
        sp500_tickers = await self.fetch_sp500()

        # Fetch all data in parallel
        ohlcv_task = self.fetch_ohlcv_all(sp500_tickers)
        fundamentals_task = self.fetch_fundamentals_combined(sp500_tickers)
        sp500_index_task = self.fetch_sp500_index()
        profiles_task = self.fetch_company_profiles(sp500_tickers)

        ohlcv, fundamentals, sp500_index, company_profiles = await asyncio.gather(
            ohlcv_task, fundamentals_task, sp500_index_task, profiles_task
        )

        logger.info("✅ Data collection complete!")

        return {
            "sp500_tickers": sp500_tickers,
            "ohlcv": ohlcv,
            "fundamentals": fundamentals,
            "sp500_index": sp500_index,
            "company_profiles": company_profiles,
        }


async def main():
    """Test data collection"""
    config = load_config()
    collector = FMPDataCollector(config)

    data = await collector.collect_all()

    print("\n📊 Collection Summary:")
    print(f"   S&P 500 Tickers: {len(data['sp500_tickers'])}")
    print(f"   OHLCV rows: {len(data['ohlcv']):,}")
    print(f"   Fundamentals rows: {len(data['fundamentals']):,}")
    print(f"   S&P 500 Index rows: {len(data['sp500_index']):,}")


if __name__ == "__main__":
    asyncio.run(main())
