# Analysis Module README

## Purpose
This folder contains the Python analytics layer for the pricing analytics project. The modules in this folder consume generated data and modeled outputs, compute pricing and profitability analytics, export CSV files for Power BI and memo use, and write analysis tables back to Postgres (`marts` schema) when a database connection is available.

The analytics layer sits after:
- synthetic data generation (`src/ingest/`)
- raw loading into Postgres (`src/load/`)
- dbt transformations (`dbt/models/`)

## What this layer produces
- Quantified pricing diagnostics
- Promotion effectiveness outputs
- Elasticity estimates
- Forecast outputs
- Inventory pricing recommendations
- Scenario simulation outputs
- Memo figures (PNG)
- Auto-generated quantified memo summary markdown
- Power BI-style dashboard page images (PNG) based on exported data
- Postgres `marts.analysis_*` tables that mirror the CSV exports when database writes succeed

## Folder contents
- `_common.py`: shared helpers for CSV loading, export directories, Postgres reads/writes
- `price_realization.py`: price realization, leakage, margin erosion, waterfall outputs
- `promo_effectiveness.py`: quasi A/B promo analysis + regression-adjusted promo effects
- `elasticity_model.py`: log-log elasticity models by category and product family
- `forecasting.py`: SARIMAX forecast with exogenous promo and competitor promo signals
- `inventory_pricing_engine.py`: rule-based pricing action engine with guardrails
- `scenario_simulator.py`: elasticity-based pricing scenario comparisons
- `advanced_pricing_metrics.py`: additional pricing analyst metrics (pocket margin, exceptions, dispersion, ROI proxy, competitor gap, and more)
- `generate_memo_figures.py`: memo charts from exported CSV outputs
- `generate_memo_summary.py`: quantified markdown summary for memo drafting
- `generate_powerbi_mock_dashboards.py`: dashboard page images from exported data

## Shared conventions

## Console progress output
Each executable script uses `StepLogger` from `src/utils/logging.py` to print visible progress messages such as:
- start and completion of major steps
- row counts
- file output paths
- warning/fallback messages

## Export destinations
Configured in `src/config/params.yaml`:
- `data/exports_for_pbi/`
- `data/exports_for_memo/`
- `memo/figures/`

## Postgres writes
Most analysis modules write result tables to Postgres (if available) using `write_table_if_possible()` in `_common.py`.

Target schema:
- `marts`

Examples:
- `marts.analysis_price_realization_diagnostics`
- `marts.analysis_promo_effectiveness`
- `marts.analysis_elasticity_estimates`
- `marts.analysis_forecast_12_weeks`
- `marts.recommended_actions`
- `marts.analysis_scenario_comparison`
- `marts.analysis_pocket_margin_proxy`
- `marts.analysis_price_variance_vs_target`
- `marts.analysis_price_dispersion_by_sku`
- `marts.analysis_discount_exception_rates`
- `marts.analysis_promo_roi_summary`
- `marts.analysis_cannibalization_proxy`
- `marts.analysis_inventory_sellthrough`
- `marts.analysis_competitor_gap_distribution`
- `marts.analysis_win_loss_proxy`

If Postgres is unavailable, CSV exports still run and the script logs a warning instead of failing on the database write.

Validation status:
- CSV exports and corresponding `marts` and `pbi` objects have been checked for row and column consistency in the current pipeline run

## Dependency note for reruns
Some modules currently replace tables using a drop and recreate pattern. If `pbi` views already exist and depend on those `marts.analysis_*` tables, a rerun can log dependency warnings and skip the Postgres write while still writing CSV outputs.

Recommended full refresh order:
1. Run analysis modules to create or refresh `marts.analysis_*` outputs
2. Run `dbt run` to rebuild `pbi` views
3. Run `dbt test`

The WSL pipeline wrapper `scripts/run_pipeline_wsl.sh` follows this order.

## Data sources used by the modules

## CSV-based inputs (common path)
Most modules read from generated/exported files:
- `data/raw_generated/sales_order_lines.csv`
- `data/raw_generated/products.csv`
- `data/raw_generated/customers.csv`
- `data/raw_generated/inventory_snapshots.csv`
- `data/external_generated/competitor_snapshots.csv`
- `data/exports_for_pbi/*.csv` (for downstream figure or scenario support)

## Database reads (optional / fallback)
Some scripts attempt a database read via SQLAlchemy first and fall back to CSV/placeholder behavior when needed.

## Module details

## `price_realization.py`
Purpose:
- Compute pricing realization diagnostics and leakage concentration
- Summarize margin erosion by SKU/segment over time
- Create a category-level price waterfall table

Inputs:
- `sales_order_lines.csv`
- `products.csv`
- `customers.csv`

Outputs:
- CSV:
  - `data/exports_for_pbi/price_realization_diagnostics.csv`
  - `data/exports_for_pbi/margin_erosion_by_sku_segment.csv`
  - `data/exports_for_pbi/price_waterfall_category.csv`
  - `data/exports_for_memo/price_realization_top_leakage.csv`
  - `data/exports_for_memo/margin_erosion_by_sku_segment.csv`
  - `data/exports_for_memo/price_waterfall_category.csv`
