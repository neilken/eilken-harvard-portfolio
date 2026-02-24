-- dbt singular test. Fails only when gross_margin_pct is null for rows where margin percent should be defined.

select *
from {{ ref('mart_pricing_metrics_weekly') }}
where gross_margin_pct is null
  and coalesce(gross_margin_pct_is_defined, false) = true

