-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select
    order_week as week_date,
    sku,
    channel,
    promo_id,
    units,
    revenue,
    gross_profit,
    promo_unit_lift,
    incremental_gross_profit
from {{ ref('mart_promo_performance') }}
