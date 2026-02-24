"""Simulate pricing scenarios using elasticity estimates and baseline category performance metrics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis._common import ensure_export_dirs, load_csv_if_exists, load_raw_sales_customers_products_csv, write_csv, write_table_if_possible
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _load_baseline_weekly_by_category() -> pd.DataFrame:
    """Load baseline weekly by category."""
    sales, _, products = load_raw_sales_customers_products_csv()
    if sales.empty or products.empty:
        return pd.DataFrame()
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    # Returns are excluded because scenarios model forward demand and gross profit impact.
    sales = sales.loc[~sales["returned_flag"]].copy()
    sales = sales.merge(products[["sku", "category"]], on="sku", how="left")
    sales["revenue_line"] = sales["transaction_price"] * sales["units"]
    sales["gross_profit_line"] = (sales["transaction_price"] - sales["cogs_unit"]) * sales["units"]
    sales["week_start"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")
    # Category-week baseline is the simulation grain for simple portfolio pricing scenarios.
    weekly = (
        sales.groupby(["category", "week_start"], as_index=False)
        .agg(
            units=("units", "sum"),
            avg_price=("transaction_price", "mean"),
            revenue=("revenue_line", "sum"),
            gross_profit=("gross_profit_line", "sum"),
            avg_cogs_unit=("cogs_unit", "mean"),
        )
    )
    return weekly


def _load_elasticities_by_category() -> pd.DataFrame:
    """Load elasticities by category."""
    params = load_params()
    pbi_path = Path(params["paths"]["exports_for_pbi"]) / "elasticity_estimates.csv"
    elas = load_csv_if_exists(pbi_path)
    if elas.empty:
        return pd.DataFrame()
    # Keep only category elasticities because scenarios are defined at category level.
    if "grain_type" in elas.columns:
        elas = elas.loc[elas["grain_type"] == "category", ["grain", "elasticity_b1"]].rename(columns={"grain": "category"})
    else:
        elas = elas.rename(columns={"grain": "category"})
    return elas.dropna(subset=["category", "elasticity_b1"])


def _simulate_scenario(weekly: pd.DataFrame, pct_change: pd.Series | float, scenario_name: str) -> pd.DataFrame:
    """Simulate scenario."""
    df = weekly.copy()
    # pct_change can be a single portfolio-wide value or a category-indexed Series for tiered strategies.
    if np.isscalar(pct_change):
        df["pct_price_change"] = float(pct_change)
    else:
        df = df.merge(pct_change.rename("pct_price_change"), left_on="category", right_index=True, how="left")
        df["pct_price_change"] = df["pct_price_change"].fillna(0.0)

    df["elasticity_b1"] = df["elasticity_b1"].fillna(-1.0)
    # Constant-elasticity demand response converts price changes into projected unit multipliers.
    df["unit_multiplier"] = (1 + df["pct_price_change"]).clip(lower=0.01) ** df["elasticity_b1"]
    df["new_units"] = (df["units"] * df["unit_multiplier"]).clip(lower=0)
    df["new_price"] = df["avg_price"] * (1 + df["pct_price_change"])
    df["new_revenue"] = df["new_units"] * df["new_price"]
    df["new_gross_profit"] = df["new_units"] * (df["new_price"] - df["avg_cogs_unit"])

    baseline_revenue = df["revenue"].sum()
    baseline_gp = df["gross_profit"].sum()
    baseline_margin = baseline_gp / baseline_revenue if baseline_revenue else np.nan
    new_revenue = df["new_revenue"].sum()
    new_gp = df["new_gross_profit"].sum()
    new_margin = new_gp / new_revenue if new_revenue else np.nan

    # Return one summarized row per scenario to simplify dashboard comparison cards and tables.
    return pd.DataFrame(
        {
            "scenario_name": [scenario_name],
            "projected_revenue_change_pct": [((new_revenue / baseline_revenue) - 1) * 100 if baseline_revenue else np.nan],
            "projected_gross_profit_change_pct": [((new_gp / baseline_gp) - 1) * 100 if baseline_gp else np.nan],
            "projected_margin_change_pct": [((new_margin - baseline_margin) * 100) if pd.notna(new_margin) and pd.notna(baseline_margin) else np.nan],
            "baseline_revenue": [baseline_revenue],
            "baseline_gross_profit": [baseline_gp],
            "projected_revenue": [new_revenue],
            "projected_gross_profit": [new_gp],
        }
    )


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=7, task_name="scenario_simulator")
    dirs = ensure_export_dirs()
    step.step("Loading baseline weekly category metrics")
    weekly = _load_baseline_weekly_by_category()
    if weekly.empty:
        log_warn("Scenario simulator baseline unavailable; writing empty output")
        df = pd.DataFrame(columns=["scenario_name", "projected_revenue_change_pct", "projected_gross_profit_change_pct", "projected_margin_change_pct"])
        step.step("Skipping scenario calculations")
        step.step("Writing exports")
        write_table_if_possible(df, "marts", "analysis_scenario_comparison")
        write_csv(df, dirs["pbi"] / "scenario_comparison.csv")
        write_csv(df, dirs["memo"] / "scenario_comparison.csv")
        step.step("Completed")
        return

    step.step("Loading elasticity estimates and attaching category elasticities")
    elas = _load_elasticities_by_category()
    # Missing category elasticities fall back to a conservative default so every category can be simulated.
    weekly = weekly.merge(elas, on="category", how="left")
    weekly["elasticity_b1"] = weekly["elasticity_b1"].fillna(-1.0)
    log_info(f"scenario baseline rows={len(weekly):,}, categories={weekly['category'].nunique()}")

    step.step("Simulating fixed increase scenarios")
    s1 = _simulate_scenario(weekly, 0.03, "plus_3_pct_selected_categories")
    s2 = _simulate_scenario(weekly, 0.05, "plus_5_pct_selected_categories")

    step.step("Simulating tiered elasticity-band scenario")
    tiered_changes = pd.Series(0.0, index=weekly["category"].drop_duplicates().sort_values().tolist())
    elas_cat = weekly.groupby("category", as_index=False)["elasticity_b1"].mean()
    # Tiered strategy applies smaller increases to highly elastic categories and larger increases to less elastic ones.
    for row in elas_cat.itertuples(index=False):
        if row.elasticity_b1 <= -1.4:
            tiered_changes.loc[row.category] = 0.01
        elif row.elasticity_b1 <= -1.0:
            tiered_changes.loc[row.category] = 0.02
        else:
            tiered_changes.loc[row.category] = 0.04
    s3 = _simulate_scenario(weekly, tiered_changes, "tiered_elasticity_bands")

    df = pd.concat([s1, s2, s3], ignore_index=True)

    step.step("Scenario comparison table prepared")
    step.step("Writing exports")
    # Scenario comparison output is consumed by the dashboard executive summary and memo recommendation section.
    write_table_if_possible(df, "marts", "analysis_scenario_comparison")
    write_csv(df, dirs["pbi"] / "scenario_comparison.csv")
    write_csv(df, dirs["memo"] / "scenario_comparison.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
