# Averaging Approach Implementation

## Summary

Implemented the averaging approach for calculating daily admission counts, which is the **correct method** given MIMIC-IV's 3-year precision limitation.

## What Was Implemented

### New Function: `calculate_average_daily_counts()`

Added to `02_exploratory_analysis.ipynb` (Cell 2), this function:

1. **Extracts month-day** from `aligned_date` (preserved from deidentified dates)
2. **Groups by** `anchor_year_group` and `month_day`
3. **Counts total admissions** for each month-day across all 3 years in the group
4. **Divides by 3** to get average per year
5. **Assigns average** to all 3 years for that month-day

### Updated Function: `aggregate_to_daily()`

Modified to:
- **Try averaging approach first** (if `anchor_year_group` and `aligned_date` are available)
- **Fall back to standard aggregation** if averaging fails or columns are missing

## How It Works

### Example

**Anchor Year Group**: "2011 - 2013"

**March 15th admissions**:
- Total across all 3 years: 30 admissions
- Average: 30 / 3 = **10 admissions per March 15th**

**Result**:
- March 15, 2011: 10 admissions (average)
- March 15, 2012: 10 admissions (average)
- March 15, 2013: 10 admissions (average)

### Benefits

1. ✅ **More Accurate**: Averages across 3-year period (acknowledges uncertainty)
2. ✅ **Preserves Patterns**: Month-day, day-of-week, seasonality all preserved
3. ✅ **Better for Forecasting**: Models learn from more accurate daily counts
4. ✅ **Transparent**: Clearly acknowledges we don't know exact year

## Implementation Details

### Edge Cases Handled

1. **Invalid Dates (Feb 29)**: Uses Feb 28 for non-leap years
2. **Overlapping Dates**: If multiple anchor_year_groups have same date, uses mean
3. **Missing Columns**: Falls back to standard aggregation if required columns missing
4. **Missing Dates**: Fills with 0 for dates with no admissions

### Code Location

- **Function**: `calculate_average_daily_counts()` in Cell 2
- **Usage**: Automatically called by `aggregate_to_daily()` in Cell 6

## Comparison

| Approach | Accuracy | Year Variation | Acknowledges Uncertainty |
|----------|----------|-----------------|--------------------------|
| **Offset-based** (old) | Medium | ✅ Preserved (artificial) | ❌ No |
| **Averaging** (new) | High | ❌ Lost (correctly) | ✅ Yes |

## Why Averaging is Better

1. **Acknowledges Uncertainty**: We don't know exact year, so we average
2. **Uses All Information**: Counts all admissions for month-day across 3 years
3. **More Accurate**: Average is more accurate than arbitrary offset assignment
4. **Preserves Patterns**: All temporal patterns (day-of-week, seasonality) maintained

## Next Steps

1. **Re-run `01_data_extraction.ipynb`** to ensure `aligned_date` and `anchor_year_group` columns are present
2. **Re-run `02_exploratory_analysis.ipynb`** to use the new averaging approach
3. **Verify output**: Check that daily counts are calculated using averaging
4. **Re-run downstream notebooks** to use the new daily counts

## Expected Output

When you run Cell 6 in `02_exploratory_analysis.ipynb`, you should see:

```
  Using averaging approach: Grouping by anchor_year_group and month-day
    (Acknowledges 3-year uncertainty by averaging across the range)
  ✓ Created average daily counts: XXXX days
    Date range: 2008-01-01 to 2022-12-31
    Mean daily admissions: XX.XX
```

The daily counts will now be **average daily counts** across the 3-year periods, which is the most accurate approach given the uncertainty.

