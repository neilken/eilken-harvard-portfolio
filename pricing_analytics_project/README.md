# Pricing Analytics Project

End to end pricing analytics project using synthetic ERP style data, Postgres, dbt, Python analytics modules, and Power BI exports.

## Scope

- Synthetic data generation for products, customers, sales, inventory
- Simulated competitor pricing snapshots
- Raw data loading into Postgres
- dbt staging, intermediate, marts, and `pbi` views
- Python analysis modules for pricing, promo, elasticity, forecasting, inventory actions, and scenarios
- Additional pricing analyst metrics (pocket margin proxy, dispersion, exception rates, promo ROI proxy, sell-through, competitor gap, win/loss proxy)
- CSV exports for Power BI and memo artifacts

## Purpose

- Supports pricing decisions that affect revenue growth, margin protection, and inventory movement
- Combines transaction, customer, inventory, and competitor data into one analytics workflow
- Produces recommendation outputs and scenario comparisons, not only descriptive reporting
- Mirrors a practical analyst workflow used by pricing, sales operations, and revenue management teams

## Tech Stack

- Python (`pandas`, `statsmodels`, `sqlalchemy`, `matplotlib`)
- SQL and PostgreSQL
- dbt (`dbt-postgres`)
- Docker (local Postgres runtime)
- Power BI (import-ready `pbi` views, DAX measure pack, theme assets)
- WSL (recommended execution environment on Windows)

## Functional Coverage

- Analytics engineering:
  - Postgres warehouse schemas, raw loaders, dbt modeling layers (`staging`, `intermediate`, `marts`, `pbi`)
  - dbt tests and output consistency validation across CSV exports, `marts`, and `pbi`
- Data science and analytics:
  - price realization, promo effectiveness, elasticity, forecasting, inventory pricing actions, and scenario simulation
  - advanced pricing metrics (pocket margin proxy, dispersion, exception rates, promo ROI proxy, competitor gap, win/loss proxy)
- BI and reporting enablement:
  - Power BI-ready `pbi` views, DAX measure pack, theme file, and dashboard page images from current outputs

## Current status

- Core pipeline is implemented and runs end to end in WSL
- Python analysis outputs, `marts.analysis_*` tables, and `pbi` views have been validated for row and column consistency

## Results summary (latest pipeline run)

- Synthetic raw data generated:
  - `raw.products`: `400`
  - `raw.customers`: `900`
  - `raw.sales_order_lines`: `46,021`
  - `raw.inventory_snapshots`: `32,583`
  - `raw.competitor_snapshots`: `97,824`
- Elasticity estimates generated: `12` (`6` category + `6` product family)
- Forecast output generated: `12` weeks
  - Average projected weekly units: `1,133.6`
  - Total projected units across horizon: `13,603.6`
- Inventory pricing recommendations generated: `400`
  - `markdown`: `167`
  - `hold`: `132`
  - `increase`: `101`
- Best scenario from `scenario_comparison.csv`:
  - `plus_5_pct_selected_categories`
  - projected revenue change: `+4.88%`
  - projected gross profit change: `+13.55%`
- dbt validation:
  - `dbt run`: pass
  - `dbt test`: pass

## Key business recommendations snapshot

- Recommended action mix from latest run: `400` SKU actions (`167` markdown, `132` hold, `101` increase)
- Best modeled scenario: `plus_5_pct_selected_categories`
  - projected revenue change: `+4.88%`
  - projected gross profit change: `+13.55%`
- Forecast output provides a `12` week planning horizon for demand and inventory pricing review
- Price realization, leakage, and margin erosion outputs identify concentration points for pricing governance follow-up

## Dashboard preview

Python-generated dashboard page previews below use real pipeline outputs from the simulated dataset. Each image is a Power BI-style page preview rendered from the current analysis exports.

### Executive summary preview

Executive summary dashboard preview

### Realization and leakage preview

Realization and leakage dashboard preview

### Promotions and elasticity preview

Promotions and elasticity dashboard preview

### Forecast and inventory actions preview

Forecast and inventory actions dashboard preview

## Data quality and validation

- dbt tests validate schema integrity, uniqueness, accepted values, price bounds, and margin sanity checks
- Python export outputs have been checked against `marts` tables and `pbi` views for row and column consistency
- A targeted dbt test fails only for invalid margin nulls on rows where margin percent should be defined

## Analysis

The analysis layer in `src/analysis/` computes pricing diagnostics and decision support outputs after raw loading and dbt modeling.

Analysis documentation: `src/analysis/README.md`

Key analysis areas:
- Price realization and discount leakage concentration
- Margin erosion and category price waterfall
- Promo effectiveness (quasi A/B and regression-adjusted effects)
- Price elasticity estimates by category and product family
- 12-week demand forecasting with promo and competitor exogenous inputs
- Inventory pricing recommendations with margin guardrails
- Pricing scenario simulation
- Advanced pricing metrics (pocket margin proxy, exception rates, dispersion, promo ROI proxy, competitor gap, win/loss proxy)

