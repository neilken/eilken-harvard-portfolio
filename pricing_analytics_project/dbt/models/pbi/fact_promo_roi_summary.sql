-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select *
from {{ source('marts_analysis_outputs', 'analysis_promo_roi_summary') }}
