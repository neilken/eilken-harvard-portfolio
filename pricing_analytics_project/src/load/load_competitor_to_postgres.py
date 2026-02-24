"""Load simulated competitor snapshot CSV data into PostgreSQL raw tables and refresh indexes."""

from __future__ import annotations

from pathlib import Path

import psycopg2

from src.utils.config import load_params
from src.utils.db import get_db_config
from src.utils.logging import StepLogger, log_info


def _connect():
    """Handle connect."""
    # Admin credentials are used here because the loader executes DDL and index statements.
    cfg = get_db_config(admin=True)
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["db"],
        user=cfg["user"],
        password=cfg["password"],
    )


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    # Competitor snapshots are generated separately, then loaded after core raw ERP tables.
    csv_path = Path(params["paths"]["external_generated"]) / "competitor_snapshots.csv"
    step = StepLogger(total_steps=5, task_name="load_competitor")

    step.step("Connecting to Postgres")
    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        step.step("Ensuring raw table DDL exists")
        ddl_path = Path("sql/raw_tables.sql")
        cur.execute(ddl_path.read_text(encoding="utf-8"))
        conn.commit()

        step.step("Loading competitor snapshots with COPY")
        cur.execute("TRUNCATE TABLE raw.competitor_snapshots")
        # COPY keeps large snapshot loads fast and consistent with the raw ERP loader pattern.
        with csv_path.open("r", encoding="utf-8") as f:
            cur.copy_expert("COPY raw.competitor_snapshots FROM STDIN WITH (FORMAT CSV, HEADER TRUE)", f)
        conn.commit()

        step.step("Creating indexes and running ANALYZE")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_snapshot_date ON raw.competitor_snapshots(snapshot_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_sku ON raw.competitor_snapshots(sku)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_competitor ON raw.competitor_snapshots(competitor_id)")
        # ANALYZE refreshes planner statistics for dbt competitive-position models.
        cur.execute("ANALYZE raw.competitor_snapshots")
        conn.commit()

        step.step("Printing row count")
        cur.execute("SELECT COUNT(*) FROM raw.competitor_snapshots")
        log_info(f"raw.competitor_snapshots row_count={cur.fetchone()[0]:,}")
    finally:
        # Explicit cleanup keeps the loader safe when a prior step raises an exception.
        cur.close()
        conn.close()
        log_info("Database connection closed")


if __name__ == "__main__":
    main()
