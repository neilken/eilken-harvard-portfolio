"""Generate Power BI-style dashboard page images from exported analysis data for layout and build guidance."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis._common import load_csv_if_exists
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


BG = "#F7FAFC"
FG = "#1A202C"
ACCENT = "#1F4E79"
ACCENT2 = "#2C7A7B"
ACCENT3 = "#C05621"
GRID = "#E2E8F0"


def _load_exports() -> dict[str, pd.DataFrame]:
    """Load exports."""
    params = load_params()
    p = Path(params["paths"]["exports_for_pbi"])
    return {
        "realization": load_csv_if_exists(p / "price_realization_diagnostics.csv"),
        "margin_erosion": load_csv_if_exists(p / "margin_erosion_by_sku_segment.csv"),
        "waterfall": load_csv_if_exists(p / "price_waterfall_category.csv"),
        "promo": load_csv_if_exists(p / "promo_effectiveness.csv"),
        "promo_reg": load_csv_if_exists(p / "promo_regression_effects.csv"),
        "elasticity": load_csv_if_exists(p / "elasticity_estimates.csv"),
        "forecast": load_csv_if_exists(p / "forecast_12_weeks.csv"),
        "actions": load_csv_if_exists(p / "recommended_actions.csv"),
        "scenario": load_csv_if_exists(p / "scenario_comparison.csv"),
    }


def _init_page(title: str) -> tuple[plt.Figure, np.ndarray]:
    """Handle init page."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), facecolor=BG)
    fig.suptitle(title, fontsize=18, fontweight="bold", color=FG, x=0.02, ha="left")
    for ax in axes.ravel():
        ax.set_facecolor("white")
        ax.grid(True, axis="y", color=GRID, linewidth=0.8)
        for spine in ax.spines.values():
            spine.set_color(GRID)
    return fig, axes


def _save_page(fig: plt.Figure, path: Path) -> None:
    """Handle save page."""
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    log_info(f"Wrote dashboard page image {path.resolve()}")


def _page1_executive(data: dict[str, pd.DataFrame], out_dir: Path) -> None:
    """Handle page1 executive."""
    fig, axes = _init_page("Page 1: Executive Summary")
    ax1, ax2, ax3, ax4 = axes.ravel()

    actions = data["actions"]
    forecast = data["forecast"]
    realization = data["realization"]
    scenario = data["scenario"]

    ax1.axis("off")
    metrics = []
    if not realization.empty:
        metrics.append(("Top10 Leakage", f"${realization.head(10)['leakage_amount'].sum():,.0f}"))
        metrics.append(("Avg Realization %", f"{realization['price_realization_pct'].mean()*100:.1f}%"))
    if not forecast.empty:
        metrics.append(("12W Forecast Avg", f"{forecast['forecast_units'].mean():,.0f}"))
    if not actions.empty:
        metrics.append(("Recommended SKUs", f"{actions['sku'].nunique():,}"))
    if not scenario.empty:
        best = scenario.sort_values("projected_gross_profit_change_pct", ascending=False).head(1)
        if not best.empty:
            metrics.append(("Best GP Scenario", f"{best.iloc[0]['projected_gross_profit_change_pct']:.1f}%"))
    y = 0.95
    for label, value in metrics:
        ax1.text(0.02, y, label, fontsize=11, color="#4A5568", transform=ax1.transAxes)
        ax1.text(0.02, y - 0.10, value, fontsize=20, fontweight="bold", color=FG, transform=ax1.transAxes)
        y -= 0.22

    if not realization.empty:
        top = realization.head(10).sort_values("leakage_amount", ascending=True)
        ax2.barh(top["sku"], top["leakage_amount"], color=ACCENT3)
        ax2.set_title("Top Leakage SKUs", color=FG)
        ax2.tick_params(labelsize=8, colors=FG)
    else:
        ax2.text(0.5, 0.5, "No realization data", ha="center", va="center")

    if not actions.empty and "action_type" in actions.columns:
        counts = actions["action_type"].value_counts().sort_index()
        ax3.bar(counts.index.astype(str), counts.values, color=[ACCENT3, "#718096", ACCENT2][: len(counts)])
        ax3.set_title("Recommended Action Mix", color=FG)
        ax3.tick_params(colors=FG)
    else:
        ax3.text(0.5, 0.5, "No action data", ha="center", va="center")

    if not forecast.empty:
        f = forecast.copy()
        f["forecast_week"] = pd.to_datetime(f["forecast_week"])
        ax4.plot(f["forecast_week"], f["forecast_units"], color=ACCENT2, linewidth=2)
        if {"forecast_low", "forecast_high"}.issubset(f.columns):
            ax4.fill_between(f["forecast_week"], f["forecast_low"], f["forecast_high"], color="#9AE6B4", alpha=0.35)
        ax4.set_title("12-Week Forecast", color=FG)
        ax4.tick_params(axis="x", rotation=30, labelsize=8, colors=FG)
        ax4.tick_params(axis="y", colors=FG)
    else:
        ax4.text(0.5, 0.5, "No forecast data", ha="center", va="center")

    _save_page(fig, out_dir / "page_1_executive_summary.png")


