"""Shared analysis helpers for reading inputs, exporting outputs, and writing analysis tables to PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
from sqlalchemy import inspect, text

from src.utils.config import load_params
from src.utils.db import get_engine
from src.utils.logging import StepLogger, log_info, log_warn


def ensure_export_dirs() -> dict[str, Path]:
    """Ensure export dirs."""
    params = load_params()
    # Shared directory creation keeps export path setup consistent across analysis modules.
    dirs = {
        "pbi": Path(params["paths"]["exports_for_pbi"]),
        "memo": Path(params["paths"]["exports_for_memo"]),
        "figures": Path(params["paths"]["memo_figures"]),
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def try_read_sql(query: str) -> pd.DataFrame:
    """Handle try read sql."""
    try:
        # Database reads are optional in analysis modules, so failures fall back to CSV-based workflows.
        engine = get_engine()
        with engine.begin() as conn:
            return pd.read_sql(query, conn)
    except Exception as exc:
        log_warn(f"Database query unavailable, placeholder output will be used: {exc}")
        return pd.DataFrame()


def placeholder_or_db(query: str, placeholder: pd.DataFrame, step: StepLogger, label: str) -> pd.DataFrame:
    """Return placeholder output or database output based on availability."""
    step.step(f"Loading data for {label}")
    df = try_read_sql(query)
    if df.empty:
        log_warn(f"Placeholder output selected for {label}")
        return placeholder
    log_info(f"Loaded rows={len(df):,} for {label}")
    return df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write csv."""
    # CSV exports are the portable interface for memo generation and CSV-based Power BI imports.
    df.to_csv(path, index=False)
    log_info(f"Wrote file {path.resolve()}")


def load_csv_if_exists(path: Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    """Load csv if exists."""
    if not path.exists():
        return pd.DataFrame()
    # Date parsing is optional because each export exposes different date columns.
    return pd.read_csv(path, parse_dates=parse_dates)


def load_raw_sales_customers_products_csv() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load raw sales customers products csv."""
    params = load_params()
    raw_dir = Path(params["paths"]["raw_generated"])
    sales = load_csv_if_exists(raw_dir / "sales_order_lines.csv", parse_dates=["order_date"])
    customers = load_csv_if_exists(raw_dir / "customers.csv")
    products = load_csv_if_exists(raw_dir / "products.csv")
    return sales, customers, products


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate identifier."""
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def write_table_if_possible(
    df: pd.DataFrame,
    schema: str,
    table: str,
    if_exists: str = "replace",
) -> bool:
    """Write a dataframe to Postgres with a rerun-safe refresh pattern."""
    schema = _validate_identifier(schema)
    table = _validate_identifier(table)
    try:
        # Centralized writes keep schema creation, chunking, and logging behavior consistent.
        # The default refresh path avoids drop and recreate so dependent pbi views remain valid.
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

        # Preserve original pandas to_sql behavior for explicit append/fail callers.
        if if_exists in {"append", "fail"}:
            df.to_sql(
                name=table,
                con=engine,
                schema=schema,
                if_exists=if_exists,
                index=False,
                chunksize=5000,
                method="multi",
            )
            log_info(f"Wrote Postgres table {schema}.{table} rows={len(df):,}")
            return True

        if if_exists != "replace":
            raise ValueError(f"Unsupported if_exists mode: {if_exists}")

        inspector = inspect(engine)
        table_exists = inspector.has_table(table_name=table, schema=schema)

        # First write can create the table directly.
        if not table_exists:
            df.to_sql(
                name=table,
                con=engine,
                schema=schema,
                if_exists="replace",
                index=False,
                chunksize=5000,
                method="multi",
            )
            log_info(f"Wrote Postgres table {schema}.{table} rows={len(df):,}")
            return True

        # Existing tables are refreshed with TRUNCATE + INSERT to preserve dependencies.
        existing_cols = [col["name"] for col in inspector.get_columns(table_name=table, schema=schema)]
        incoming_cols = list(df.columns)
        if existing_cols != incoming_cols:
            log_warn(
                f"Postgres write skipped for {schema}.{table}: column mismatch "
                f"(existing={existing_cols}, incoming={incoming_cols})"
            )
            return False

        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {schema}.{table}"))
        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists="append",
            index=False,
            chunksize=5000,
            method="multi",
        )
        log_info(f"Refreshed Postgres table {schema}.{table} rows={len(df):,}")
        return True
    except Exception as exc:
        log_warn(f"Postgres write skipped for {schema}.{table}: {exc}")
        return False
