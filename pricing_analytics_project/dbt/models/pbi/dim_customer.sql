-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select customer_id, segment, region, channel, price_tier
from {{ ref('stg_customers') }}