def _page2_realization(data: dict[str, pd.DataFrame], out_dir: Path) -> None:
    """Handle page2 realization."""
    fig, axes = _init_page("Page 2: Price Realization and Leakage")
    ax1, ax2, ax3, ax4 = axes.ravel()
    waterfall = data["waterfall"]
    realization = data["realization"]
    erosion = data["margin_erosion"]

    if not waterfall.empty:
        cat = waterfall.groupby("waterfall_component", as_index=False)["amount"].sum()
        ax1.bar(cat["waterfall_component"], cat["amount"], color=ACCENT)
        ax1.set_title("Category Waterfall Components (Aggregated)", color=FG)
        ax1.tick_params(axis="x", rotation=35, labelsize=8, colors=FG)
        ax1.tick_params(axis="y", colors=FG)
    else:
        ax1.text(0.5, 0.5, "No waterfall data", ha="center", va="center")

    if not realization.empty:
        top = realization.head(15)
        ax2.scatter(top["price_realization_pct"] * 100, top["gross_margin_pct"] * 100, c=top["leakage_amount"], cmap="Blues", s=60)
        ax2.set_title("Price Realization % vs Gross Margin % (Top Leakage SKUs)", color=FG)
        ax2.set_xlabel("Price Realization %")
        ax2.set_ylabel("Gross Margin %")
        ax2.tick_params(colors=FG)
    else:
        ax2.text(0.5, 0.5, "No realization data", ha="center", va="center")

    if not erosion.empty:
        e = erosion.copy()
        e["order_week"] = pd.to_datetime(e["order_week"])
        series = e.groupby("order_week", as_index=False)["gross_margin_pct"].mean()
        ax3.plot(series["order_week"], series["gross_margin_pct"] * 100, color=ACCENT2, linewidth=2)
        ax3.set_title("Average Margin Erosion Trend", color=FG)
        ax3.set_ylabel("Gross Margin %")
        ax3.tick_params(axis="x", rotation=30, labelsize=8, colors=FG)
        ax3.tick_params(axis="y", colors=FG)
    else:
        ax3.text(0.5, 0.5, "No margin erosion data", ha="center", va="center")

    if not realization.empty:
        table = realization.head(10)[["sku", "leakage_amount", "price_realization_pct", "gross_margin_pct"]].copy()
        table["price_realization_pct"] = (table["price_realization_pct"] * 100).round(1)
        table["gross_margin_pct"] = (table["gross_margin_pct"] * 100).round(1)
        ax4.axis("off")
        ax4.set_title("Top Leakage SKU Table (Preview)", color=FG, loc="left")
        tbl = ax4.table(cellText=table.values, colLabels=table.columns, loc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1, 1.2)
    else:
        ax4.text(0.5, 0.5, "No table data", ha="center", va="center")

    _save_page(fig, out_dir / "page_2_realization_leakage.png")


def _page3_promotions(data: dict[str, pd.DataFrame], out_dir: Path) -> None:
    """Handle page3 promotions."""
    fig, axes = _init_page("Page 3: Promotions and Elasticity")
    ax1, ax2, ax3, ax4 = axes.ravel()
    promo = data["promo"]
    promo_reg = data["promo_reg"]
    elas = data["elasticity"]

    if not promo.empty:
        top = promo.sort_values("incremental_gross_profit", ascending=False).head(12)
        colors = [ACCENT2 if x >= 0 else ACCENT3 for x in top["incremental_gross_profit"]]
        ax1.bar(top["promo_id"].astype(str), top["incremental_gross_profit"], color=colors)
        ax1.set_title("Promo Incremental Gross Profit", color=FG)
        ax1.tick_params(axis="x", rotation=40, labelsize=8, colors=FG)
        ax1.tick_params(axis="y", colors=FG)
    else:
        ax1.text(0.5, 0.5, "No promo data", ha="center", va="center")

    if not promo.empty and "promo_unit_lift" in promo.columns:
        top2 = promo.sort_values("promo_unit_lift", ascending=False).head(12)
        ax2.bar(top2["promo_id"].astype(str), top2["promo_unit_lift"], color=ACCENT)
        ax2.set_title("Promo Unit Lift", color=FG)
        ax2.tick_params(axis="x", rotation=40, labelsize=8, colors=FG)
        ax2.tick_params(axis="y", colors=FG)
    else:
        ax2.text(0.5, 0.5, "No promo lift data", ha="center", va="center")

    if not elas.empty:
        use = elas.copy()
        ax3.scatter(use["elasticity_b1"], use["r_squared"], c=np.where(use["grain_type"].astype(str).eq("category"), 1, 2), cmap="viridis", s=80)
        for _, r in use.head(10).iterrows():
            ax3.annotate(str(r["grain"]), (r["elasticity_b1"], r["r_squared"]), fontsize=7)
        ax3.axvline(-1.0, linestyle="--", linewidth=1, color="#718096")
        ax3.set_title("Elasticity vs Fit Quality", color=FG)
        ax3.set_xlabel("Elasticity (b1)")
        ax3.set_ylabel("R-squared")
        ax3.tick_params(colors=FG)
    else:
        ax3.text(0.5, 0.5, "No elasticity data", ha="center", va="center")

    ax4.axis("off")
    ax4.set_title("Promo Regression Effects (Preview)", color=FG, loc="left")
    if not promo_reg.empty:
        t = promo_reg.copy()
        tbl = ax4.table(cellText=t.values, colLabels=t.columns, loc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1, 1.3)
    else:
        ax4.text(0.5, 0.5, "No regression output", ha="center", va="center")

    _save_page(fig, out_dir / "page_3_promotions_elasticity.png")


