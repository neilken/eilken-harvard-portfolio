"""Compute additional pricing analyst metrics such as pocket margin proxy, exception rates, dispersion, sell-through, and competitor gap signals."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis._common import ensure_export_dirs, load_csv_if_exists, load_raw_sales_customers_products_csv, write_csv, write_table_if_possible
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _load_base_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load base inputs."""
    params = load_params()
    sales, customers, products = load_raw_sales_customers_products_csv()
    # Shared config keeps path resolution consistent with the rest of the pipeline.
    raw_dir = Path(params["paths"]["raw_generated"])
    ext_dir = Path(params["paths"]["external_generated"])
    inventory = load_csv_if_exists(raw_dir / "inventory_snapshots.csv", parse_dates=["snapshot_date"])
    competitor = load_csv_if_exists(ext_dir / "competitor_snapshots.csv", parse_dates=["captured_at", "snapshot_date"])
    return sales, customers, products, inventory, competitor


def _prepare_sales_panel(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare sales panel."""
    if sales.empty:
        return pd.DataFrame()
    # Build one enriched transaction panel so every metric uses the same cleaned line-level inputs.
    s = sales.copy()
    s["order_date"] = pd.to_datetime(s["order_date"])
    s["returned_flag"] = s.get("returned_flag", False)
    s["returned_flag"] = s["returned_flag"].fillna(False).astype(bool)
    s = s.loc[~s["returned_flag"]].copy()
    s["promo_flag"] = s["promo_flag"].fillna(False).astype(bool)
    s["freight_unit"] = s["freight_unit"].fillna(0.0)
    s["payment_fees_unit"] = s["payment_fees_unit"].fillna(0.0)
    s["order_week"] = s["order_date"] - pd.to_timedelta(s["order_date"].dt.weekday, unit="D")
    s["revenue_line"] = s["transaction_price"] * s["units"]
    s["list_revenue_line"] = s["list_price"] * s["units"]
    s["discount_amount_line"] = s["list_revenue_line"] - s["revenue_line"]
    s["gross_profit_line"] = (s["transaction_price"] - s["cogs_unit"]) * s["units"]
    # Pocket margin proxy removes freight and payment fees from transaction economics.
    s["pocket_revenue_line"] = (s["transaction_price"] - s["freight_unit"] - s["payment_fees_unit"]) * s["units"]
    s["pocket_margin_line"] = (s["transaction_price"] - s["freight_unit"] - s["payment_fees_unit"] - s["cogs_unit"]) * s["units"]

    # Attribute joins add segmentation columns without changing the transaction grain.
    if not customers.empty:
        s = s.merge(customers[["customer_id", "segment", "region", "channel", "price_tier"]], on="customer_id", how="left")
    else:
        s["segment"] = "unknown"
        s["region"] = "unknown"
        s["channel"] = "unknown"
        s["price_tier"] = "B"

    if not products.empty:
        s = s.merge(products[["sku", "category", "product_family", "lifecycle_stage"]], on="sku", how="left")
    else:
        s["category"] = "unknown"
        s["product_family"] = "unknown"
        s["lifecycle_stage"] = "active"

    return s


def _pocket_margin_proxy(sales: pd.DataFrame) -> pd.DataFrame:
    """Handle pocket margin proxy."""
    grp = (
        sales.groupby(["order_week", "sku", "category", "segment", "channel"], as_index=False)
        .agg(
            revenue=("revenue_line", "sum"),
            pocket_revenue=("pocket_revenue_line", "sum"),
            gross_profit=("gross_profit_line", "sum"),
            pocket_margin_value=("pocket_margin_line", "sum"),
            units=("units", "sum"),
        )
    )
    grp["gross_margin_pct"] = grp["gross_profit"] / grp["revenue"].where(grp["revenue"] != 0)
    grp["pocket_margin_pct"] = grp["pocket_margin_value"] / grp["pocket_revenue"].where(grp["pocket_revenue"] != 0)
    grp["pocket_cost_drag_pct_of_revenue"] = (grp["revenue"] - grp["pocket_revenue"]) / grp["revenue"].where(grp["revenue"] != 0)
    return grp


def _price_target_variance(sales: pd.DataFrame) -> pd.DataFrame:
    """Handle price target variance."""
    baseline = (
        sales.loc[~sales["promo_flag"]]
        .groupby(["sku", "channel", "price_tier"], as_index=False)
        .agg(target_transaction_price=("transaction_price", "median"))
    )
    merged = sales.merge(baseline, on=["sku", "channel", "price_tier"], how="left")
    merged["target_transaction_price"] = merged["target_transaction_price"].fillna(merged.groupby("sku")["transaction_price"].transform("median"))
    merged["price_variance_amt"] = merged["transaction_price"] - merged["target_transaction_price"]
    merged["price_variance_pct"] = merged["price_variance_amt"] / merged["target_transaction_price"].where(merged["target_transaction_price"] != 0)
    out = (
        merged.groupby(["order_week", "channel", "price_tier"], as_index=False)
        .agg(
            lines=("order_id", "count"),
            avg_target_price=("target_transaction_price", "mean"),
            avg_actual_price=("transaction_price", "mean"),
            avg_price_variance_amt=("price_variance_amt", "mean"),
            avg_price_variance_pct=("price_variance_pct", "mean"),
            weighted_variance_dollars=("price_variance_amt", lambda s: float((s * merged.loc[s.index, "units"]).sum())),
        )
    )
    return out


def _price_dispersion_by_sku(sales: pd.DataFrame) -> pd.DataFrame:
    """Handle price dispersion by sku."""
    agg = (
        sales.groupby(["sku", "category"], as_index=False)
        .agg(
            txn_count=("transaction_price", "count"),
            avg_transaction_price=("transaction_price", "mean"),
            std_transaction_price=("transaction_price", "std"),
            min_transaction_price=("transaction_price", "min"),
            p10_transaction_price=("transaction_price", lambda s: float(s.quantile(0.10))),
            p50_transaction_price=("transaction_price", lambda s: float(s.quantile(0.50))),
            p90_transaction_price=("transaction_price", lambda s: float(s.quantile(0.90))),
            max_transaction_price=("transaction_price", "max"),
        )
    )
    agg["std_transaction_price"] = agg["std_transaction_price"].fillna(0.0)
    agg["price_cv"] = agg["std_transaction_price"] / agg["avg_transaction_price"].where(agg["avg_transaction_price"] != 0)
    agg["price_spread_pct_p90_p10"] = (agg["p90_transaction_price"] - agg["p10_transaction_price"]) / agg["p50_transaction_price"].where(agg["p50_transaction_price"] != 0)
    return agg.sort_values(["price_cv", "txn_count"], ascending=[False, False])


def _discount_exception_rates(sales: pd.DataFrame, tolerance: float = 0.01) -> pd.DataFrame:
    """Handle discount exception rates."""
    # Expected discount values are policy proxies used to estimate exception rates by tier and promo status.
    expected = {
        ("A", True): 0.18,
        ("A", False): 0.12,
        ("B", True): 0.13,
        ("B", False): 0.07,
        ("C", True): 0.10,
        ("C", False): 0.03,
    }
    s = sales.copy()
    s["expected_discount_pct"] = [
        expected.get((str(t), bool(p)), np.nan) for t, p in zip(s["price_tier"], s["promo_flag"])
    ]
    s["discount_pct_recomputed"] = (s["list_price"] - s["transaction_price"]) / s["list_price"].where(s["list_price"] != 0)
    s["discount_exception_flag"] = (s["discount_pct_recomputed"] - s["expected_discount_pct"]).abs() > tolerance
    out = (
        s.groupby(["order_week", "channel", "segment", "price_tier", "promo_flag"], as_index=False)
        .agg(
            line_count=("order_id", "count"),
            exception_count=("discount_exception_flag", "sum"),
            avg_actual_discount_pct=("discount_pct_recomputed", "mean"),
            avg_expected_discount_pct=("expected_discount_pct", "mean"),
        )
    )
    out["exception_rate"] = out["exception_count"] / out["line_count"].where(out["line_count"] != 0)
    return out


def _promo_roi_and_cannibalization_proxy(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Handle promo roi and cannibalization proxy."""
    s = sales.copy()
    # Normalize missing promo identifiers so promo and non-promo rows can be grouped reliably.
    s["promo_id_norm"] = s["promo_id"].fillna("").replace("", "NO_PROMO")
    sku_channel_nonpromo = (
        s.loc[~s["promo_flag"]]
        .groupby(["sku", "channel"], as_index=False)
        .agg(
            baseline_units=("units", "mean"),
            baseline_gross_profit=("gross_profit_line", "mean"),
            baseline_discount_amount=("discount_amount_line", "mean"),
        )
    )
    promo_rows = s.loc[s["promo_flag"]].merge(sku_channel_nonpromo, on=["sku", "channel"], how="left")
    promo_rows["incremental_units"] = promo_rows["units"] - promo_rows["baseline_units"].fillna(0)
    promo_rows["incremental_gross_profit"] = promo_rows["gross_profit_line"] - promo_rows["baseline_gross_profit"].fillna(0)
    promo_rows["discount_cost"] = promo_rows["discount_amount_line"].clip(lower=0)
    promo_rows["promo_roi_proxy"] = promo_rows["incremental_gross_profit"] / promo_rows["discount_cost"].where(promo_rows["discount_cost"] != 0)

    promo_roi = (
        promo_rows.groupby("promo_id_norm", as_index=False)
        .agg(
            promo_line_count=("order_id", "count"),
            incremental_units=("incremental_units", "sum"),
            incremental_gross_profit=("incremental_gross_profit", "sum"),
            discount_cost=("discount_cost", "sum"),
        )
    )
    promo_roi["promo_roi_proxy"] = promo_roi["incremental_gross_profit"] / promo_roi["discount_cost"].where(promo_roi["discount_cost"] != 0)
    promo_roi = promo_roi.rename(columns={"promo_id_norm": "promo_id"})

    # Category-week rollup is reused as a lightweight cannibalization proxy signal.
    category_week = (
        s.groupby(["category", "order_week"], as_index=False)
        .agg(
            units=("units", "sum"),
            promo_share=("promo_flag", "mean"),
        )
    )
    category_week["baseline_units_4w"] = (
        category_week.sort_values("order_week")
        .groupby("category")["units"]
        .transform(lambda x: x.rolling(4, min_periods=1).mean().shift(1))
    )
    category_week["baseline_units_4w"] = category_week["baseline_units_4w"].fillna(category_week["units"])
    category_week["cannibalization_proxy_index"] = (category_week["units"] - category_week["baseline_units_4w"]) / category_week["baseline_units_4w"].where(category_week["baseline_units_4w"] != 0)
    return promo_roi, category_week


def _inventory_sellthrough_metrics(sales: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Handle inventory sellthrough metrics."""
    if inventory.empty:
        return pd.DataFrame()
    # Align inventory and sales to weekly grain before calculating sell-through and days-of-supply metrics.
    inv = inventory.copy()
    inv["snapshot_date"] = pd.to_datetime(inv["snapshot_date"])
    inv["snapshot_week"] = inv["snapshot_date"] - pd.to_timedelta(inv["snapshot_date"].dt.weekday, unit="D")
    weekly_sales = (
        sales.groupby(["sku", "order_week"], as_index=False)
        .agg(units_sold=("units", "sum"))
        .rename(columns={"order_week": "snapshot_week"})
    )
    merged = inv.merge(weekly_sales, on=["sku", "snapshot_week"], how="left")
    merged["units_sold"] = merged["units_sold"].fillna(0)
    merged["sell_through_rate"] = merged["units_sold"] / (merged["on_hand_units"] + merged["units_sold"]).where((merged["on_hand_units"] + merged["units_sold"]) != 0)
    merged["days_of_supply"] = (merged["on_hand_units"] / merged["units_sold"].where(merged["units_sold"] > 0)) * 7
    merged["dos_bucket"] = pd.cut(
        merged["days_of_supply"],
        bins=[-np.inf, 30, 60, 90, 180, np.inf],
        labels=["0-30", "31-60", "61-90", "91-180", "180+"],
    ).astype(str)
    out = (
        merged.groupby(["snapshot_week", "dos_bucket"], as_index=False)
        .agg(
            sku_count=("sku", "nunique"),
            total_on_hand_units=("on_hand_units", "sum"),
            total_units_sold=("units_sold", "sum"),
            avg_sell_through_rate=("sell_through_rate", "mean"),
        )
    )
    return out


def _competitor_gap_metrics(sales: pd.DataFrame, competitor: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Handle competitor gap metrics."""
    if competitor.empty:
        return pd.DataFrame(), pd.DataFrame()
    # Weekly competitor benchmarks reduce noise from multiple snapshot captures per date.
    comp = competitor.copy()
    comp["snapshot_date"] = pd.to_datetime(comp["snapshot_date"])
    comp["snapshot_week"] = comp["snapshot_date"] - pd.to_timedelta(comp["snapshot_date"].dt.weekday, unit="D")
    comp_week = (
        comp.groupby(["sku", "snapshot_week"], as_index=False)
        .agg(
            competitor_min_price=("competitor_price", "min"),
            competitor_median_price=("competitor_price", "median"),
            competitor_promo_share=("promo_flag", "mean"),
        )
    )
    sales_week = (
        sales.groupby(["sku", "order_week"], as_index=False)
        .agg(
            avg_transaction_price=("transaction_price", "mean"),
            units=("units", "sum"),
        )
        .rename(columns={"order_week": "snapshot_week"})
    )
    merged = sales_week.merge(comp_week, on=["sku", "snapshot_week"], how="inner")
    if merged.empty:
        return pd.DataFrame(), pd.DataFrame()
    merged["price_index_vs_comp_min"] = merged["avg_transaction_price"] / merged["competitor_min_price"].where(merged["competitor_min_price"] != 0)
    merged["price_gap_pct_vs_comp_min"] = (merged["avg_transaction_price"] - merged["competitor_min_price"]) / merged["competitor_min_price"].where(merged["competitor_min_price"] != 0)
    merged["price_index_band"] = pd.cut(
        merged["price_index_vs_comp_min"],
        bins=[-np.inf, 0.90, 0.95, 1.00, 1.05, 1.10, np.inf],
        labels=["<0.90", "0.90-0.95", "0.95-1.00", "1.00-1.05", "1.05-1.10", ">1.10"],
    ).astype(str)

    gap_dist = (
        merged.groupby("price_index_band", as_index=False)
        .agg(
            sku_week_count=("sku", "count"),
            avg_units=("units", "mean"),
            avg_price_gap_pct=("price_gap_pct_vs_comp_min", "mean"),
        )
    )

    merged = merged.sort_values(["sku", "snapshot_week"])
    merged["prior_units"] = merged.groupby("sku")["units"].shift(1)
    merged["units_growth_pct"] = (merged["units"] - merged["prior_units"]) / merged["prior_units"].where(merged["prior_units"] != 0)
    win_loss_proxy = (
        merged.groupby("price_index_band", as_index=False)
        .agg(
            observations=("sku", "count"),
            avg_units_growth_pct=("units_growth_pct", "mean"),
            median_units_growth_pct=("units_growth_pct", "median"),
            avg_competitor_promo_share=("competitor_promo_share", "mean"),
        )
    )
    return gap_dist, win_loss_proxy


def _write_metric_output(df: pd.DataFrame, table: str, pbi_name: str, memo_name: str, dirs: dict[str, Path]) -> None:
    """Write metric output."""
    if df.empty:
        log_warn(f"Skipping {table} because no rows were produced")
        return
    # Mirrored table and CSV outputs keep Power BI imports and Postgres-backed workflows aligned.
    write_table_if_possible(df, "marts", table)
    write_csv(df, dirs["pbi"] / pbi_name)
    write_csv(df, dirs["memo"] / memo_name)


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=6, task_name="advanced_pricing_metrics")
    dirs = ensure_export_dirs()

    step.step("Loading generated/raw datasets")
    sales, customers, products, inventory, competitor = _load_base_inputs()
    if sales.empty:
        log_warn("Sales data unavailable; advanced pricing metrics were not generated")
        return

    step.step("Preparing enriched sales panel")
    sales_panel = _prepare_sales_panel(sales, customers, products)
    log_info(f"advanced sales panel rows={len(sales_panel):,}")

    step.step("Computing pricing, promo, inventory, and competitor metrics")
    # Each metric function returns a report-ready table at a stable grain for dashboard import.
    pocket_margin = _pocket_margin_proxy(sales_panel)
    price_target_var = _price_target_variance(sales_panel)
    price_dispersion = _price_dispersion_by_sku(sales_panel)
    discount_exceptions = _discount_exception_rates(sales_panel)
    promo_roi, cannibalization_proxy = _promo_roi_and_cannibalization_proxy(sales_panel)
    inventory_sellthrough = _inventory_sellthrough_metrics(sales_panel, inventory)
    gap_dist, win_loss_proxy = _competitor_gap_metrics(sales_panel, competitor)

    step.step("Writing metric outputs to Postgres and CSV")
    # Output names are intentionally paired to simplify traceability between tables and CSV files.
    _write_metric_output(
        pocket_margin,
        "analysis_pocket_margin_proxy",
        "pocket_margin_proxy.csv",
        "pocket_margin_proxy.csv",
        dirs,
    )
    _write_metric_output(
        price_target_var,
        "analysis_price_variance_vs_target",
        "price_variance_vs_target.csv",
        "price_variance_vs_target.csv",
        dirs,
    )
    _write_metric_output(
        price_dispersion,
        "analysis_price_dispersion_by_sku",
        "price_dispersion_by_sku.csv",
        "price_dispersion_by_sku.csv",
        dirs,
    )
    _write_metric_output(
        discount_exceptions,
        "analysis_discount_exception_rates",
        "discount_exception_rates.csv",
        "discount_exception_rates.csv",
        dirs,
    )
    _write_metric_output(
        promo_roi,
        "analysis_promo_roi_summary",
        "promo_roi_summary.csv",
        "promo_roi_summary.csv",
        dirs,
    )
    _write_metric_output(
        cannibalization_proxy,
        "analysis_cannibalization_proxy",
        "cannibalization_proxy.csv",
        "cannibalization_proxy.csv",
        dirs,
    )
    _write_metric_output(
        inventory_sellthrough,
        "analysis_inventory_sellthrough",
        "inventory_sellthrough_metrics.csv",
        "inventory_sellthrough_metrics.csv",
        dirs,
    )
    _write_metric_output(
        gap_dist,
        "analysis_competitor_gap_distribution",
        "competitor_gap_distribution.csv",
        "competitor_gap_distribution.csv",
        dirs,
    )
    _write_metric_output(
        win_loss_proxy,
        "analysis_win_loss_proxy",
        "win_loss_proxy.csv",
        "win_loss_proxy.csv",
        dirs,
    )

    step.step("Summary")
    produced = {
        "pocket_margin_proxy": len(pocket_margin),
        "price_variance_vs_target": len(price_target_var),
        "price_dispersion_by_sku": len(price_dispersion),
        "discount_exception_rates": len(discount_exceptions),
        "promo_roi_summary": len(promo_roi),
        "cannibalization_proxy": len(cannibalization_proxy),
        "inventory_sellthrough": len(inventory_sellthrough),
        "competitor_gap_distribution": len(gap_dist),
        "win_loss_proxy": len(win_loss_proxy),
    }
    log_info("Rows produced by advanced metrics: " + ", ".join(f"{k}={v:,}" for k, v in produced.items()))


if __name__ == "__main__":
    main()
