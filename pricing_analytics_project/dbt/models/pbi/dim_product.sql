-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select sku, product_name, category, product_family, brand, lifecycle_stage
from {{ ref('stg_products') }}
