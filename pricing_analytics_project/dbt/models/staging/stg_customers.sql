-- dbt staging model. Cleans and types raw source data for downstream joins and metrics.

select
    customer_id,
    lower(segment) as segment,
    region,
    lower(channel) as channel,
    upper(price_tier) as price_tier
from {{ source('raw', 'customers') }}
