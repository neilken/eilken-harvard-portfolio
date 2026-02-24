-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

select
    c.snapshot_week,
    c.sku,
    p.category,
    p.product_family,
    c.competitor_min_price,
    c.competitor_median_price,
    c.avg_transaction_price,
    c.price_index_vs_comp_min,
    c.price_index_vs_comp_median,
    c.competitor_count
from {{ ref('int_competitor_position') }} c
-- Product attributes are attached for category and family-level competitive views.
left join {{ ref('stg_products') }} p using (sku)
