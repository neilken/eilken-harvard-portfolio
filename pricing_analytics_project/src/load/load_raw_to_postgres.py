"""Create raw tables and load generated ERP CSV files into PostgreSQL using COPY."""

from __future__ import annotations

from pathlib import Path

import psycopg2

from src.utils.config import load_params
from src.utils.db import get_db_config
from src.utils.logging import StepLogger, log_info


RAW_FILE_MAP = {
    "products": "products.csv",
    "customers": "customers.csv",
    "sales_order_lines": "sales_order_lines.csv",
    "inventory_snapshots": "inventory_snapshots.csv",
}


def _connect():
    """Handle connect."""
    # Raw loads use admin credentials so schema DDL and index creation always have sufficient permissions.
    cfg = get_db_config(admin=True)
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["db"],
        user=cfg["user"],
        password=cfg["password"],
    )


def _copy_table(cur, table: str, file_path: Path) -> None:
    """Handle copy table."""
    # COPY is used for speed and to keep the load pattern close to warehouse ingestion workflows.
    with file_path.open("r", encoding="utf-8") as f:
        cur.copy_expert(f"COPY raw.{table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)", f)


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    raw_dir = Path(params["paths"]["raw_generated"])
    # Raw DDL is executed on each run so tables exist even after a fresh container rebuild.
    ddl_path = Path("sql/raw_tables.sql")
    step = StepLogger(total_steps=6, task_name="load_raw")

    step.step("Connecting to Postgres")
    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        step.step("Creating raw tables from SQL DDL")
        cur.execute(ddl_path.read_text(encoding="utf-8"))
        conn.commit()

        step.step("Loading CSV files with COPY")
        for table, filename in RAW_FILE_MAP.items():
            file_path = raw_dir / filename
            log_info(f"Loading raw.{table} from {file_path}")
            # TRUNCATE keeps table definitions and indexes while replacing the current raw dataset contents.
            cur.execute(f"TRUNCATE TABLE raw.{table}")
            _copy_table(cur, table, file_path)
        conn.commit()

        step.step("Creating indexes")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_order_date ON raw.sales_order_lines(order_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_sku ON raw.sales_order_lines(sku)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON raw.sales_order_lines(customer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inventory_snapshot_date ON raw.inventory_snapshots(snapshot_date)")
        conn.commit()

        step.step("Running ANALYZE")
        # ANALYZE refreshes planner stats so dbt queries use better execution plans.
        for table in RAW_FILE_MAP.keys():
            cur.execute(f"ANALYZE raw.{table}")
        conn.commit()

        step.step("Printing row counts")
        for table in RAW_FILE_MAP.keys():
            cur.execute(f"SELECT COUNT(*) FROM raw.{table}")
            log_info(f"raw.{table} row_count={cur.fetchone()[0]:,}")
        conn.commit()
    finally:
        # Explicit cleanup keeps the loader safe when a prior step raises an exception.
        cur.close()
        conn.close()
        log_info("Database connection closed")


if __name__ == "__main__":
    main()
