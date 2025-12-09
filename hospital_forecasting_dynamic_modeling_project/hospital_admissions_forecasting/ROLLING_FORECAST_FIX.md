# Fix for Flat ARIMAX/SARIMAX Forecasts

## Problem
ARIMAX and SARIMAX models are producing flat (straight line) forecasts because they forecast all 877 days at once using `predict(n_periods=877)`. When forecasting that many steps ahead, ARIMA models converge to the unconditional mean, resulting in flat forecasts.

## Solution
Implement rolling window forecasts similar to the Enhanced LSTM approach:
- Forecast in smaller windows (30 days)
- Retrain periodically (every 90 days)
- Use known exogenous variables (day_of_week, is_weekend, is_holiday) for future dates

## Implementation
Replace the single-step forecast generation with a rolling window approach for both ARIMAX and SARIMAX models in notebook 04.

### Key Changes:
1. Replace `predict(n_periods=forecast_len)` with rolling windows
2. Add periodic retraining logic (can be skipped for now, but structure is there)
3. Use exogenous variables from test_exog for each window



