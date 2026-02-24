"""Generate simulated competitor pricing snapshots from synthetic sales baselines and apply snapshot aggregation rules."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    raw_dir = Path(params["paths"]["raw_generated"])
    ext_dir = Path(params["paths"]["external_generated"])
    ext_dir.mkdir(parents=True, exist_ok=True)
    # Offset the seed so competitor simulation is reproducible but not identical to ERP generation randomness.
    rng = np.random.default_rng(int(params.get("seed", 42)) + 101)
    step = StepLogger(total_steps=5, task_name="competitor_simulator")

    step.step("Loading generated sales data")
    sales = pd.read_csv(raw_dir / "sales_order_lines.csv", parse_dates=["order_date"])

    step.step("Building weekly SKU baseline prices")
    # Weekly SKU median list price is used as the competitor pricing baseline.
    sales["snapshot_week"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")
    sku_week = sales.groupby(["sku", "snapshot_week"], as_index=False).agg(list_price=("list_price", "median"))

    step.step("Generating competitor snapshots")
    competitors = [f"COMP{i+1}" for i in range(int(params["generation"].get("competitor_count", 3)))]
    rows = []
    # Multiple captures per snapshot date are generated first, then aggregated to the latest capture.
    for rec in sku_week.itertuples(index=False):
        for comp in competitors:
            promo_flag = bool(rng.random() < 0.1)
            # Competitor price is anchored to synthetic list price with small noise and optional promo discount.
            comp_price = rec.list_price * (1 + rng.normal(0, 0.03)) * (1 - (rng.uniform(0.05, 0.2) if promo_flag else 0))
            captured_at = pd.Timestamp(rec.snapshot_week) + pd.Timedelta(days=int(rng.integers(0, 7)), hours=int(rng.integers(0, 24)))
            rows.append(
                {
                    "captured_at": captured_at.isoformat(),
                    "snapshot_date": captured_at.date().isoformat(),
                    "competitor_id": comp,
                    "sku": rec.sku,
                    "competitor_price": round(max(0.01, comp_price), 2),
                    "competitor_shipping": round(float(rng.uniform(0, 18)), 2),
                    "in_stock": bool(rng.random() > 0.08),
                    "promo_flag": promo_flag,
                    "url": f"https://example.com/{comp.lower()}/{rec.sku.lower()}",
                    "match_score": round(float(rng.uniform(0.75, 0.99)), 2),
                }
            )
    comp = pd.DataFrame(rows)
    log_info(f"raw generated competitor rows before aggregation={len(comp):,}")

    step.step("Applying multi-capture aggregation rule")
    comp["captured_at"] = pd.to_datetime(comp["captured_at"])
    # Latest-capture rule matches the project plan requirement for normalized competitor snapshots.
    comp = (
        comp.sort_values("captured_at")
        .groupby(["snapshot_date", "competitor_id", "sku"], as_index=False)
        .tail(1)
        .sort_values(["snapshot_date", "competitor_id", "sku"])
    )
    log_info("Aggregation rule=latest capture per snapshot_date, competitor_id, sku")

    step.step("Writing CSV output")
    out_path = ext_dir / "competitor_snapshots.csv"
    comp.to_csv(out_path, index=False)
    log_info(f"competitor_snapshots rows={len(comp):,}")
    log_info(f"CSV output written to {out_path.resolve()}")


if __name__ == "__main__":
    main()