def _page4_actions(data: dict[str, pd.DataFrame], out_dir: Path) -> None:
    """Handle page4 actions."""
    fig, axes = _init_page("Page 4: Forecast, Scenarios, and Inventory Actions")
    ax1, ax2, ax3, ax4 = axes.ravel()
    forecast = data["forecast"]
    scenario = data["scenario"]
    actions = data["actions"]

    if not forecast.empty:
        f = forecast.copy()
        f["forecast_week"] = pd.to_datetime(f["forecast_week"])
        ax1.plot(f["forecast_week"], f["forecast_units"], color=ACCENT2, linewidth=2)
        ax1.fill_between(f["forecast_week"], f["forecast_low"], f["forecast_high"], color="#9AE6B4", alpha=0.35)
        ax1.set_title("Forecast with Interval", color=FG)
        ax1.tick_params(axis="x", rotation=30, labelsize=8, colors=FG)
        ax1.tick_params(axis="y", colors=FG)
    else:
        ax1.text(0.5, 0.5, "No forecast data", ha="center", va="center")

    if not scenario.empty:
        s = scenario.copy()
        x = np.arange(len(s))
        width = 0.35
        ax2.bar(x - width / 2, s["projected_revenue_change_pct"], width=width, label="Revenue %", color=ACCENT)
        ax2.bar(x + width / 2, s["projected_gross_profit_change_pct"], width=width, label="Gross Profit %", color=ACCENT3)
        ax2.set_xticks(x)
        ax2.set_xticklabels(s["scenario_name"], rotation=20, ha="right", fontsize=8)
        ax2.set_title("Scenario Comparison", color=FG)
        ax2.legend(fontsize=8)
        ax2.tick_params(colors=FG)
    else:
        ax2.text(0.5, 0.5, "No scenario data", ha="center", va="center")

    if not actions.empty and {"days_of_supply", "recommended_pct_change", "action_type"}.issubset(actions.columns):
        a = actions.copy()
        color_map = {"markdown": ACCENT3, "hold": "#718096", "increase": ACCENT2}
        ax3.scatter(
            a["days_of_supply"].fillna(0),
            a["recommended_pct_change"].fillna(0) * 100,
            c=[color_map.get(x, ACCENT) for x in a["action_type"].fillna("hold")],
            s=18,
            alpha=0.7,
        )
        ax3.set_title("Actions by Days of Supply", color=FG)
        ax3.set_xlabel("Days of Supply")
        ax3.set_ylabel("Recommended % Change")
        ax3.tick_params(colors=FG)
    else:
        ax3.text(0.5, 0.5, "No action detail data", ha="center", va="center")

    ax4.axis("off")
    ax4.set_title("Recommendation Table (Preview)", color=FG, loc="left")
    if not actions.empty:
        cols = [c for c in ["sku", "action_type", "recommended_pct_change", "rationale"] if c in actions.columns]
        t = actions[cols].head(12).copy()
        if "recommended_pct_change" in t.columns:
            t["recommended_pct_change"] = (t["recommended_pct_change"] * 100).round(1)
        tbl = ax4.table(cellText=t.values, colLabels=t.columns, loc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(7)
        tbl.scale(1, 1.2)
    else:
        ax4.text(0.5, 0.5, "No recommendations data", ha="center", va="center")

    _save_page(fig, out_dir / "page_4_forecast_inventory_actions.png")


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    out_dir = Path("dashboards/powerbi/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    step = StepLogger(total_steps=6, task_name="generate_powerbi_mock_dashboards")
    step.step("Loading Power BI export datasets")
    data = _load_exports()

    if all(df.empty for df in data.values()):
        log_warn("No export datasets found, dashboard page images were not generated")
        return

    step.step("Generating Page 1 executive summary image")
    _page1_executive(data, out_dir)

    step.step("Generating Page 2 realization and leakage image")
    _page2_realization(data, out_dir)

    step.step("Generating Page 3 promotions and elasticity image")
    _page3_promotions(data, out_dir)

    step.step("Generating Page 4 forecast and inventory actions image")
    _page4_actions(data, out_dir)

    step.step("Completed")


if __name__ == "__main__":
    main()
