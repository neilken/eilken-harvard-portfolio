-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select
    cast(recommendation_snapshot_date as date) as recommendation_snapshot_date,
    sku,
    action_type,
    cast(recommended_pct_change as numeric(12,4)) as recommended_pct_change,
    rationale,
    expected_impact_note
from {{ source('marts_analysis_outputs', 'recommended_actions') }}