- Postgres:
  - `marts.analysis_price_realization_diagnostics`
  - `marts.analysis_margin_erosion_by_sku_segment`
  - `marts.analysis_price_waterfall_category`

Key calculations:
- `revenue_line`, `list_revenue_line`, discount amount
- gross profit and contribution profit
- price realization percent
- margin erosion trend by week

## `promo_effectiveness.py`
Purpose:
- Estimate promotion impact using two approaches:
  - quasi A/B (promo vs non-promo baseline by SKU/channel)
  - regression-adjusted effects with controls

Inputs:
- `sales_order_lines.csv`
- `products.csv`
- `customers.csv`

Outputs:
- CSV:
  - `data/exports_for_pbi/promo_effectiveness.csv`
  - `data/exports_for_pbi/promo_regression_effects.csv`
  - `data/exports_for_memo/promo_effectiveness_summary.csv`
  - `data/exports_for_memo/promo_regression_effects.csv`
- Postgres:
  - `marts.analysis_promo_effectiveness`
  - `marts.analysis_promo_regression_effects`

Regression controls:
- price
- discount level
- seasonality (`sin_woy`, `cos_woy`)
- category and channel dummy variables

## `elasticity_model.py`
Purpose:
- Estimate price elasticity using a log-log OLS model

Grain:
- category
- product family

Preprocessing:
- weekly aggregation
- filters `units > 0` and `price > 0`
- excludes returned lines

Outputs:
- CSV:
  - `data/exports_for_pbi/elasticity_estimates.csv`
  - `data/exports_for_memo/elasticity_estimates.csv`
- Postgres:
  - `marts.analysis_elasticity_estimates`

Main fields in output:
- `grain_type`
- `grain`
- `elasticity_b1`
- `ci_low`, `ci_high`
- `n_obs`
- `r_squared`

## `forecasting.py`
Purpose:
- Forecast aggregate demand using SARIMAX with exogenous inputs

Inputs:
- `sales_order_lines.csv`
- `products.csv` (optional category enrichment)
- `external_generated/competitor_snapshots.csv` (competitor promo share)

Model:
- SARIMAX
- Endogenous series: weekly units
- Exogenous features:
  - promo intensity index
  - competitor promo share

Outputs:
- CSV:
  - `data/exports_for_pbi/forecast_12_weeks.csv`
  - `data/exports_for_memo/forecast_12_weeks.csv`
- Postgres:
  - `marts.analysis_forecast_12_weeks`

## `inventory_pricing_engine.py`
Purpose:
- Generate SKU-level pricing actions from inventory, lifecycle, competitor position, and margin guardrails

Inputs:
- `inventory_snapshots.csv`
- `sales_order_lines.csv`
- `products.csv`
- `competitor_snapshots.csv`

Rules implemented:
- markdown for end-of-life items
- markdown for overstock (`days_of_supply > 180`)
- increase for underpriced items vs competitor when margin buffer exists
- hold if a markdown violates margin floor guardrail

Outputs:
- CSV:
  - `data/exports_for_pbi/recommended_actions.csv`
  - `data/exports_for_memo/recommended_actions.csv`
- Postgres:
  - `marts.recommended_actions`

Key output fields:
- `sku`
- `action_type`
- `recommended_pct_change`
- `rationale`
- `expected_impact_note`
- `recommendation_snapshot_date`

## `scenario_simulator.py`
Purpose:
- Simulate pricing scenarios using elasticity estimates and baseline category metrics

Scenarios implemented:
- `plus_3_pct_selected_categories`
- `plus_5_pct_selected_categories`
- `tiered_elasticity_bands`

Inputs:
- baseline weekly category metrics from generated sales/product data
- elasticity estimates from `data/exports_for_pbi/elasticity_estimates.csv`

Outputs:
- CSV:
  - `data/exports_for_pbi/scenario_comparison.csv`
  - `data/exports_for_memo/scenario_comparison.csv`
- Postgres:
  - `marts.analysis_scenario_comparison`

## `advanced_pricing_metrics.py`
Purpose:
- Add a broader pricing analyst metric pack without making the pipeline overly heavy
- Compute operational pricing diagnostics often used in pricing reviews and governance meetings

Metrics included:
- pocket margin proxy and pocket cost drag
- price variance vs target by customer tier/channel
- price dispersion by SKU (cross-customer spread)
- discount exception rates vs expected band
- promo ROI proxy
- category cannibalization proxy during promo periods
- inventory sell-through metrics
- competitor price gap distribution
- win/loss proxy by competitor price index band

Inputs:
- `sales_order_lines.csv`
- `customers.csv`
- `products.csv`
- `inventory_snapshots.csv`
- `competitor_snapshots.csv`

Outputs:
- CSV (`data/exports_for_pbi/` and `data/exports_for_memo/`):
  - `pocket_margin_proxy.csv`
  - `price_variance_vs_target.csv`
  - `price_dispersion_by_sku.csv`
  - `discount_exception_rates.csv`
  - `promo_roi_summary.csv`
  - `cannibalization_proxy.csv`
  - `inventory_sellthrough_metrics.csv`
  - `competitor_gap_distribution.csv`
  - `win_loss_proxy.csv`
