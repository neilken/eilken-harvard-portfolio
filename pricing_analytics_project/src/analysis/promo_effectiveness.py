"""Estimate promotion performance with quasi A/B summaries and regression-adjusted promo effects."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.analysis._common import (
    ensure_export_dirs,
    load_raw_sales_customers_products_csv,
    placeholder_or_db,
    write_csv,
    write_table_if_possible,
)
from src.utils.logging import StepLogger, log_info, log_warn


def _prepare_weekly_panel() -> pd.DataFrame:
    """Prepare weekly panel."""
    sales, customers, products = load_raw_sales_customers_products_csv()
    if sales.empty:
        return pd.DataFrame()

    # Weekly SKU x channel x category grain preserves promotional variation while reducing transaction noise.
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["promo_flag"] = sales["promo_flag"].fillna(False).astype(bool)
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    # Returns are excluded so promo lift metrics reflect demand generation, not reverse logistics.
    sales = sales.loc[~sales["returned_flag"]].copy()
    sales["gross_profit_line"] = (sales["transaction_price"] - sales["cogs_unit"]) * sales["units"]
    sales["week_start"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")

    if not customers.empty:
        sales = sales.merge(customers[["customer_id", "channel"]], on="customer_id", how="left")
    else:
        sales["channel"] = "unknown"
    if not products.empty:
        sales = sales.merge(products[["sku", "category"]], on="sku", how="left")
    else:
        sales["category"] = "unknown"

    # Revenue is recomputed as a weighted line sum to avoid averaging prices before multiplying by units.
    weekly = (
        sales.groupby(["sku", "channel", "category", "week_start"], as_index=False)
        .agg(
            units=("units", "sum"),
            revenue=("transaction_price", lambda s: float((s * sales.loc[s.index, "units"]).sum())),
            gross_profit=("gross_profit_line", "sum"),
            avg_price=("transaction_price", "mean"),
            avg_discount_pct=("discount_pct", "mean"),
            promo_flag=("promo_flag", "max"),
            promo_id=("promo_id", lambda s: next((x for x in s if isinstance(x, str) and x), "")),
        )
    )
    # Seasonal features and log transforms support the pooled regression model.
    weekly["week_of_year"] = pd.to_datetime(weekly["week_start"]).dt.isocalendar().week.astype(int)
    weekly["sin_woy"] = np.sin(2 * np.pi * weekly["week_of_year"] / 52.0)
    weekly["cos_woy"] = np.cos(2 * np.pi * weekly["week_of_year"] / 52.0)
    weekly["log_units_plus1"] = np.log1p(weekly["units"].clip(lower=0))
    weekly["log_avg_price"] = np.log(weekly["avg_price"].clip(lower=0.01))
    weekly["promo_flag_int"] = weekly["promo_flag"].astype(int)
    return weekly


def _quasi_ab_metrics(weekly: pd.DataFrame) -> pd.DataFrame:
    """Handle quasi ab metrics."""
    keys = ["sku", "channel"]
    # Non-promo weeks provide a simple baseline for a quasi A/B style promo comparison.
    baseline = (
        weekly.loc[~weekly["promo_flag"]]
        .groupby(keys, as_index=False)
        .agg(
            baseline_units=("units", "mean"),
            baseline_gross_profit=("gross_profit", "mean"),
        )
    )
    promo_weeks = weekly.loc[weekly["promo_flag"]].merge(baseline, on=keys, how="left")
    if promo_weeks.empty:
        return pd.DataFrame(columns=["promo_id", "promo_unit_lift", "incremental_gross_profit"])
    # Lift is computed versus the SKU x channel baseline, then summarized by promo id.
    promo_weeks["promo_unit_lift"] = promo_weeks["units"] - promo_weeks["baseline_units"].fillna(0)
    promo_weeks["incremental_gross_profit"] = promo_weeks["gross_profit"] - promo_weeks["baseline_gross_profit"].fillna(0)
    out = (
        promo_weeks.groupby("promo_id", as_index=False)
        .agg(
            promo_weeks=("promo_id", "count"),
            promo_unit_lift=("promo_unit_lift", "mean"),
            incremental_gross_profit=("incremental_gross_profit", "sum"),
        )
        .sort_values("incremental_gross_profit", ascending=False)
    )
    return out


def _regression_adjusted_effects(weekly: pd.DataFrame) -> pd.DataFrame:
    """Handle regression adjusted effects."""
    if weekly.empty:
        return pd.DataFrame()
    # Pooled category x channel x week panel reduces sparsity and supports controlled promo effect estimation.
    pooled = (
        weekly.groupby(["category", "channel", "week_start"], as_index=False)
        .agg(
            units=("units", "sum"),
            gross_profit=("gross_profit", "sum"),
            revenue=("revenue", "sum"),
            avg_price=("avg_price", "mean"),
            promo_share=("promo_flag_int", "mean"),
            avg_discount_pct=("avg_discount_pct", "mean"),
            sin_woy=("sin_woy", "mean"),
            cos_woy=("cos_woy", "mean"),
        )
    )
    pooled["log_units_plus1"] = np.log1p(pooled["units"].clip(lower=0))
    pooled["log_avg_price"] = np.log(pooled["avg_price"].clip(lower=0.01))
    # Category and channel dummies control for structural mix differences across the portfolio.
    dummies = pd.get_dummies(pooled[["category", "channel"]], drop_first=True, dtype=float)
    X = pd.concat(
        [
            pooled[["promo_share", "log_avg_price", "avg_discount_pct", "sin_woy", "cos_woy"]].astype(float),
            dummies,
        ],
        axis=1,
    )
    X = sm.add_constant(X, has_constant="add")
    y_units = pooled["log_units_plus1"].astype(float)
    y_gp = pooled["gross_profit"].astype(float)
    # Separate regressions quantify promo share impact on demand and gross profit.
    model_units = sm.OLS(y_units, X).fit()
    model_gp = sm.OLS(y_gp, X).fit()
    ci_units = model_units.conf_int().loc["promo_share"].tolist() if "promo_share" in model_units.params.index else [np.nan, np.nan]
    ci_gp = model_gp.conf_int().loc["promo_share"].tolist() if "promo_share" in model_gp.params.index else [np.nan, np.nan]
    return pd.DataFrame(
        {
            "metric": ["log_units_plus1", "gross_profit"],
            "promo_share_coef": [
                float(model_units.params.get("promo_share", np.nan)),
                float(model_gp.params.get("promo_share", np.nan)),
            ],
            "ci_low": [float(ci_units[0]), float(ci_gp[0])],
            "ci_high": [float(ci_units[1]), float(ci_gp[1])],
            "n_obs": [int(model_units.nobs), int(model_gp.nobs)],
            "r_squared": [float(model_units.rsquared), float(model_gp.rsquared)],
        }
    )


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=5, task_name="promo_effectiveness")
    dirs = ensure_export_dirs()
    step.step("Preparing weekly promo analysis panel")
    weekly = _prepare_weekly_panel()
    if weekly.empty:
        log_warn("Generated CSV inputs not available, database fallback placeholder will be used")
        placeholder = pd.DataFrame(
            {"promo_id": ["PROMO_PLACEHOLDER"], "promo_weeks": [1], "promo_unit_lift": [0.0], "incremental_gross_profit": [0.0]}
        )
        leaderboard = placeholder_or_db(
            "select coalesce(nullif(promo_id,''),'NO_PROMO') as promo_id, count(*) as promo_weeks, "
            "avg(units) as promo_unit_lift, sum((transaction_price - cogs_unit) * units) as incremental_gross_profit "
            "from raw.sales_order_lines where promo_flag is true group by 1",
            placeholder,
            step,
            "promo leaderboard fallback",
        )
        reg_effects = pd.DataFrame()
    else:
        log_info(f"weekly promo panel rows={len(weekly):,}")
        step.step("Computing quasi A/B promo lift metrics")
        leaderboard = _quasi_ab_metrics(weekly)
        log_info(f"promo leaderboard rows={len(leaderboard):,}")

        step.step("Estimating regression-adjusted promo effects with controls")
        reg_effects = _regression_adjusted_effects(weekly)
        log_info(f"regression effect rows={len(reg_effects):,}")

    step.step("Writing exports")
    # Leaderboard and regression outputs are exported separately because they support different visuals.
    write_table_if_possible(leaderboard, "marts", "analysis_promo_effectiveness")
    write_csv(leaderboard, dirs["pbi"] / "promo_effectiveness.csv")
    write_csv(leaderboard, dirs["memo"] / "promo_effectiveness_summary.csv")
    if not reg_effects.empty:
        write_table_if_possible(reg_effects, "marts", "analysis_promo_regression_effects")
        write_csv(reg_effects, dirs["memo"] / "promo_regression_effects.csv")
        write_csv(reg_effects, dirs["pbi"] / "promo_regression_effects.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
