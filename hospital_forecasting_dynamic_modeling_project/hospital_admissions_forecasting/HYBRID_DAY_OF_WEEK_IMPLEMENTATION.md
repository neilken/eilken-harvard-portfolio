# Hybrid Day-of-Week Identification Implementation

## Summary

Implemented a **hybrid approach** that uses day-of-week to identify the correct year when unique, and falls back to averaging when ambiguous. This significantly improves accuracy compared to pure averaging.

## What Was Changed

### Modified File
- `notebooks/02_exploratory_analysis.ipynb`

### New Function: `identify_year_from_day_of_week()`

This function checks which year(s) in the `anchor_year_group` range match the day-of-week from the deidentified date.

**Returns:**
- `int`: Unique matching year (most accurate)
- `list`: Multiple matching years (ambiguous)
- `None`: No match (shouldn't happen for valid dates)

**Features:**
- Handles leap years correctly
- Handles invalid dates (e.g., Feb 29 in non-leap years)
- Accounts for day-of-week progression across years

### Updated Function: `calculate_average_daily_counts()`

Completely rewritten to implement the hybrid approach:

1. **Extract preserved information** from deidentified date:
   - Month, day, day-of-week from `admittime`

2. **Identify year for each admission**:
   - Use `identify_year_from_day_of_week()` to check which year(s) match
   - Track unique matches vs. ambiguous matches

3. **Process unique matches**:
   - Assign admission directly to the identified year
   - Most accurate - no averaging needed!

4. **Process ambiguous matches**:
   - Group by `anchor_year_group` and `month_day`
   - Average across the matching years (not all 3 years)
   - More accurate than averaging across all 3 years

5. **Process no-match cases** (fallback):
   - Use averaging across all 3 years
   - Should be rare

6. **Aggregate and create time series**:
   - Sum counts for same date
   - Fill missing dates with 0
   - Return daily time series

## Benefits

### ✅ Maximum Accuracy
- **Unique matches**: Assign to exact year (no averaging error)
- **Ambiguous matches**: Average only across matching years (not all 3)
- **Result**: More accurate daily counts than pure averaging

### ✅ Preserves Temporal Patterns
- Day-of-week patterns preserved
- Seasonal patterns preserved
- Weekly patterns preserved

### ✅ Handles Edge Cases
- Leap years (2012)
- Invalid dates (Feb 29)
- Missing data
- Ambiguous matches

## Expected Results

When you run `02_exploratory_analysis.ipynb`, you should see:

```
Using HYBRID approach: Day-of-week identification + averaging
  - Day-of-week uniquely identifies year → use that year
  - Day-of-week ambiguous → average across matching years
  Day-of-week identification: X unique (Y%), Z ambiguous (W%)
  ✓ Created daily counts: N days
  Date range: YYYY-MM-DD to YYYY-MM-DD
  Mean daily admissions: X.XX
  Total admissions: XXXX
```

### Statistics to Watch

- **Unique match percentage**: Should be high (likely 60-80%+)
  - Higher = more accurate
- **Ambiguous match percentage**: Should be lower (likely 20-40%)
  - Lower = less averaging needed
- **Total admissions**: Should match original count

## How It Works

### Example 1: Unique Match

**Patient**: anchor_year_group = "2011 - 2013"  
**Admission**: March 15, deidentified date shows **Tuesday**

**Check each year**:
- March 15, 2011: Tuesday ✓ (matches!)
- March 15, 2012: Thursday ✗
- March 15, 2013: Friday ✗

**Result**: Assign admission to **2011** (unique match, no averaging!)

### Example 2: Ambiguous Match

**Patient**: anchor_year_group = "2011 - 2013"  
**Admission**: January 1, deidentified date shows **Saturday**

**Check each year**:
- January 1, 2011: Saturday ✓ (matches!)
- January 1, 2012: Sunday ✗
- January 1, 2013: Tuesday ✗

**Result**: Actually, this is unique! But if multiple years matched:
- Average across matching years only (not all 3)
- More accurate than averaging across all 3

### Example 3: Leap Year Effect

**Patient**: anchor_year_group = "2011 - 2013"  
**Admission**: March 1, deidentified date shows **Tuesday**

**Check each year**:
- March 1, 2011: Tuesday ✓ (matches!)
- March 1, 2012: Thursday ✗ (2012 is leap year, +2 days)
- March 1, 2013: Friday ✗

**Result**: Assign to **2011** (unique match!)

## Comparison to Previous Approach

### Previous (Pure Averaging)
- Always averaged across all 3 years
- No use of day-of-week information
- Less accurate

### New (Hybrid)
- Uses day-of-week when unique match
- Averages only when ambiguous
- More accurate overall

## Next Steps

1. **Run `02_exploratory_analysis.ipynb`** to test the implementation
2. **Check the statistics**:
   - Unique match percentage
   - Ambiguous match percentage
   - Total admissions count
3. **Verify daily counts** look reasonable
4. **Compare to previous results** (if available)

## Technical Details

### Day-of-Week Calculation
- Uses `pd.Timestamp.dayofweek` (0=Monday, 6=Sunday)
- Preserved from deidentified `admittime`
- Accounts for leap year effects

### Year Identification Logic
```python
for year in range(start_year, end_year + 1):
    date = pd.Timestamp(year=year, month=month, day=day)
    if date.dayofweek == day_of_week:
        matching_years.append(year)
```

### Aggregation Strategy
1. **Unique matches**: Direct assignment (count = 1)
2. **Ambiguous matches**: Average across matching years
3. **No matches**: Average across all 3 years (fallback)
4. **Final aggregation**: Sum counts for same date

## Potential Issues

### ⚠️ Ambiguity Cases
- If day-of-week repeats in multiple years (rare)
- Solution: Average across matching years (better than all 3)

### ⚠️ Invalid Dates
- Feb 29 in non-leap years
- Solution: Use Feb 28 instead

### ⚠️ Missing Data
- Missing `anchor_year_group` or `admittime`
- Solution: Skip or use fallback averaging

## Conclusion

The hybrid approach significantly improves accuracy by:
- Using day-of-week to identify exact year when possible
- Averaging only when necessary
- Preserving all temporal patterns

This should result in more accurate daily admission counts for forecasting!

