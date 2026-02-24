# Auto-Generated Quantified Findings

This file is generated from pipeline outputs and can be copied into the final memo draft.

### Pricing realization and leakage
- Top 10 leakage SKUs account for approximately $416,207 in discount leakage.
- Average gross margin across top leakage SKUs is 36.33%.
- Priority action: review discount guardrails and exception approvals for the highest leakage SKUs.

- SKU00076: $46,765 leakage
- SKU00377: $45,095 leakage
- SKU00138: $43,048 leakage
- SKU00272: $42,408 leakage
- SKU00195: $42,158 leakage

### Promotion effectiveness
- Promotions show mixed profitability outcomes after discounting.
- Highest incremental gross profit promotions:
- PROMO202503: $6,823
- PROMO202304: $-1,178
- PROMO202504: $-1,378
- Lowest incremental gross profit promotions:
- PROMO202408: $-24,473
- PROMO202308: $-22,442
- PROMO202508: $-21,001

### Elasticity summary
- Average estimated elasticity across modeled groups is 0.06.
- Most elastic group: exhaust (-0.22).
- Least elastic group: fuel (0.54).
- Recommendation: use smaller test increases for highly elastic groups and larger tests for less elastic groups.

### Forecast summary
- Average 12-week forecast volume is 1,134 units per week.
- Forecast trend from first to last projected week is 21.23%.
- Recommendation: sequence pricing and promotion changes with forecast uncertainty bands in mind.

### Inventory pricing actions
- Markdown actions: 167
- Hold actions: 132
- Increase actions: 101
- Median days of supply for markdown recommendations: 182.8 days.
- Recommendation: execute markdowns in waves and monitor realized margin versus guardrails.

### Scenario simulation
- Highest projected gross profit scenario: `plus_5_pct_selected_categories` (13.55% gross profit change, 4.88% revenue change).
- Recommendation: validate the top scenario with a controlled category-level pricing test before broad rollout.
