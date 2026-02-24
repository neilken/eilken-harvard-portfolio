"""Generate inventory-aware pricing recommendations using lifecycle, stock position, competitor price, and margin guardrails."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis._common import ensure_export_dirs, load_csv_if_exists, load_raw_sales_customers_products_csv, write_csv, write_table_if_possible
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _build_recommendations_from_csv() -> pd.DataFrame:
    """Build recommendations from csv."""
    params = load_params()
    sales, _, products = load_raw_sales_customers_products_csv()
    raw_dir = Path(params["paths"]["raw_generated"])
    ext_dir = Path(params["paths"]["external_generated"])
    inventory = load_csv_if_exists(raw_dir / "inventory_snapshots.csv")
    competitor = load_csv_if_exists(ext_dir / "competitor_snapshots.csv", parse_dates=["captured_at", "snapshot_date"])

    # Recommendations require inventory, sales, and product attributes.
    if inventory.empty or sales.empty or products.empty:
        return pd.DataFrame()

    sales = sales.copy()
    inventory = inventory.copy()
    competitor = competitor.copy() if not competitor.empty else competitor

    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    # Returns are excluded so demand and margin estimates reflect sell-through behavior.
    sales = sales.loc[~sales["returned_flag"]].copy()
    sales["order_week"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")
    sales["contribution_margin_pct_line"] = (
        (sales["transaction_price"] - sales["cogs_unit"] - sales["freight_unit"].fillna(0) - sales["payment_fees_unit"].fillna(0))
        / sales["transaction_price"].where(sales["transaction_price"] != 0)
    )

    inventory["snapshot_date"] = pd.to_datetime(inventory["snapshot_date"])
    inventory["snapshot_week"] = inventory["snapshot_date"] - pd.to_timedelta(inventory["snapshot_date"].dt.weekday, unit="D")

    # Weekly demand and margin estimates are used to calculate stock coverage and pricing headroom.
    weekly_demand = (
        sales.groupby(["sku", "order_week"], as_index=False)
        .agg(
            weekly_units=("units", "sum"),
            avg_transaction_price=("transaction_price", "mean"),
            avg_contribution_margin_pct=("contribution_margin_pct_line", "mean"),
        )
        .rename(columns={"order_week": "snapshot_week"})
    )

    demand_avg = (
        weekly_demand.groupby("sku", as_index=False)
        .agg(
            avg_weekly_units=("weekly_units", "mean"),
            avg_transaction_price=("avg_transaction_price", "mean"),
            avg_contribution_margin_pct=("avg_contribution_margin_pct", "mean"),
        )
    )

    # Use the latest inventory snapshot per SKU for current recommendation decisions.
    latest_inv_idx = inventory.groupby("sku")["snapshot_date"].idxmax()
    latest_inventory = inventory.loc[latest_inv_idx].copy()
    latest_inventory = latest_inventory.merge(demand_avg, on="sku", how="left")
    latest_inventory["days_of_supply"] = (
        latest_inventory["on_hand_units"] / latest_inventory["avg_weekly_units"].where(latest_inventory["avg_weekly_units"] > 0)
    ) * 7
    latest_inventory["overstock_flag"] = latest_inventory["days_of_supply"] > 180

    products = products[["sku", "category", "lifecycle_stage"]].copy()
    latest_inventory = latest_inventory.merge(products, on="sku", how="left")
    latest_inventory["end_of_life_flag"] = latest_inventory["lifecycle_stage"].eq("end_of_life")

    # Latest competitor prices are rolled up to SKU-level benchmarks for pricing position checks.
    if not competitor.empty:
        competitor["snapshot_date"] = pd.to_datetime(competitor["snapshot_date"])
        latest_comp_idx = competitor.groupby(["sku", "competitor_id"])["snapshot_date"].idxmax()
        latest_comp = competitor.loc[latest_comp_idx]
        comp_roll = (
            latest_comp.groupby("sku", as_index=False)
            .agg(
                competitor_min_price=("competitor_price", "min"),
                competitor_median_price=("competitor_price", "median"),
                competitor_promo_any=("promo_flag", "max"),
            )
        )
        latest_inventory = latest_inventory.merge(comp_roll, on="sku", how="left")
    else:
        latest_inventory["competitor_min_price"] = pd.NA
        latest_inventory["competitor_median_price"] = pd.NA
        latest_inventory["competitor_promo_any"] = False

    latest_inventory["price_index_vs_comp_min"] = (
        latest_inventory["avg_transaction_price"] / latest_inventory["competitor_min_price"].where(latest_inventory["competitor_min_price"].notna())
    )
    latest_inventory["margin_floor_pct"] = 0.15
    latest_inventory["strategic_sku_flag"] = False

    # Initialize to hold, then apply rule masks in priority order.
    latest_inventory["action_type"] = "hold"
    latest_inventory["recommended_pct_change"] = 0.0
    latest_inventory["rationale"] = "within_guardrails"

    # Rule precedence: end-of-life markdowns, then overstock markdowns, then underpriced increases.
    eol_mask = latest_inventory["end_of_life_flag"].fillna(False)
    overstock_mask = latest_inventory["overstock_flag"].fillna(False) & ~eol_mask
    underpriced_mask = (
        latest_inventory["price_index_vs_comp_min"].notna()
        & (latest_inventory["price_index_vs_comp_min"] < 0.95)
        & ~(eol_mask | overstock_mask)
        & (latest_inventory["avg_contribution_margin_pct"].fillna(0) > 0.20)
    )

    latest_inventory.loc[eol_mask, ["action_type", "recommended_pct_change", "rationale"]] = [
        "markdown",
        -0.20,
        "end_of_life_inventory_disposition",
    ]
    latest_inventory.loc[overstock_mask, ["action_type", "recommended_pct_change", "rationale"]] = [
        "markdown",
        -0.10,
        "overstock_days_of_supply_guardrail",
    ]
    latest_inventory.loc[underpriced_mask, ["action_type", "recommended_pct_change", "rationale"]] = [
        "increase",
        0.03,
        "underpriced_vs_competitor_with_margin_buffer",
    ]

    # Margin floor guardrail can override markdown recommendations to avoid value-destructive actions.
    low_margin_mask = latest_inventory["avg_contribution_margin_pct"].fillna(0) < latest_inventory["margin_floor_pct"]
    markdown_mask = latest_inventory["action_type"].eq("markdown") & low_margin_mask
    latest_inventory.loc[markdown_mask, ["action_type", "recommended_pct_change", "rationale"]] = [
        "hold",
        0.0,
        "margin_floor_guardrail_hold",
    ]

    latest_inventory["expected_impact_note"] = latest_inventory["action_type"].map(
        {
            "markdown": "inventory_reduction_priority",
            "increase": "margin_improvement_with_demand_risk",
            "hold": "monitor",
        }
    ).fillna("monitor")
    latest_inventory["recommendation_snapshot_date"] = pd.Timestamp.today().date().isoformat()

    cols = [
        "sku",
        "category",
        "lifecycle_stage",
        "snapshot_date",
        "on_hand_units",
        "days_of_supply",
        "avg_weekly_units",
        "avg_transaction_price",
        "competitor_min_price",
        "price_index_vs_comp_min",
        "avg_contribution_margin_pct",
        "action_type",
        "recommended_pct_change",
        "rationale",
        "expected_impact_note",
        "recommendation_snapshot_date",
    ]
    return latest_inventory[cols].sort_values(["action_type", "days_of_supply"], ascending=[True, False])


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=4, task_name="inventory_pricing_engine")
    dirs = ensure_export_dirs()
    step.step("Building inventory and pricing action recommendations from generated data")
    df = _build_recommendations_from_csv()
    if df.empty:
        log_warn("Generated data unavailable for inventory pricing engine; writing empty output")
        df = pd.DataFrame(
            columns=[
                "sku", "category", "lifecycle_stage", "snapshot_date", "on_hand_units", "days_of_supply",
                "avg_weekly_units", "avg_transaction_price", "competitor_min_price", "price_index_vs_comp_min",
                "avg_contribution_margin_pct", "action_type", "recommended_pct_change", "rationale",
                "expected_impact_note", "recommendation_snapshot_date"
            ]
        )
    else:
        log_info(f"recommendation rows={len(df):,}")
        step.step("Applied overstock, lifecycle, competitor, and margin guardrail rules")

    step.step("Writing exports")
    # Recommendation outputs feed both Power BI dashboard visuals and memo recommendation summaries.
    write_table_if_possible(df, "marts", "recommended_actions")
    write_csv(df, dirs["pbi"] / "recommended_actions.csv")
    write_csv(df, dirs["memo"] / "recommended_actions.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
