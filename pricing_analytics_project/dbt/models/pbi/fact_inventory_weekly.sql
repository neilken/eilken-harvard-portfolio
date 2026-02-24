-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select
    snapshot_week as week_date,
    sku,
    on_hand_units,
    on_order_units,
    backorder_units,
    days_of_supply,
    overstock_flag,
    end_of_life_flag
from {{ ref('mart_inventory_actions_base') }}
