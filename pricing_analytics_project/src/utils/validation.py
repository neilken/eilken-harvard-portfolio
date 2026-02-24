"""Data validation helpers used by generation and load steps."""

from __future__ import annotations

import pandas as pd


def basic_sales_sanity(df: pd.DataFrame) -> None:
    """Handle basic sales sanity."""
    if (df["transaction_price"] < 0).any():
        raise ValueError("Found negative transaction_price values")
    if (df["list_price"] < df["transaction_price"]).any():
        raise ValueError("Found transaction_price greater than list_price")
    if (df["units"] < 0).any():
        raise ValueError("Found negative units")
