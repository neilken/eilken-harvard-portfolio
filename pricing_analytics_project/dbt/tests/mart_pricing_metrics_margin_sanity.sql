-- dbt data test. Returns failing rows when an assertion is violated.

select *
from {{ ref('mart_pricing_metrics_weekly') }}
where gross_margin_pct is not null
  and (gross_margin_pct < -0.25 or gross_margin_pct > 0.95)
