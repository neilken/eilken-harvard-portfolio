"""Generate a quantified memo summary markdown file from current analysis outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis._common import load_csv_if_exists
from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info, log_warn


def _fmt_money(value: float) -> str:
    """Handle fmt money."""
    return f"${value:,.0f}"


def _fmt_pct(value: float) -> str:
    """Handle fmt pct."""
    return f"{value:.2f}%"


def _top_leakage_section(memo_exports: Path) -> tuple[str, list[str]]:
    """Handle top leakage section."""
    df = load_csv_if_exists(memo_exports / "price_realization_top_leakage.csv")
    if df.empty:
        return "### Pricing realization and leakage\nData unavailable.\n", []
    top10 = df.head(10).copy()
    leakage_total = float(top10["leakage_amount"].fillna(0).sum())
    avg_margin = float(top10["gross_margin_pct"].fillna(0).mean() * 100) if "gross_margin_pct" in top10.columns else 0.0
    lines = [
        "### Pricing realization and leakage",
        f"- Top 10 leakage SKUs account for approximately {_fmt_money(leakage_total)} in discount leakage.",
        f"- Average gross margin across top leakage SKUs is {_fmt_pct(avg_margin)}.",
        "- Priority action: review discount guardrails and exception approvals for the highest leakage SKUs.",
        "",
    ]
    bullet_skus = [f"- {row['sku']}: {_fmt_money(float(row['leakage_amount']))} leakage" for _, row in top10.head(5).iterrows()]
    lines.extend(bullet_skus)
    lines.append("")
    return "\n".join(lines), [str(x) for x in top10.head(5)["sku"].tolist()]


def _promo_section(memo_exports: Path) -> str:
    """Handle promo section."""
    df = load_csv_if_exists(memo_exports / "promo_effectiveness_summary.csv")
    if df.empty:
        return "### Promotion effectiveness\nData unavailable.\n"
    best = df.sort_values("incremental_gross_profit", ascending=False).head(3)
    worst = df.sort_values("incremental_gross_profit", ascending=True).head(3)
    lines = [
        "### Promotion effectiveness",
        "- Promotions show mixed profitability outcomes after discounting.",
        "- Highest incremental gross profit promotions:",
    ]
    lines.extend(
        [f"- {row['promo_id']}: {_fmt_money(float(row['incremental_gross_profit']))}" for _, row in best.iterrows()]
    )
    lines.append("- Lowest incremental gross profit promotions:")
    lines.extend(
        [f"- {row['promo_id']}: {_fmt_money(float(row['incremental_gross_profit']))}" for _, row in worst.iterrows()]
    )
    lines.append("")
    return "\n".join(lines)


def _elasticity_section(memo_exports: Path) -> str:
    """Handle elasticity section."""
    df = load_csv_if_exists(memo_exports / "elasticity_estimates.csv")
    if df.empty:
        return "### Elasticity summary\nData unavailable.\n"
    if "grain_type" in df.columns:
        cat = df.loc[df["grain_type"] == "category"].copy()
    else:
        cat = df.copy()
    if cat.empty:
        cat = df.copy()
    avg_elas = float(cat["elasticity_b1"].mean())
    most_elastic = cat.sort_values("elasticity_b1").head(1)
    least_elastic = cat.sort_values("elasticity_b1", ascending=False).head(1)
    lines = [
        "### Elasticity summary",
        f"- Average estimated elasticity across modeled groups is {avg_elas:.2f}.",
    ]
    if not most_elastic.empty:
        r = most_elastic.iloc[0]
        lines.append(f"- Most elastic group: {r['grain']} ({r['elasticity_b1']:.2f}).")
    if not least_elastic.empty:
        r = least_elastic.iloc[0]
        lines.append(f"- Least elastic group: {r['grain']} ({r['elasticity_b1']:.2f}).")
    lines.append("- Recommendation: use smaller test increases for highly elastic groups and larger tests for less elastic groups.")
    lines.append("")
    return "\n".join(lines)


def _forecast_section(memo_exports: Path) -> str:
    """Handle forecast section."""
    df = load_csv_if_exists(memo_exports / "forecast_12_weeks.csv")
    if df.empty:
        return "### Forecast summary\nData unavailable.\n"
    avg_units = float(df["forecast_units"].mean())
    first = float(df["forecast_units"].iloc[0])
    last = float(df["forecast_units"].iloc[-1])
    trend_pct = ((last / first) - 1) * 100 if first else 0.0
    lines = [
        "### Forecast summary",
        f"- Average 12-week forecast volume is {avg_units:,.0f} units per week.",
        f"- Forecast trend from first to last projected week is {_fmt_pct(trend_pct)}.",
        "- Recommendation: sequence pricing and promotion changes with forecast uncertainty bands in mind.",
        "",
    ]
    return "\n".join(lines)


def _actions_section(memo_exports: Path) -> str:
    """Handle actions section."""
    df = load_csv_if_exists(memo_exports / "recommended_actions.csv")
    if df.empty:
        return "### Inventory pricing actions\nData unavailable.\n"
    counts = df["action_type"].fillna("unknown").value_counts()
    lines = [
        "### Inventory pricing actions",
        f"- Markdown actions: {int(counts.get('markdown', 0))}",
        f"- Hold actions: {int(counts.get('hold', 0))}",
        f"- Increase actions: {int(counts.get('increase', 0))}",
    ]
    if "days_of_supply" in df.columns:
        overstock = df.loc[df["action_type"] == "markdown", "days_of_supply"].dropna()
        if not overstock.empty:
            lines.append(f"- Median days of supply for markdown recommendations: {float(overstock.median()):.1f} days.")
    lines.append("- Recommendation: execute markdowns in waves and monitor realized margin versus guardrails.")
    lines.append("")
    return "\n".join(lines)


def _scenario_section(memo_exports: Path) -> str:
    """Handle scenario section."""
    df = load_csv_if_exists(memo_exports / "scenario_comparison.csv")
    if df.empty:
        return "### Scenario simulation\nData unavailable.\n"
    best_gp = df.sort_values("projected_gross_profit_change_pct", ascending=False).head(1)
    lines = ["### Scenario simulation"]
    if not best_gp.empty:
        r = best_gp.iloc[0]
        lines.append(
            f"- Highest projected gross profit scenario: `{r['scenario_name']}` "
            f"({_fmt_pct(float(r['projected_gross_profit_change_pct']))} gross profit change, "
            f"{_fmt_pct(float(r['projected_revenue_change_pct']))} revenue change)."
        )
    lines.append("- Recommendation: validate the top scenario with a controlled category-level pricing test before broad rollout.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    memo_exports = Path(params["paths"]["exports_for_memo"])
    memo_dir = Path("memo")
    memo_dir.mkdir(parents=True, exist_ok=True)

    step = StepLogger(total_steps=3, task_name="generate_memo_summary")
    step.step("Loading analysis outputs for memo summary")

    leakage_section, _ = _top_leakage_section(memo_exports)
    sections = [
        "# Auto-Generated Quantified Findings",
        "",
        "This file is generated from pipeline outputs and can be copied into the final memo draft.",
        "",
        leakage_section,
        _promo_section(memo_exports),
        _elasticity_section(memo_exports),
        _forecast_section(memo_exports),
        _actions_section(memo_exports),
        _scenario_section(memo_exports),
    ]

    step.step("Writing markdown summary")
    out_path = memo_dir / "pricing_strategy_memo_auto_summary.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    log_info(f"Wrote memo summary {out_path.resolve()}")

    step.step("Completed")


if __name__ == "__main__":
    main()