Analysis outputs:
- CSV exports for Power BI: `data/exports_for_pbi/`
- CSV exports for memo content: `data/exports_for_memo/`
- Postgres tables in `marts` (`marts.analysis_*`, `marts.recommended_actions`)
- Memo figures: `memo/figures/`
- Dashboard page images: `dashboards/powerbi/screenshots/`


## Example analysis figures

### Elasticity estimate confidence intervals

Elasticity estimates figure

### 12-week demand forecast

Forecast figure

## Repo structure

```text
pricing_analytics_project/
|-- README.md
|-- requirements.txt
|-- .env.example
|-- Makefile
|-- docker/
|   |-- docker-compose.yml
|   `-- initdb/
|       |-- 00_create_schemas.sql
|       `-- 01_create_roles.sql
|-- sql/
|   `-- raw_tables.sql
|-- dbt/
|   |-- dbt_project.yml
|   |-- profiles.yml
|   |-- macros/
|   |-- models/
|   |   |-- staging/
|   |   |-- intermediate/
|   |   |-- marts/
|   |   `-- pbi/
|   `-- tests/
|-- src/
|   |-- config/
|   |   `-- params.yaml
|   |-- ingest/
|   |   |-- generate_erp_data.py
|   |   `-- competitor_simulator.py
|   |-- load/
|   |   |-- load_raw_to_postgres.py
|   |   `-- load_competitor_to_postgres.py
|   |-- analysis/
|   |   |-- README.md
|   |   |-- price_realization.py
|   |   |-- promo_effectiveness.py
|   |   |-- elasticity_model.py
|   |   |-- forecasting.py
|   |   |-- inventory_pricing_engine.py
|   |   |-- scenario_simulator.py
|   |   |-- advanced_pricing_metrics.py
|   |   |-- generate_memo_figures.py
|   |   |-- generate_memo_summary.py
|   |   `-- generate_powerbi_mock_dashboards.py
|   `-- utils/
|-- data/
|   |-- raw_generated/
|   |-- external_generated/
|   |-- exports_for_pbi/
|   `-- exports_for_memo/
|-- dashboards/
|   `-- powerbi/
|       |-- dax/
|       |-- theme/
|       `-- screenshots/
|-- memo/
|   |-- pricing_strategy_memo.md
|   |-- pricing_strategy_memo_auto_summary.md
|   `-- figures/
`-- scripts/
    `-- run_pipeline_wsl.sh
```

## Pipeline architecture (flow)

```text
Synthetic data generators                      Docker / Postgres
-----------------------                       -----------------
src/ingest/generate_erp_data.py   ----->      raw schema tables
src/ingest/competitor_simulator.py ----->     (products, customers, sales,
                                              inventory, competitor snapshots)
                                                    |
                                                    v
Python loaders (COPY + indexes)               dbt modeling layers
----------------------------                  -------------------
src/load/load_raw_to_postgres.py   ----->     staging -> intermediate -> marts
src/load/load_competitor_to_postgres.py       (weekly pricing, promo, margin,
                                              competitor, inventory marts)
                                                    |
                                                    v
Python analytics modules                    Analysis outputs in Postgres + CSV
------------------------                    -------------------------------
price_realization.py               ----->   marts.analysis_* tables
promo_effectiveness.py             ----->   marts.recommended_actions
elasticity_model.py                ----->   data/exports_for_pbi/*.csv
forecasting.py                     ----->   data/exports_for_memo/*.csv
inventory_pricing_engine.py                memo/figures/*.png
scenario_simulator.py                      dashboards/powerbi/screenshots/*.png
advanced_pricing_metrics.py
                                                    |
                                                    v
dbt pbi views (dims/facts + analysis views)  ----->  Power BI import / reporting
```

## SQL database setup (Postgres)

SQL documentation: `SQL_README.md`

## Database runtime

- Engine: PostgreSQL 16 (Docker container)
- Container orchestration: `docker/docker-compose.yml`
- Default database: `pricing`
- Host port: `5432`

## Schema layout

- `raw`: ingested/generated source tables
- `staging`: dbt staging views (typed/cleaned fields)
- `intermediate`: dbt intermediate tables (enriched joins and derived metrics)
- `marts`: dbt marts and Python analysis output tables (`analysis_*`, `recommended_actions`)
- `pbi`: Power BI import-friendly views (dims/facts and analysis views)
- `audit`: reserved for validation/logging (optional future expansion)

## Roles and access

Configured in `docker/initdb/01_create_roles.sql`:

- `pricing_app`
  - read/write access for pipeline operations and dbt modeling
  - database privileges to connect/create temporary objects
- `pricing_ro`
  - read-only access for Power BI imports from `marts` and `pbi`

## Raw tables (created by SQL DDL)

Defined in `sql/raw_tables.sql`:

- `raw.products`
- `raw.customers`
- `raw.sales_order_lines`
- `raw.inventory_snapshots`
- `raw.competitor_snapshots`

## How SQL is used in the pipeline

- Init SQL:
  - creates schemas and roles/grants
