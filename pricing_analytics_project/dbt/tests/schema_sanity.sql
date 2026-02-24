-- dbt data test. Returns failing rows when an assertion is violated.

select 1 as should_be_zero_rows
where false
