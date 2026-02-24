"""Forecast weekly demand with SARIMAX using promo and competitor signals as exogenous inputs."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src.analysis._common import ensure_export_dirs, load_csv_if_exists, load_raw_sales_customers_products_csv, write_csv, write_table_if_possible
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _prepare_weekly_series() -> pd.DataFrame:
    """Prepare weekly series."""
    sales, _, products = load_raw_sales_customers_products_csv()
    if sales.empty:
        return pd.DataFrame()
    # Aggregate to a single weekly demand series for an executive-level forecast view.
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    sales["returned_flag"] = sales.get("returned_flag", False)
    sales["returned_flag"] = sales["returned_flag"].fillna(False).astype(bool)
    # Returns are excluded so forecast targets reflect shipped demand rather than net returns activity.
    sales = sales.loc[~sales["returned_flag"]].copy()
    sales["week_start"] = sales["order_date"] - pd.to_timedelta(sales["order_date"].dt.weekday, unit="D")
    if not products.empty:
        sales = sales.merge(products[["sku", "category"]], on="sku", how="left")
    else:
        sales["category"] = "all"

    # Promo intensity and average price are kept as potential explanatory signals.
    weekly_sales = (
        sales.groupby("week_start", as_index=False)
        .agg(
            units=("units", "sum"),
            promo_intensity_index=("promo_flag", "mean"),
            avg_price=("transaction_price", "mean"),
        )
        .sort_values("week_start")
    )

    params = load_params()
    comp_path = Path(params["paths"]["external_generated"]) / "competitor_snapshots.csv"
    # Competitor promo share is merged as an external exogenous signal when available.
    comp = load_csv_if_exists(comp_path, parse_dates=["captured_at", "snapshot_date"])
    if comp.empty:
        weekly_sales["competitor_promo_share"] = 0.0
    else:
        comp["snapshot_week"] = pd.to_datetime(comp["snapshot_date"]) - pd.to_timedelta(pd.to_datetime(comp["snapshot_date"]).dt.weekday, unit="D")
        comp_week = (
            comp.groupby("snapshot_week", as_index=False)
            .agg(competitor_promo_share=("promo_flag", "mean"))
            .rename(columns={"snapshot_week": "week_start"})
        )
        weekly_sales = weekly_sales.merge(comp_week, on="week_start", how="left")
        weekly_sales["competitor_promo_share"] = weekly_sales["competitor_promo_share"].fillna(0.0)

    weekly_sales["units"] = weekly_sales["units"].astype(float)
    return weekly_sales


def _fit_sarimax_forecast(df: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    """Fit sarimax forecast."""
    df = df.sort_values("week_start").copy()
    # Force weekly frequency so SARIMAX receives a regular time index.
    y = df.set_index("week_start")["units"].asfreq("W-MON")
    exog = df.set_index("week_start")[["promo_intensity_index", "competitor_promo_share"]].asfreq("W-MON").fillna(0.0)

    # Use annual weekly seasonality when enough history exists, otherwise use a shorter fallback season.
    seasonal_period = 52 if len(y.dropna()) >= 104 else 12
    order = (1, 0, 1)
    seasonal_order = (1, 0, 0, seasonal_period)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Warning suppression keeps expected statsmodels convergence and invertibility noise out of pipeline logs.
        model = SARIMAX(
            y,
            exog=exog,
            order=order,
            seasonal_order=seasonal_order,
            trend="c",
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False, maxiter=200)

    future_index = pd.date_range(y.index.max() + pd.Timedelta(days=7), periods=horizon, freq="W-MON")
    # Future exogenous assumptions use a recent average because no future promo calendar is supplied.
    recent_window = min(8, len(exog))
    future_exog = pd.DataFrame(
        {
            "promo_intensity_index": [float(exog["promo_intensity_index"].tail(recent_window).mean())] * horizon,
            "competitor_promo_share": [float(exog["competitor_promo_share"].tail(recent_window).mean())] * horizon,
        },
        index=future_index,
    )
    fc = fit.get_forecast(steps=horizon, exog=future_exog)
    ci = fc.conf_int(alpha=0.05)
    mean = fc.predicted_mean
    col_low = ci.columns[0]
    col_high = ci.columns[1]
    # Clip negative forecasts and bounds because unit demand cannot be negative in this business context.
    out = pd.DataFrame(
        {
            "forecast_week": future_index.date.astype(str),
            "series_name": "category_total",
            "forecast_units": np.maximum(mean.values, 0.0),
            "forecast_low": np.maximum(ci[col_low].values, 0.0),
            "forecast_high": np.maximum(ci[col_high].values, 0.0),
            "model_type": f"SARIMAX{order}x{seasonal_order}",
            "promo_intensity_assumption": float(future_exog["promo_intensity_index"].iloc[0]),
            "competitor_promo_assumption": float(future_exog["competitor_promo_share"].iloc[0]),
        }
    )
    return out


from pathlib import Path


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    step = StepLogger(total_steps=4, task_name="forecasting")
    dirs = ensure_export_dirs()
    step.step("Preparing weekly demand and exogenous inputs")
    weekly = _prepare_weekly_series()
    if weekly.empty:
        log_warn("Forecast inputs unavailable; writing empty forecast output")
        df = pd.DataFrame(columns=["forecast_week", "series_name", "forecast_units", "forecast_low", "forecast_high"])
        step.step("Skipping SARIMAX fit because no weekly series is available")
        step.step("Writing exports")
        write_table_if_possible(df, "marts", "analysis_forecast_12_weeks")
        write_csv(df, dirs["pbi"] / "forecast_12_weeks.csv")
        write_csv(df, dirs["memo"] / "forecast_12_weeks.csv")
        step.step("Completed")
        return

    log_info(f"weekly forecast history rows={len(weekly):,}")
    step.step("Fitting SARIMAX model with promo and competitor exogenous inputs")
    df = _fit_sarimax_forecast(weekly, horizon=12)
    log_info(f"forecast rows={len(df):,}")

    step.step("Writing exports")
    # The same forecast output is exported for dashboard visuals and memo narrative support.
    write_table_if_possible(df, "marts", "analysis_forecast_12_weeks")
    write_csv(df, dirs["pbi"] / "forecast_12_weeks.csv")
    write_csv(df, dirs["memo"] / "forecast_12_weeks.csv")
    step.step("Completed")


if __name__ == "__main__":
    main()
