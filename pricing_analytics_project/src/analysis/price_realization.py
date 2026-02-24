"""Compute price realization diagnostics, margin erosion summaries, and category waterfall outputs for pricing review."""

from __future__ import annotations

import pandas as pd

from src.analysis._common import (
    ensure_export_dirs,
    load_raw_sales_customers_products_csv,
    placeholder_or_db,
    write_csv,
    write_table_if_possible,
)
from src.utils.logging import StepLogger, log_info, log_warn


def _build_diagnostics_from_csv() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build diagnostics from csv."""
    sales, customers, products = load_raw_sales_customers_products_csv()
    if sales.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Normalize line-level economics first so all downstream summaries share the same definitions.
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    sales["revenue_line"] = sales["transaction_price"] * sales["units"]
    sales["list_revenue_line"] = sales["list_price"] * sales["units"]
    sales["discount_amount_line"] = sales["list_revenue_line"] - sales["revenue_line"]
    sales["gross_profit_line"] = (sales["transaction_price"] - sales["cogs_unit"]) * sales["units"]
    sales["contribution_profit_line"] = (
        (sales["transaction_price"] - sales["cogs_unit"] - sales["freight_unit"].fillna(0) - sales["payment_fees_unit"].fillna(0))
        * sales["units"]
    )
    sales["order_week"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")

    # Join dimension attributes for segmentation used in leakage, erosion, and waterfall outputs.
    if not products.empty:
        sales = sales.merge(products[["sku", "category", "product_family"]], on="sku", how="left")
    else:
        sales["category"] = "unknown"
        sales["product_family"] = "unknown"
    if not customers.empty:
        sales = sales.merge(customers[["customer_id", "segment", "channel"]], on="customer_id", how="left")
    else:
        sales["segment"] = "unknown"
        sales["channel"] = "unknown"

    # Returns are excluded from pricing diagnostics to avoid reversing realized price and margin signals.
    sales_clean = sales.loc[~sales["returned_flag"]].copy()

    # Leakage output is intentionally limited to top SKUs by leakage dollars for dashboard readability.
    leakage = (
        sales_clean.groupby("sku", as_index=False)
        .agg(
            list_revenue=("list_revenue_line", "sum"),
            revenue=("revenue_line", "sum"),
            discount_amount=("discount_amount_line", "sum"),
            gross_profit=("gross_profit_line", "sum"),
        )
    )
    leakage["price_realization_pct"] = leakage["revenue"] / leakage["list_revenue"].where(leakage["list_revenue"] != 0)
    leakage["gross_margin_pct"] = leakage["gross_profit"] / leakage["revenue"].where(leakage["revenue"] != 0)
    leakage["leakage_amount"] = leakage["discount_amount"]
    leakage = leakage.sort_values("leakage_amount", ascending=False).head(100)

    # Weekly SKU x segment grain supports trend analysis without over-aggregating segment effects.
    margin_erosion = (
        sales_clean.groupby(["order_week", "sku", "segment"], as_index=False)
        .agg(
            revenue=("revenue_line", "sum"),
            gross_profit=("gross_profit_line", "sum"),
            contribution_profit=("contribution_profit_line", "sum"),
        )
    )
    margin_erosion["gross_margin_pct"] = margin_erosion["gross_profit"] / margin_erosion["revenue"].where(margin_erosion["revenue"] != 0)
    margin_erosion["contribution_margin_pct"] = margin_erosion["contribution_profit"] / margin_erosion["revenue"].where(margin_erosion["revenue"] != 0)

    # Category waterfall components are built from a rollup, then reshaped into a long plotting format.
    category_rollup = (
        sales_clean.groupby("category", as_index=False)
        .agg(
            list_revenue=("list_revenue_line", "sum"),
            net_revenue=("revenue_line", "sum"),
            cogs=("cogs_unit", lambda s: float((s * sales_clean.loc[s.index, "units"]).sum())),
            freight=("freight_unit", lambda s: float((s.fillna(0) * sales_clean.loc[s.index, "units"]).sum())),
            fees=("payment_fees_unit", lambda s: float((s.fillna(0) * sales_clean.loc[s.index, "units"]).sum())),
        )
    )
    category_rollup["discount_amount"] = category_rollup["list_revenue"] - category_rollup["net_revenue"]
    category_rollup["gross_profit"] = category_rollup["net_revenue"] - category_rollup["cogs"]
    category_rollup["contribution_profit"] = category_rollup["net_revenue"] - category_rollup["cogs"] - category_rollup["freight"] - category_rollup["fees"]

    waterfall = category_rollup.melt(
        id_vars=["category"],
        value_vars=[
            "list_revenue",
            "discount_amount",
            "net_revenue",
            "cogs",
            "freight",
            "fees",
            "gross_profit",
            "contribution_profit",
        ],
        var_name="waterfall_component",
        value_name="amount",
    )
    return leakage, margin_erosion, waterfall


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=4, task_name="price_realization")
    dirs = ensure_export_dirs()
    step.step("Preparing price realization diagnostics from generated data")
    leakage, margin_erosion, waterfall = _build_diagnostics_from_csv()

    if leakage.empty:
        log_warn("Generated CSV inputs unavailable, using database fallback placeholder")
        # Placeholder rows keep downstream exports and memo automation from failing on empty inputs.
        placeholder = pd.DataFrame(
            {"sku": ["SKU00001"], "leakage_amount": [0.0], "price_realization_pct": [1.0], "gross_margin_pct": [0.0]}
        )
        leakage = placeholder_or_db(
            "select sku, sum((list_price - transaction_price) * units) as leakage_amount, "
            "sum(transaction_price * units) / nullif(sum(list_price * units),0) as price_realization_pct, "
            "sum((transaction_price-cogs_unit)*units) / nullif(sum(transaction_price*units),0) as gross_margin_pct "
            "from raw.sales_order_lines where coalesce(returned_flag,false)=false "
            "group by sku order by leakage_amount desc limit 100",
            placeholder,
            step,
            "price realization leakage fallback",
        )
        margin_erosion = pd.DataFrame()
        waterfall = pd.DataFrame()
    else:
        log_info(f"leakage rows={len(leakage):,}, margin_erosion rows={len(margin_erosion):,}, waterfall rows={len(waterfall):,}")
        step.step("Prepared leakage ranking, margin erosion, and price waterfall tables")

    step.step("Writing exports")
    # Each dataset is written to both CSV exports and Postgres tables for Power BI and memo workflows.
    write_table_if_possible(leakage, "marts", "analysis_price_realization_diagnostics")
    write_csv(leakage, dirs["pbi"] / "price_realization_diagnostics.csv")
    write_csv(leakage, dirs["memo"] / "price_realization_top_leakage.csv")
    if not margin_erosion.empty:
        write_table_if_possible(margin_erosion, "marts", "analysis_margin_erosion_by_sku_segment")
        write_csv(margin_erosion, dirs["pbi"] / "margin_erosion_by_sku_segment.csv")
        write_csv(margin_erosion, dirs["memo"] / "margin_erosion_by_sku_segment.csv")
    if not waterfall.empty:
        write_table_if_possible(waterfall, "marts", "analysis_price_waterfall_category")
        write_csv(waterfall, dirs["pbi"] / "price_waterfall_category.csv")
        write_csv(waterfall, dirs["memo"] / "price_waterfall_category.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
