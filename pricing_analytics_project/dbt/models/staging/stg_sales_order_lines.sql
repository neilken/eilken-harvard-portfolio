-- dbt staging model. Cleans and types raw source data for downstream joins and metrics.

select
    order_id,
    line_id,
    cast(order_date as date) as order_date,
    sku,
    customer_id,
    cast(units as integer) as units,
    cast(list_price as numeric(12,2)) as list_price,
    cast(transaction_price as numeric(12,2)) as transaction_price,
    -- Preserve the source discount field and also recompute it from prices for consistency checks.
    cast(discount_pct as numeric(8,4)) as discount_pct_source,
    -- Flag rows where the source discount differs materially from the price-derived value.
    case
        when nullif(list_price, 0) is null then null
        else round(((list_price - transaction_price) / nullif(list_price, 0))::numeric, 4)
    end as discount_pct_recomputed,
    case
        when discount_pct is null then false
        when abs(discount_pct - ((list_price - transaction_price) / nullif(list_price, 0))) > 0.01 then true
        else false
    end as discount_pct_discrepancy_flag,
    coalesce(promo_flag, false) as promo_flag,
    nullif(promo_id, '') as promo_id,
    cast(cogs_unit as numeric(12,2)) as cogs_unit,
    cast(freight_unit as numeric(12,2)) as freight_unit,
    cast(payment_fees_unit as numeric(12,2)) as payment_fees_unit,
    coalesce(returned_flag, false) as returned_flag,
    -- Line-level monetary fields are reused heavily in intermediate and mart models.
    cast(transaction_price * units as numeric(14,2)) as revenue_line,
    cast(list_price * units as numeric(14,2)) as list_revenue_line,
    cast(cogs_unit * units as numeric(14,2)) as cogs_line
from {{ source('raw', 'sales_order_lines') }}
