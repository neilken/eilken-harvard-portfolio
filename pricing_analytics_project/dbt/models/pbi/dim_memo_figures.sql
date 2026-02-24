-- Power BI import model. Exposes dashboard-ready dimensions or facts from marts and analysis outputs.

select *
from (
    values
        (
            'fig_top_discount_leakage',
            'Top Discount Leakage SKUs',
            'top_discount_leakage_skus.png',
            'memo/figures/top_discount_leakage_skus.png',
            'Leakage ranking chart for memo and dashboard cross-reference'
        ),
        (
            'fig_promo_incremental_gp',
            'Promo Incremental Gross Profit',
            'promo_incremental_gross_profit.png',
            'memo/figures/promo_incremental_gross_profit.png',
            'Promo effectiveness comparison chart'
        ),
        (
            'fig_elasticity_estimates_ci',
            'Elasticity Estimates with Confidence Intervals',
            'elasticity_estimates_ci.png',
            'memo/figures/elasticity_estimates_ci.png',
            'Elasticity model summary figure'
        ),
        (
            'fig_forecast_12_weeks',
            '12-Week Demand Forecast',
            'forecast_12_weeks.png',
            'memo/figures/forecast_12_weeks.png',
            'Forecast with interval band'
        ),
        (
            'fig_recommended_actions_counts',
            'Recommended Pricing Actions',
            'recommended_actions_counts.png',
            'memo/figures/recommended_actions_counts.png',
            'Action mix summary chart'
        )
) as t(
    figure_id,
    figure_title,
    file_name,
    relative_path,
    figure_description
)
