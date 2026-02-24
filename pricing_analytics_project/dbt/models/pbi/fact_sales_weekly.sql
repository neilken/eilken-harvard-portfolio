-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select
    order_week as week_date,
    sku,
    customer_id,
    segment,
    channel,
    units,
    revenue,
    list_revenue,
    discount_amount,
    price_realization_pct,
    gross_profit,
    gross_margin_pct,
    gross_margin_pct_is_defined,
    gross_margin_pct_null_reason,
    contribution_profit
from {{ ref('mart_pricing_metrics_weekly') }}
