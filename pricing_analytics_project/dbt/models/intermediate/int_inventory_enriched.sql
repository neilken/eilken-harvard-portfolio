-- dbt intermediate model. Enriches cleaned data and defines reusable derived fields for marts.

with demand as (
    -- Demand is aligned to weekly SKU grain so days-of-supply can be calculated from inventory snapshots.
    select sku, order_week, sum(case when returned_flag then 0 else units end) as weekly_units
    from {{ ref('int_sales_enriched') }}
    group by 1, 2
),
inventory as (
    -- snapshot_week normalizes daily inventory snapshots to the reporting week.
    select
        snapshot_date,
        date_trunc('week', snapshot_date)::date as snapshot_week,
        sku,
        on_hand_units,
        on_order_units,
        backorder_units,
        unit_cost
    from {{ ref('stg_inventory_snapshots') }}
)
select
    i.*,
    d.weekly_units,
    -- days_of_supply is expressed in days using weekly units as the denominator.
    case when nullif(d.weekly_units, 0) is null then null else (i.on_hand_units::numeric / nullif(d.weekly_units, 0)) * 7 end as days_of_supply,
    case when nullif(d.weekly_units, 0) is null then false else ((i.on_hand_units::numeric / nullif(d.weekly_units, 0)) * 7) > 180 end as overstock_flag
from inventory i
-- left join preserves inventory snapshots even when no sales occurred in the same week.
left join demand d
    on i.sku = d.sku
    and i.snapshot_week = d.order_week
