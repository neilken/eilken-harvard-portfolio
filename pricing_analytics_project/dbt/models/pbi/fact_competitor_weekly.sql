-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select
    snapshot_week as week_date,
    sku,
    competitor_min_price,
    competitor_median_price,
    avg_transaction_price,
    price_index_vs_comp_min,
    price_index_vs_comp_median,
    competitor_count
from {{ ref('mart_competitive_position') }}
