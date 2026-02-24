-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

with dates as (
    select distinct order_week::date as d from {{ ref('mart_pricing_metrics_weekly') }}
    union
    select distinct snapshot_week::date as d from {{ ref('mart_competitive_position') }}
    union
    select distinct snapshot_week::date as d from {{ ref('mart_inventory_actions_base') }}
)
select
    d as date_key,
    extract(week from d) as week_of_year,
    extract(month from d) as month_num,
    extract(quarter from d) as quarter_num,
    extract(year from d) as year_num
from dates
