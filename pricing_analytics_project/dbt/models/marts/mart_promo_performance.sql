-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

with base as (
    -- Base panel aggregates sales to weekly SKU x channel x promo_id grain.
    select
        order_week,
        sku,
        channel,
        promo_id,
        promo_flag,
        sum(units) as units,
        sum(revenue_line) as revenue,
        sum(gross_profit_line) as gross_profit
    from {{ ref('int_sales_enriched') }}
    where not returned_flag
    group by 1,2,3,4,5
),
promo as (
    -- Promo weeks are compared against non-promo baselines within the same SKU and channel.
    select * from base where promo_flag = true
),
nonpromo as (
    select sku, channel, avg(units) as avg_units_nonpromo, avg(gross_profit) as avg_gross_profit_nonpromo
    from base
    where coalesce(promo_flag, false) = false
    group by 1,2
)
select
    p.order_week,
    p.sku,
    p.channel,
    p.promo_id,
    p.units,
    p.revenue,
    p.gross_profit,
    n.avg_units_nonpromo,
    n.avg_gross_profit_nonpromo,
    -- Lift metrics are simple quasi A/B proxies and are refined further in Python regression outputs.
    (p.units - coalesce(n.avg_units_nonpromo, 0)) as promo_unit_lift,
    (p.gross_profit - coalesce(n.avg_gross_profit_nonpromo, 0)) as incremental_gross_profit
from promo p
left join nonpromo n using (sku, channel)
