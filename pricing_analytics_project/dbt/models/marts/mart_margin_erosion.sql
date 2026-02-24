-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

select
    order_week,
    sku,
    category,
    segment,
    channel,
    -- Weekly SKU x segment x channel grain supports margin erosion trend slicing in dashboards.
    avg(gross_margin_pct_line) as avg_gross_margin_pct,
    sum(gross_profit_line) as gross_profit,
    sum(revenue_line) as revenue
from {{ ref('int_sales_enriched') }}
-- Returns are excluded from margin erosion summaries.
where not returned_flag
group by 1,2,3,4,5
