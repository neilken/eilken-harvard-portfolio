"""Create lightweight memo figures from analysis exports for portfolio documentation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.analysis._common import ensure_export_dirs, load_csv_if_exists
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _save_fig(path: Path) -> None:
    """Handle save fig."""
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log_info(f"Wrote figure {path.resolve()}")


def _plot_top_leakage(memo_dir: Path, figures_dir: Path) -> bool:
    """Handle plot top leakage."""
    df = load_csv_if_exists(memo_dir / "price_realization_top_leakage.csv")
    if df.empty or "sku" not in df.columns:
        return False
    top = df.head(15).copy()
    top = top.sort_values("leakage_amount", ascending=True)
    plt.figure(figsize=(10, 6))
    plt.barh(top["sku"], top["leakage_amount"], color="#b44d3a")
    plt.title("Top Discount Leakage SKUs")
    plt.xlabel("Leakage Amount")
    plt.ylabel("SKU")
    _save_fig(figures_dir / "top_discount_leakage_skus.png")
    return True


def _plot_promo_leaderboard(memo_dir: Path, figures_dir: Path) -> bool:
    """Handle plot promo leaderboard."""
    df = load_csv_if_exists(memo_dir / "promo_effectiveness_summary.csv")
    if df.empty or "promo_id" not in df.columns:
        return False
    top = df.sort_values("incremental_gross_profit", ascending=False).head(12).copy()
    colors = ["#2c7a7b" if x >= 0 else "#c05621" for x in top["incremental_gross_profit"]]
    plt.figure(figsize=(10, 6))
    plt.bar(top["promo_id"].astype(str), top["incremental_gross_profit"], color=colors)
    plt.title("Promo Incremental Gross Profit")
    plt.xlabel("Promo ID")
    plt.ylabel("Incremental Gross Profit")
    plt.xticks(rotation=45, ha="right")
    _save_fig(figures_dir / "promo_incremental_gross_profit.png")
    return True


def _plot_elasticity_estimates(memo_dir: Path, figures_dir: Path) -> bool:
    """Handle plot elasticity estimates."""
    df = load_csv_if_exists(memo_dir / "elasticity_estimates.csv")
    if df.empty or "elasticity_b1" not in df.columns:
        return False
    use = df.loc[df.get("grain_type", "").astype(str).eq("category")] if "grain_type" in df.columns else df.copy()
    if use.empty:
        use = df.copy()
    use = use.sort_values("elasticity_b1")
    plt.figure(figsize=(10, 6))
    plt.errorbar(
        use["grain"].astype(str),
        use["elasticity_b1"],
        yerr=[
            (use["elasticity_b1"] - use["ci_low"]).clip(lower=0),
            (use["ci_high"] - use["elasticity_b1"]).clip(lower=0),
        ],
        fmt="o",
        color="#1f4e79",
        ecolor="#7aa6c2",
        capsize=4,
    )
    plt.axhline(-1.0, color="#666666", linestyle="--", linewidth=1)
    plt.title("Elasticity Estimates with Confidence Intervals")
    plt.xlabel("Grain")
    plt.ylabel("Elasticity (b1)")
    plt.xticks(rotation=30, ha="right")
    _save_fig(figures_dir / "elasticity_estimates_ci.png")
    return True


def _plot_forecast(memo_dir: Path, figures_dir: Path) -> bool:
    """Handle plot forecast."""
    df = load_csv_if_exists(memo_dir / "forecast_12_weeks.csv")
    if df.empty or "forecast_week" not in df.columns:
        return False
    df = df.copy()
    df["forecast_week"] = pd.to_datetime(df["forecast_week"])
    plt.figure(figsize=(10, 6))
    plt.plot(df["forecast_week"], df["forecast_units"], color="#2f855a", linewidth=2, label="Forecast")
    if {"forecast_low", "forecast_high"}.issubset(df.columns):
        plt.fill_between(df["forecast_week"], df["forecast_low"], df["forecast_high"], color="#9ae6b4", alpha=0.35, label="95% interval")
    plt.title("12-Week Demand Forecast")
    plt.xlabel("Forecast Week")
    plt.ylabel("Units")
    plt.legend()
    _save_fig(figures_dir / "forecast_12_weeks.png")
    return True


def _plot_recommendations(memo_dir: Path, figures_dir: Path) -> bool:
    """Handle plot recommendations."""
    df = load_csv_if_exists(memo_dir / "recommended_actions.csv")
    if df.empty or "action_type" not in df.columns:
        return False
    counts = df["action_type"].fillna("unknown").value_counts().sort_index()
    plt.figure(figsize=(8, 5))
    plt.bar(counts.index.astype(str), counts.values, color=["#c05621", "#4a5568", "#2b6cb0"][: len(counts)])
    plt.title("Recommended Pricing Actions")
    plt.xlabel("Action Type")
    plt.ylabel("Count of SKUs")
    _save_fig(figures_dir / "recommended_actions_counts.png")
    return True


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    dirs = ensure_export_dirs()
    memo_exports_dir = Path(params["paths"]["exports_for_memo"])
    figures_dir = Path(params["paths"]["memo_figures"])
    figures_dir.mkdir(parents=True, exist_ok=True)

    step = StepLogger(total_steps=7, task_name="generate_memo_figures")
    step.step("Loading memo export files")

    generated = 0
    step.step("Creating top discount leakage figure")
    generated += int(_plot_top_leakage(memo_exports_dir, figures_dir))

    step.step("Creating promo performance figure")
    generated += int(_plot_promo_leaderboard(memo_exports_dir, figures_dir))

    step.step("Creating elasticity figure")
    generated += int(_plot_elasticity_estimates(memo_exports_dir, figures_dir))

    step.step("Creating forecast figure")
    generated += int(_plot_forecast(memo_exports_dir, figures_dir))

    step.step("Creating recommendation action mix figure")
    generated += int(_plot_recommendations(memo_exports_dir, figures_dir))

    step.step("Summary")
    if generated == 0:
        log_warn("No figures generated because memo export inputs were missing")
    else:
        log_info(f"Generated figures count={generated}")


if __name__ == "__main__":
    main()
