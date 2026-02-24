-- dbt staging model. Cleans and types raw source data for downstream joins and metrics.

select
    cast(captured_at as timestamp) as captured_at,
    cast(snapshot_date as date) as snapshot_date,
    competitor_id,
    sku,
    cast(competitor_price as numeric(12,2)) as competitor_price,
    cast(competitor_shipping as numeric(12,2)) as competitor_shipping,
    coalesce(in_stock, true) as in_stock,
    coalesce(promo_flag, false) as promo_flag,
    url,
    cast(match_score as numeric(4,2)) as match_score,
    -- snapshot_week aligns competitor data to the same weekly grain used in marts and dashboard facts.
    date_trunc('week', snapshot_date)::date as snapshot_week
from {{ source('raw', 'competitor_snapshots') }}
