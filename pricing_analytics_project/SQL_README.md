# SQL README

## Purpose
This document explains how SQL is used across the pricing analytics project and what each SQL file or SQL folder is responsible for.

Status:
- SQL models and views are implemented and used in the working pipeline
- Core SQL outputs have been validated for existence, row counts, and consistency with Python-generated exports

The SQL layer in this project is split across:
- PostgreSQL initialization SQL (`docker/initdb/`)
- Raw table DDL (`sql/`)
- dbt transformation SQL (`dbt/models/`)
- dbt test SQL (`dbt/tests/`)
- dbt macro SQL (`dbt/macros/`)

This project uses SQL for warehouse setup, data modeling, validation, and Power BI-ready views.

## SQL execution flow
1. Docker starts PostgreSQL and runs init SQL in `docker/initdb/`
2. Python loaders execute `sql/raw_tables.sql` and load CSVs into `raw.*`
3. dbt SQL builds `staging`, `intermediate`, `marts`, and `pbi` objects
4. Python analysis modules write `marts.analysis_*` tables
5. dbt `pbi` SQL exposes dashboard-friendly views over `marts` and analysis outputs
6. dbt tests run SQL assertions against staged and modeled data

## Important note about source of truth
- Source SQL files live in:
  - `pricing_analytics_project/sql/`
  - `pricing_analytics_project/docker/initdb/`
  - `pricing_analytics_project/dbt/models/`
  - `pricing_analytics_project/dbt/tests/`
  - `pricing_analytics_project/dbt/macros/`
- Edit source SQL in project folders and treat generated SQL as build artifacts:
  - `pricing_analytics_project/dbt/target/`
- Treat package SQL under the virtual environment as dependency code:
  - `pricing_analytics_project/.venv-wsl/`

Location note:
- This README is at the project root because it documents SQL across multiple folders, not only `sql/`
- A future move to `sql/README.md` is reasonable if the cross-folder scope is kept explicit

## PostgreSQL initialization SQL (`docker/initdb/`)

### `docker/initdb/00_create_schemas.sql`
Purpose:
- Creates the project schema layout used by the pipeline and dbt

Schemas created:
- `raw`
- `staging`
- `intermediate`
- `marts`
- `pbi`
- `audit` (reserved for future audit and validation logging)

When it runs:
- Automatically on first container initialization for a new Docker volume

### `docker/initdb/01_create_roles.sql`
Purpose:
- Creates database roles used by the pipeline and BI tooling
- Grants schema and table permissions
- Sets default privileges for future dbt and analysis-created objects

Key roles:
- `pricing_app`
  - read/write role for loaders, dbt, and Python analysis outputs
- `pricing_ro`
  - read-only role intended for Power BI imports from `marts` and `pbi`

## Raw table DDL (`sql/`)

### `sql/raw_tables.sql`
Purpose:
- Defines raw source tables loaded from generated CSV files

Tables defined:
- `raw.products`
  - Product master data
- `raw.customers`
  - Customer master data
- `raw.sales_order_lines`
  - Transaction-level sales fact source
  - Composite primary key: `(order_id, line_id)`
- `raw.inventory_snapshots`
  - Inventory snapshots at `snapshot_date x sku`
- `raw.competitor_snapshots`
  - Competitor snapshots at normalized `snapshot_date x competitor_id x sku`
  - Includes `captured_at` for capture-time tracking

How it is used:
- Executed by the raw loaders on each run before `COPY`

## dbt SQL models (`dbt/models/`)

dbt models are organized into four layers:
- `staging`
- `intermediate`
- `marts`
- `pbi`

### `dbt/models/staging/`
Purpose:
- Clean and type raw source fields
- Standardize boolean and date handling
- Recompute/validate key derived fields used later in marts

Files:
- `stg_products.sql`
  - Types product attributes for joins and dimension builds
- `stg_customers.sql`
  - Types customer attributes used for segmentation
- `stg_sales_order_lines.sql`
  - Core cleaned sales line model
  - Recomputes `discount_pct_recomputed`
  - Flags discount discrepancies vs source field
  - Derives line-level revenue and cost fields
- `stg_inventory_snapshots.sql`
  - Cleaned inventory snapshot source model
- `stg_competitor_snapshots.sql`
  - Cleaned competitor snapshot source model
  - Derives `snapshot_week` for weekly rollups

### `dbt/models/intermediate/`
Purpose:
- Join staged models together
- Define reusable business logic and derived metrics
- Normalize grains for marts

Files:
- `int_sales_enriched.sql`
  - Enriches sales lines with product and customer attributes
  - Derives `order_week`
  - Derives gross and contribution profit line metrics
  - Produces reusable line-level enriched sales model
- `int_competitor_position.sql`
  - Aggregates competitor snapshots to weekly SKU benchmarks
  - Computes internal vs competitor price indices
  - Produces reusable competitive position metrics
- `int_inventory_enriched.sql`
  - Aligns inventory with weekly demand
  - Calculates `days_of_supply`
  - Flags overstock conditions

### `dbt/models/marts/`
Purpose:
- Build analytics-ready business outputs at reporting grains used by dashboards and analysis

Files:
- `mart_pricing_metrics_weekly.sql`
  - Weekly pricing and margin metrics at:
    - `order_week x sku x customer_id x category x product_family x segment x channel`
  - Excludes returns through conditional aggregation
  - Computes price realization, gross margin, and contribution profit after aggregation
- `mart_discount_leakage.sql`
  - Computes discount leakage above expected discount policy proxy
  - Uses tier and promo status baseline discount thresholds
  - Flags leakage exceptions
- `mart_margin_erosion.sql`
  - Margin trend summary at:
    - `order_week x sku x category x segment x channel`
  - Used for margin erosion visualizations
