-- dbt intermediate model. Enriches cleaned data and defines reusable derived fields for marts.

with comp_weekly as (
    -- Collapse competitor snapshots to weekly SKU benchmarks for stable price index comparisons.
    select
        snapshot_week,
        sku,
        min(competitor_price) as competitor_min_price,
        percentile_cont(0.5) within group (order by competitor_price) as competitor_median_price,
        count(distinct competitor_id) as competitor_count
    from {{ ref('stg_competitor_snapshots') }}
    group by 1, 2
),
internal_weekly as (
    -- Internal price benchmark uses weekly SKU average transaction price and excludes returns.
    select order_week as snapshot_week, sku, avg(transaction_price) as avg_transaction_price
    from {{ ref('int_sales_enriched') }}
    where not returned_flag
    group by 1, 2
)
select
    c.snapshot_week,
    c.sku,
    c.competitor_min_price,
    c.competitor_median_price,
    c.competitor_count,
    i.avg_transaction_price,
    -- Price indices measure internal price position versus competitor benchmarks.
    case when nullif(c.competitor_min_price, 0) is null then null else i.avg_transaction_price / nullif(c.competitor_min_price, 0) end as price_index_vs_comp_min,
    case when nullif(c.competitor_median_price, 0) is null then null else i.avg_transaction_price / nullif(c.competitor_median_price, 0) end as price_index_vs_comp_median
from comp_weekly c
left join internal_weekly i
    on c.snapshot_week = i.snapshot_week
    and c.sku = i.sku