- Loader SQL:
  - `TRUNCATE`, `COPY`, `CREATE INDEX`, `ANALYZE`
- dbt SQL:
  - transforms raw data into `staging`, `intermediate`, `marts`, and `pbi`
- dbt tests (SQL):
  - validates price bounds, uniqueness, accepted values, and margin sanity
- Python + SQLAlchemy:
  - reads/writes analysis outputs in `marts.analysis_*` and `marts.recommended_actions`

## Core `pbi` objects for Power BI import

- Dimensions:
  - `pbi.dim_date`, `pbi.dim_product`, `pbi.dim_customer`, `pbi.dim_competitor`, `pbi.dim_memo_figures`
- Facts (core):
  - `pbi.fact_sales_weekly`, `pbi.fact_inventory_weekly`, `pbi.fact_competitor_weekly`, `pbi.fact_promo_weekly`, `pbi.fact_recommendations`
- Facts (analysis outputs):
  - `pbi.fact_price_realization_analysis`
  - `pbi.fact_margin_erosion_analysis`
  - `pbi.fact_price_waterfall_category`
  - `pbi.fact_promo_effectiveness_analysis`
  - `pbi.fact_promo_regression_effects`
  - `pbi.fact_elasticity_estimates`
  - `pbi.fact_forecast_12_weeks`
  - `pbi.fact_scenario_comparison`
  - `pbi.fact_recommended_actions_analysis`
  - `pbi.fact_pocket_margin_proxy`
  - `pbi.fact_price_variance_vs_target`
  - `pbi.fact_price_dispersion_by_sku`
  - `pbi.fact_discount_exception_rates`
  - `pbi.fact_promo_roi_summary`
  - `pbi.fact_cannibalization_proxy`
  - `pbi.fact_inventory_sellthrough_analysis`
  - `pbi.fact_competitor_gap_distribution`
  - `pbi.fact_win_loss_proxy`

## Quick start

1. Create `.env` from `.env.example`
2. Start Postgres with Docker
3. Install Python dependencies
4. Generate synthetic data and competitor snapshots
5. Load raw tables
6. Run analysis modules (creates or refreshes `marts.analysis_*` outputs)
7. Run dbt (`pbi` views depend on some analysis output tables)
8. Run dbt tests

## Recommended run path (WSL, no Docker Desktop)

Use WSL Ubuntu for Docker and dbt execution to avoid Windows to WSL localhost instability during longer dbt runs.

### One-command WSL pipeline

```bash
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && ./scripts/run_pipeline_wsl.sh"
```

Replace `<repo_path>` with the WSL path to the cloned repository root.

What the script does:

- Creates and reuses `.venv-wsl`
- Installs Python requirements in WSL
- Starts Postgres with `docker compose`
- Waits for Postgres readiness
- Generates synthetic data and competitor snapshots
- Loads raw tables to Postgres
- Runs all analysis modules
- Runs `dbt run` and `dbt test` (sequentially)
- Writes CSV exports and Postgres analysis tables in `marts`
- Refreshes Power BI-ready `pbi` views over dbt marts and Python analysis outputs

## Power BI connection notes (Windows + WSL Docker)

- Preferred server: `127.0.0.1`
- Database: `pricing`
- User: `pricing_app`
- Password: `pricing_app_pw`
- If Windows to WSL localhost forwarding is unstable, use the current WSL IP from `wsl -d Ubuntu -- hostname -I` as the Power BI server
- CSV import from `data/exports_for_pbi/` is a supported fallback and matches validated pipeline outputs

### Manual WSL commands (if debugging)

```bash
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && python3 -m venv .venv-wsl"
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && . .venv-wsl/bin/activate && pip install -r requirements.txt"
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && docker compose -f docker/docker-compose.yml up -d"
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && . .venv-wsl/bin/activate && python -m src.analysis.advanced_pricing_metrics"
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && . .venv-wsl/bin/activate && dbt run --project-dir dbt --profiles-dir dbt --threads 1"
wsl -d Ubuntu -- bash -lc "cd '<repo_path>/pricing_analytics_project' && . .venv-wsl/bin/activate && dbt test --project-dir dbt --profiles-dir dbt --threads 1"
```

## Example commands

```bash
make db-up
make generate-data
make load-raw
make load-competitor
make dbt-run
make dbt-test
make analysis
```

## Notes

- Data is synthetic unless a real competitor scrape is explicitly added later
- Additional Power BI import views exist in `dbt/models/pbi/` for `marts.analysis_*` outputs and `marts.recommended_actions`
- Full WSL pipeline run is validated end to end
- `dbt test` returns one expected warning for `gross_margin_pct` nulls (`severity: warn`)
- Analysis Postgres reruns use a dependency-safe refresh pattern (`TRUNCATE + INSERT`) that preserves dependent `pbi` views
- A detailed output validation report is saved at `validation_output_report.json` during manual validation checks
- Python and SQL source files include purpose comments and additional inline logic comments for maintainability

## Related docs

- Analysis module details: `src/analysis/README.md`
- SQL documentation: `SQL_README.md`

