-- dbt data test. Returns failing rows when an assertion is violated.

select
    order_id,
    line_id,
    count(*) as cnt
from {{ ref('stg_sales_order_lines') }}
group by 1, 2
having count(*) > 1
