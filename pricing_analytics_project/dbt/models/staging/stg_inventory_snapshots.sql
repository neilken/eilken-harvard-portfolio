-- dbt staging model. Cleans and types raw source data for downstream joins and metrics.

select
    -- Inventory remains at snapshot_date x sku grain in staging and is enriched later in the intermediate layer.
    cast(snapshot_date as date) as snapshot_date,
    sku,
    cast(on_hand_units as integer) as on_hand_units,
    cast(on_order_units as integer) as on_order_units,
    cast(backorder_units as integer) as backorder_units,
    cast(unit_cost as numeric(12,2)) as unit_cost
from {{ source('raw', 'inventory_snapshots') }}