- `mart_promo_performance.sql`
  - Weekly promo performance and quasi A/B lift proxy
  - Compares promo weeks to non-promo baselines by SKU and channel
- `mart_competitive_position.sql`
  - Competitive pricing position with product attributes
  - Exposes price index metrics for dashboard use
- `mart_inventory_actions_base.sql`
  - Inventory rule-engine base model for pricing recommendations
  - Includes overstock and lifecycle flags plus default guardrail fields

### `dbt/models/pbi/`
Purpose:
- Expose Power BI import-ready dimensions and facts
- Keep Power BI data loading simple and stable

File groups:

Dimensions:
- `dim_date.sql`
- `dim_product.sql`
- `dim_customer.sql`
- `dim_competitor.sql`
- `dim_memo_figures.sql`

Core facts (dbt marts-backed):
- `fact_sales_weekly.sql`
- `fact_inventory_weekly.sql`
- `fact_competitor_weekly.sql`
- `fact_promo_weekly.sql`
- `fact_recommendations.sql`

Analysis passthrough facts (Python `marts.analysis_*` backed):
- `fact_price_realization_analysis.sql`
- `fact_margin_erosion_analysis.sql`
- `fact_price_waterfall_category.sql`
- `fact_promo_effectiveness_analysis.sql`
- `fact_promo_regression_effects.sql`
- `fact_elasticity_estimates.sql`
- `fact_forecast_12_weeks.sql`
- `fact_scenario_comparison.sql`
- `fact_recommended_actions_analysis.sql`
- `fact_pocket_margin_proxy.sql`
- `fact_price_variance_vs_target.sql`
- `fact_price_dispersion_by_sku.sql`
- `fact_discount_exception_rates.sql`
- `fact_promo_roi_summary.sql`
- `fact_cannibalization_proxy.sql`
- `fact_inventory_sellthrough_analysis.sql`
- `fact_competitor_gap_distribution.sql`
- `fact_win_loss_proxy.sql`

Notes:
- Many `pbi` analysis models are simple passthrough views (`select * from source(...)`)
- These views are intentionally thin so the Python analysis outputs remain the source of logic

## dbt tests SQL (`dbt/tests/`)
Purpose:
- Custom SQL assertions that return failing rows when a rule is violated

Files:
- `schema_sanity.sql`
  - Basic environment or schema presence sanity test
- `stg_sales_order_lines_price_bounds.sql`
  - Validates line price bounds and basic price consistency
- `stg_sales_order_lines_unique_order_line.sql`
  - Validates `(order_id, line_id)` uniqueness
- `mart_pricing_metrics_margin_sanity.sql`
  - Validates margin sanity thresholds in `mart_pricing_metrics_weekly`

How to interpret:
- A passing test returns zero rows
- A failing test returns offending rows for investigation

## dbt macro SQL (`dbt/macros/`)

### `dbt/macros/generate_schema_name.sql`
Purpose:
- Controls dbt schema naming so models materialize into direct schemas such as:
  - `staging`
  - `intermediate`
  - `marts`
  - `pbi`

Why it matters:
- Keeps the warehouse layout aligned with the project structure and naming conventions
- Prevents default dbt schema suffixing behavior from creating unexpected schema names

## SQL grains and logic conventions used in this project

Common grains:
- Raw sales: transaction line (`order_id`, `line_id`)
- Inventory: `snapshot_date x sku`
- Competitor snapshots: normalized `snapshot_date x competitor_id x sku`
- Weekly reporting: `order_week` or `snapshot_week`

Common logic conventions:
- Returns are often excluded for pricing, margin, promo, and elasticity metrics
- Price and margin percentages are generally calculated after aggregation, not averaged from line-level ratios
- Competitor pricing is rolled up to weekly SKU benchmarks for stable price index analysis
- `pbi` views are kept thin and dashboard-oriented

## How SQL interacts with Python outputs
Python analysis modules write results into:
- `marts.analysis_*`
- `marts.recommended_actions`

dbt `pbi` models then expose those tables as Power BI views:
- `pbi.fact_*_analysis`
- `pbi.fact_recommendations`

This design keeps:
- SQL/dbt responsible for warehouse modeling
- Python responsible for statistical and rule-based analytics
- Power BI loading simple and consistent

## Running and validating the SQL layer

Run dbt in WSL (recommended):
```bash
cd <repo_path>/pricing_analytics_project
. .venv-wsl/bin/activate
dbt run --project-dir dbt --profiles-dir dbt --threads 1
dbt test --project-dir dbt --profiles-dir dbt --threads 1
```

SQL layer validation already used in this project:
- dbt tests (`dbt test`)
- Row count and schema consistency checks between:
  - CSV exports
  - `marts` analysis tables
  - `pbi` passthrough views
- Sanity checks for:
  - key uniqueness
  - price bounds
  - margin sanity

## Editing guidance for SQL files
- Add comments for business logic, grain, and non-obvious formulas
- Keep comments concise and focused on logic
- Edit source SQL files and treat generated SQL in `dbt/target/` as build artifacts
- Re-run `dbt run` and `dbt test` after SQL changes

## SQL unification guidance (recommended)
Use consistent conventions across SQL files instead of merging layers into fewer files.

Standardize:
- naming conventions for grains and fact or dim outputs
- weekly date normalization logic (`date_trunc('week', ...)::date`)
- returns handling rules (`where not returned_flag` versus zeroing out returned rows)
- ratio calculations after aggregation
- top-of-file comments that state purpose and grain

Keep the current separation:
- keep `staging`, `intermediate`, `marts`, and `pbi` as separate layers
- keep Python statistical logic in Python unless there is a clear modeling reason to move it
