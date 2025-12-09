# Feature Usage Analysis Across Models

## Summary

This document analyzes which features are being used in each model and how they are selected.

## Feature Selection Process

### ARIMAX & SARIMAX Models

**Location:** `04c_arimax_models.ipynb`

**Process:**
1. **Load all features** from `features_for_arimax.csv` (all columns except 'admissions')
2. **Select top 15 features** using `SelectKBest` with `f_regression` scoring
3. **Scale features** using `StandardScaler`
4. **Use selected features** in ARIMAX/SARIMAX training

**Code:**
```python
# Load all features
exog_features = [col for col in arimax_features_data.columns if col != 'admissions']

# Select top 15 features
n_features_to_select = min(15, len(exog_features))
selector = SelectKBest(score_func=f_regression, k=n_features_to_select)
selector.fit(train_exog_aligned.values, train_data_aligned.values)

# Get selected features
selected_indices = selector.get_support(indices=True)
selected_features = [exog_features[i] for i in selected_indices]
```

**Current Output:**
- From notebook output: "✓ Using 5 exogenous features: ['day_of_year_sin', 'day_of_year_cos', 'is_weekend', 'is_holiday', 'is_holiday_weekend']"
- This suggests only 5 features are available in the loaded file
- All 5 are selected (since 5 < 15)

### LSTM Model

**Location:** `04e_lstm_models.ipynb`

**Process:**
1. **Load all features** from `features_for_lstm.csv` (all columns except 'admissions')
2. **Select top 20 features** using `SelectKBest` with `f_regression` scoring
3. **Scale features** using `MinMaxScaler`
4. **Use selected features** in LSTM training

**Code:**
```python
# Load all features
feature_cols = [col for col in features_data.columns if col != 'admissions']

# Select top 20 features
n_features_to_select = min(20, len(feature_cols))
selector = SelectKBest(score_func=f_regression, k=n_features_to_select)
selector.fit(X_features, y_target)

# Get selected features
selected_indices = selector.get_support(indices=True)
selected_features = [feature_cols[i] for i in selected_indices]
```

**Current Output:**
- From notebook output: "✓ Using 19 LSTM features: ['day_of_week_sin', 'day_of_week_cos', 'month_sin', 'month_cos', 'day_of_year_sin', 'day_of_year_cos', 'is_weekend', 'is_holiday', 'is_holiday_weekend', 'admissions_lag_1']... (+9 more)"
- 19 features are available and selected

### VAR Model

**Location:** `04d_var_model.ipynb`

**Process:**
- VAR model uses **multiple KPIs** (admissions, discharges, bed occupancy)
- **No feature selection** - uses all available KPIs
- Features are the KPIs themselves, not engineered features

## Available Features (from outputs)

### ARIMAX/SARIMAX Features (5 features):
1. `day_of_year_sin` - Seasonal pattern (sine)
2. `day_of_year_cos` - Seasonal pattern (cosine)
3. `is_weekend` - Weekend indicator
4. `is_holiday` - Holiday indicator
5. `is_holiday_weekend` - Holiday weekend indicator

### LSTM Features (19 features):
1. `day_of_week_sin` - Day of week (sine)
2. `day_of_week_cos` - Day of week (cosine)
3. `month_sin` - Month (sine)
4. `month_cos` - Month (cosine)
5. `day_of_year_sin` - Day of year (sine)
6. `day_of_year_cos` - Day of year (cosine)
7. `is_weekend` - Weekend indicator
8. `is_holiday` - Holiday indicator
9. `is_holiday_weekend` - Holiday weekend indicator
10. `admissions_lag_1` - Lag 1 feature
11. ... (+9 more features, likely lag features, rolling stats, etc.)

## Missing Features for Volatility Capture

Based on the forecast analysis showing the model struggles with volatility, the following features might be missing:

### Potentially Missing Features:
1. **Volatility features:**
   - `rolling_std_7` - 7-day rolling standard deviation
   - `rolling_std_30` - 30-day rolling standard deviation
   - `recent_volatility` - Recent volatility indicator

2. **Spike detection features:**
   - `is_spike` - Indicator for sudden spikes
   - `spike_magnitude` - Magnitude of recent spikes
   - `days_since_spike` - Days since last spike

3. **Trend features:**
   - `trend_7` - 7-day trend
   - `trend_30` - 30-day trend
   - `momentum` - Momentum indicator

4. **Zero-inflation features:**
   - `is_zero` - Zero indicator
   - `days_since_zero` - Days since last zero
   - `zero_count_7` - Count of zeros in last 7 days

## Recommendations

### 1. Add Feature Printing
Add code to print the actual selected features after selection:
```python
print(f"  Selected features: {selected_features}")
print(f"  Feature scores: {dict(zip(selected_features, selector.scores_[selected_indices]))}")
```

### 2. Verify Feature Engineering
Check `03_feature_engineering.ipynb` to ensure it creates:
- Lag features (admissions_lag_1, admissions_lag_7, etc.)
- Rolling statistics (rolling_mean_7, rolling_std_7, etc.)
- Volatility features
- Trend features

### 3. Increase Feature Selection
Consider increasing `n_features_to_select` if more features are available:
- ARIMAX: Currently 15, could increase if more features available
- LSTM: Currently 20, could increase if more features available

### 4. Add Volatility-Specific Features
If volatility features don't exist, add them in feature engineering:
- Rolling standard deviation
- Recent volatility indicators
- Spike detection features

## Next Steps

1. **Check feature engineering notebook** to see what features are actually created
2. **Add feature printing** to model notebooks to see which features are selected
3. **Verify feature availability** - ensure all expected features are in the CSV files
4. **Add volatility features** if missing from feature engineering

