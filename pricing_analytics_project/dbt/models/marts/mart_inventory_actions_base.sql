-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

select
    i.snapshot_date,
    i.snapshot_week,
    i.sku,
    p.category,
    p.lifecycle_stage,
    i.on_hand_units,
    i.on_order_units,
    i.backorder_units,
    i.days_of_supply,
    i.overstock_flag,
    (p.lifecycle_stage = 'end_of_life') as end_of_life_flag,
    -- margin_floor_pct and strategic_sku_flag are default placeholders used by recommendation logic.
    0.15::numeric as margin_floor_pct,
    false as strategic_sku_flag
from {{ ref('int_inventory_enriched') }} i
left join {{ ref('stg_products') }} p using (sku)
