-- dbt staging model. Cleans and types raw source data for downstream joins and metrics.

select
    sku,
    product_name,
    lower(category) as category,
    lower(product_family) as product_family,
    brand,
    lower(lifecycle_stage) as lifecycle_stage,
    cast(launch_date as date) as launch_date
from {{ source('raw', 'products') }}
