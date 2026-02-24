-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select distinct competitor_id, competitor_id as competitor_name
from {{ ref('stg_competitor_snapshots') }}
