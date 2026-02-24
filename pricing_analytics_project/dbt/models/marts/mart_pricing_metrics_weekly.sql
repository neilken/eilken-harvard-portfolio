-- dbt mart model. Builds analytics-ready business metrics at a reporting grain.

select
    order_week,
    sku,
    customer_id,
    category,
    product_family,
    segment,
    channel,
    -- Returned lines are zeroed out so weekly pricing metrics reflect sell-through behavior.
    sum(case when returned_flag then 0 else units end) as units,
    sum(case when returned_flag then 0 else revenue_line end) as revenue,
    sum(case when returned_flag then 0 else list_revenue_line end) as list_revenue,
    sum(case when returned_flag then 0 else (list_revenue_line - revenue_line) end) as discount_amount,
    -- Price realization is net revenue divided by list revenue at the reporting grain.
    case when nullif(sum(case when returned_flag then 0 else list_revenue_line end), 0) is null then null
         else sum(case when returned_flag then 0 else revenue_line end) / nullif(sum(case when returned_flag then 0 else list_revenue_line end), 0)
    end as price_realization_pct,
    sum(case when returned_flag then 0 else gross_profit_line end) as gross_profit,
    -- Gross margin percent is computed after aggregation to avoid averaging line-level ratios.
    case when nullif(sum(case when returned_flag then 0 else revenue_line end), 0) is null then null
         else sum(case when returned_flag then 0 else gross_profit_line end) / nullif(sum(case when returned_flag then 0 else revenue_line end), 0)
    end as gross_margin_pct,
    -- This flag makes downstream filtering explicit instead of inferring null meaning.
    case when nullif(sum(case when returned_flag then 0 else revenue_line end), 0) is null then false else true end as gross_margin_pct_is_defined,
    -- Null margin percent is expected when the aggregated non-return revenue is zero.
    case
        when nullif(sum(case when returned_flag then 0 else revenue_line end), 0) is null then 'zero_revenue_after_returns'
        else null
    end as gross_margin_pct_null_reason,
    sum(case when returned_flag then 0 else contribution_profit_line end) as contribution_profit
from {{ ref('int_sales_enriched') }}
group by 1,2,3,4,5,6,7
