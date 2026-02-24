-- dbt data test. Returns failing rows when an assertion is violated.

select *
from {{ ref('stg_sales_order_lines') }}
where transaction_price < 0
   or list_price < 0
   or transaction_price > list_price
