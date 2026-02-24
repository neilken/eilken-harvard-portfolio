-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

with baseline as (
    -- Expected discount policy proxy by price tier and promo status.
    select * from (values
        ('A', true, 0.18::numeric),
        ('A', false, 0.12::numeric),
        ('B', true, 0.13::numeric),
        ('B', false, 0.07::numeric),
        ('C', true, 0.10::numeric),
        ('C', false, 0.03::numeric)
    ) as t(price_tier, promo_flag, expected_discount_pct)
)
select
    s.order_week,
    s.sku,
    s.customer_id,
    s.segment,
    s.channel,
    s.price_tier,
    s.promo_flag,
    s.discount_pct_recomputed as actual_discount_pct,
    b.expected_discount_pct,
    -- Leakage only counts discount above expected policy, not all discount dollars.
    greatest(coalesce(s.discount_pct_recomputed, 0) - b.expected_discount_pct, 0) as leakage_pct,
    greatest(coalesce(s.discount_pct_recomputed, 0) - b.expected_discount_pct, 0) * s.list_revenue_line as leakage_amount,
    (greatest(coalesce(s.discount_pct_recomputed, 0) - b.expected_discount_pct, 0) > 0.01) as leakage_flag
from {{ ref('int_sales_enriched') }} s
left join baseline b
  on s.price_tier = b.price_tier
 and s.promo_flag = b.promo_flag
-- Returns are excluded so leakage reflects active selling behavior.
where not s.returned_flag