- Postgres:
  - `marts.analysis_pocket_margin_proxy`
  - `marts.analysis_price_variance_vs_target`
  - `marts.analysis_price_dispersion_by_sku`
  - `marts.analysis_discount_exception_rates`
  - `marts.analysis_promo_roi_summary`
  - `marts.analysis_cannibalization_proxy`
  - `marts.analysis_inventory_sellthrough`
  - `marts.analysis_competitor_gap_distribution`
  - `marts.analysis_win_loss_proxy`

## `generate_memo_figures.py`
Purpose:
- Create lightweight figures for memo use directly from exported analysis CSVs

Outputs (PNG):
- `memo/figures/top_discount_leakage_skus.png`
- `memo/figures/promo_incremental_gross_profit.png`
- `memo/figures/elasticity_estimates_ci.png`
- `memo/figures/forecast_12_weeks.png`
- `memo/figures/recommended_actions_counts.png`

## `generate_memo_summary.py`
Purpose:
- Generate a quantified markdown summary from current pipeline outputs to accelerate memo drafting

Output:
- `memo/pricing_strategy_memo_auto_summary.md`

Typical content:
- leakage totals and top SKUs
- promo winners/losers
- elasticity summary
- forecast summary
- recommendation counts
- top scenario summary

## `generate_powerbi_mock_dashboards.py`
Purpose:
- Generate Power BI-style dashboard page images using real exported data for layout and content reference

Outputs (PNG):
- `dashboards/powerbi/screenshots/page_1_executive_summary.png`
- `dashboards/powerbi/screenshots/page_2_realization_leakage.png`
- `dashboards/powerbi/screenshots/page_3_promotions_elasticity.png`
- `dashboards/powerbi/screenshots/page_4_forecast_inventory_actions.png`

Important note:
- These are Python-rendered dashboard page images for Power BI layout and content reference
- The charts and values are based on real pipeline outputs generated from synthetic data
- The generated PNGs are real images and plots based on simulated data outputs

## Execution order (recommended)
Run these after data generation, raw load, and dbt:
1. `price_realization.py`
2. `promo_effectiveness.py`
3. `elasticity_model.py`
4. `forecasting.py`
5. `inventory_pricing_engine.py`
6. `scenario_simulator.py`
7. `advanced_pricing_metrics.py`
8. `generate_memo_figures.py`
9. `generate_memo_summary.py`
10. `generate_powerbi_mock_dashboards.py`

## Run commands

## Windows (local Python)
```powershell
cd pricing_analytics_project
python -m src.analysis.price_realization
python -m src.analysis.promo_effectiveness
python -m src.analysis.elasticity_model
python -m src.analysis.forecasting
python -m src.analysis.inventory_pricing_engine
python -m src.analysis.scenario_simulator
python -m src.analysis.advanced_pricing_metrics
python -m src.analysis.generate_memo_figures
python -m src.analysis.generate_memo_summary
python -m src.analysis.generate_powerbi_mock_dashboards
```

## WSL (recommended for full pipeline)
```bash
cd /mnt/c/Users/eilke/Desktop/Github\ Repo/eilken-harvard-portfolio/pricing_analytics_project
. .venv-wsl/bin/activate
python -m src.analysis.price_realization
python -m src.analysis.promo_effectiveness
python -m src.analysis.elasticity_model
python -m src.analysis.forecasting
python -m src.analysis.inventory_pricing_engine
python -m src.analysis.scenario_simulator
python -m src.analysis.advanced_pricing_metrics
python -m src.analysis.generate_memo_figures
python -m src.analysis.generate_memo_summary
python -m src.analysis.generate_powerbi_mock_dashboards
```

Or run the WSL pipeline wrapper:
```bash
./scripts/run_pipeline_wsl.sh
```

## Troubleshooting

## Postgres write warnings in analysis scripts
Cause:
- Postgres container not running
- unreachable host/port from current shell

Effect:
- CSV exports still succeed
- Postgres writes are skipped with warning logs

Fix:
- Start Postgres via WSL Docker
- Run analytics from WSL (`.venv-wsl`) for stable connectivity
- Run `dbt run` after analysis modules so `pbi` views refresh against the latest `marts.analysis_*` tables

## Power BI connectivity issues on Windows
Cause:
- Windows to WSL localhost forwarding can be unstable on some machines

Fix:
- Try server `127.0.0.1` first
- If the port is intermittently unavailable, use the WSL IP from `wsl -d Ubuntu -- hostname -I`
- CSV import from `data/exports_for_pbi/` is a valid fallback path and uses the same computed outputs

## Empty outputs
Cause:
- upstream exports or generated raw CSV files missing

Fix:
- Run:
  - synthetic data generation
  - raw loaders
  - dbt models
  - analysis modules in the recommended order

## Statistical outputs look unusual
This project uses synthetic data and lightweight modeling choices. Results are intended to be directionally useful for a portfolio demonstration, not production-calibrated recommendations.
