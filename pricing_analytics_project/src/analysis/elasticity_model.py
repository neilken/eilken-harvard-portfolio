"""Estimate price elasticity from weekly aggregated demand and price data using log-log regression models."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.analysis._common import ensure_export_dirs, load_raw_sales_customers_products_csv, write_csv, write_table_if_possible
from src.utils.logging import StepLogger, log_info, log_warn


def _prepare_weekly_family_panel() -> pd.DataFrame:
    """Prepare weekly family panel."""
    sales, customers, products = load_raw_sales_customers_products_csv()
    if sales.empty or products.empty:
        return pd.DataFrame()

    # Build a weekly category and product-family panel because elasticity is estimated on aggregated demand.
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    # Returns are excluded so negative demand effects do not distort log-log elasticity estimates.
    sales = sales.loc[~sales["returned_flag"]].copy()
    sales = sales.merge(products[["sku", "category", "product_family"]], on="sku", how="left")
    if not customers.empty and "customer_id" in sales.columns:
        sales = sales.merge(customers[["customer_id", "channel"]], on="customer_id", how="left")
    else:
        sales["channel"] = "unknown"
    sales["week_start"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")

    # Weekly aggregation reduces transaction noise and creates a stable time-series modeling grain.
    panel = (
        sales.groupby(["category", "product_family", "week_start"], as_index=False)
        .agg(
            units=("units", "sum"),
            avg_price=("transaction_price", "mean"),
            promo_share=("promo_flag", "mean"),
            unique_skus=("sku", "nunique"),
        )
    )
    # Positive filters are required because the model uses log(units) and log(price).
    panel = panel.loc[(panel["units"] > 0) & (panel["avg_price"] > 0)].copy()
    # Seasonal terms capture recurring within-year demand patterns without overfitting many dummy variables.
    panel["week_of_year"] = pd.to_datetime(panel["week_start"]).dt.isocalendar().week.astype(int)
    panel["sin_woy"] = np.sin(2 * np.pi * panel["week_of_year"] / 52.0)
    panel["cos_woy"] = np.cos(2 * np.pi * panel["week_of_year"] / 52.0)
    panel["log_units"] = np.log(panel["units"])
    panel["log_price"] = np.log(panel["avg_price"])
    return panel


def _fit_group_elasticity(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Fit group elasticity."""
    results: list[dict] = []
    for grain_value, g in df.groupby(group_col):
        # Minimum data thresholds avoid unstable elasticity estimates on sparse groups.
        if len(g) < 30 or g["log_price"].nunique() < 8:
            continue
        # Control variables isolate the price coefficient from promo intensity and seasonality effects.
        X = sm.add_constant(g[["log_price", "promo_share", "sin_woy", "cos_woy"]].astype(float), has_constant="add")
        y = g["log_units"].astype(float)
        model = sm.OLS(y, X).fit()
        if "log_price" not in model.params.index:
            continue
        ci = model.conf_int().loc["log_price"]
        # The log_price coefficient is the elasticity estimate in a log-log demand model.
        results.append(
            {
                "grain_type": group_col,
                "grain": grain_value,
                "elasticity_b1": float(model.params["log_price"]),
                "ci_low": float(ci.iloc[0]),
                "ci_high": float(ci.iloc[1]),
                "promo_share_coef": float(model.params.get("promo_share", np.nan)),
                "n_obs": int(model.nobs),
                "r_squared": float(model.rsquared),
                "preprocessing_rule": "weekly aggregate; units>0 and price>0",
            }
        )
    return pd.DataFrame(results)


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=5, task_name="elasticity_model")
    dirs = ensure_export_dirs()
    step.step("Preparing weekly aggregate panel from generated/raw data")
    panel = _prepare_weekly_family_panel()
    if panel.empty:
        log_warn("Elasticity model input unavailable; writing empty output schema")
        df = pd.DataFrame(
            columns=[
                "grain_type", "grain", "elasticity_b1", "ci_low", "ci_high",
                "promo_share_coef", "n_obs", "r_squared", "preprocessing_rule"
            ]
        )
        step.step("Skipping model fit because no panel rows are available")
        step.step("Writing exports")
        write_table_if_possible(df, "marts", "analysis_elasticity_estimates")
        write_csv(df, dirs["pbi"] / "elasticity_estimates.csv")
        write_csv(df, dirs["memo"] / "elasticity_estimates.csv")
        step.step("Completed")
        return

    log_info(f"elasticity panel rows={len(panel):,}")
    step.step("Fitting category-level elasticity models")
    category_results = _fit_group_elasticity(panel, "category")
    log_info(f"category elasticity rows={len(category_results):,}")

    step.step("Fitting product_family-level elasticity models")
    family_results = _fit_group_elasticity(panel, "product_family")
    log_info(f"product_family elasticity rows={len(family_results):,}")

    df = pd.concat([category_results, family_results], ignore_index=True).sort_values(
        ["grain_type", "grain"], kind="stable"
    ) if (not category_results.empty or not family_results.empty) else pd.DataFrame()
    log_info("Log-log specification uses weekly aggregation with positive unit and price filters")

    step.step("Writing exports")
    # Output is shared by Power BI, memo figures, and scenario simulation modules.
    write_table_if_possible(df, "marts", "analysis_elasticity_estimates")
    write_csv(df, dirs["pbi"] / "elasticity_estimates.csv")
    write_csv(df, dirs["memo"] / "elasticity_estimates.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
