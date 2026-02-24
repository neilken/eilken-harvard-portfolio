-- dbt intermediate model. Enriches cleaned data and defines reusable derived fields for marts.

select
    s.order_id,
    s.line_id,
    s.order_date,
    -- order_week is the common reporting grain used by pricing, promo, and elasticity marts.
    date_trunc('week', s.order_date)::date as order_week,
    s.sku,
    p.product_name,
    p.category,
    p.product_family,
    p.brand,
    p.lifecycle_stage,
    s.customer_id,
    c.segment,
    c.region,
    c.channel,
    c.price_tier,
    s.units,
    s.list_price,
    s.transaction_price,
    s.discount_pct_source,
    s.discount_pct_recomputed,
    s.discount_pct_discrepancy_flag,
    s.promo_flag,
    s.promo_id,
    s.cogs_unit,
    coalesce(s.freight_unit, 0) as freight_unit,
    coalesce(s.payment_fees_unit, 0) as payment_fees_unit,
    s.returned_flag,
    s.revenue_line,
    s.list_revenue_line,
    s.cogs_line,
    -- gross and contribution profit are defined once here and reused across downstream marts.
    (s.revenue_line - s.cogs_line) as gross_profit_line,
    (s.revenue_line - s.cogs_line - coalesce(s.freight_unit, 0) * s.units - coalesce(s.payment_fees_unit, 0) * s.units) as contribution_profit_line,
    case when nullif(s.revenue_line, 0) is null then null else (s.revenue_line - s.cogs_line) / nullif(s.revenue_line, 0) end as gross_margin_pct_line
from {{ ref('stg_sales_order_lines') }} s
-- left joins retain sales rows even if a generated dimension row is unexpectedly missing.
left join {{ ref('stg_products') }} p using (sku)
left join {{ ref('stg_customers') }} c using (customer_id)
