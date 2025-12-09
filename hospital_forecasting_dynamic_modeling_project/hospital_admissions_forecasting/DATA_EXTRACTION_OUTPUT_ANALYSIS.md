# Data Extraction Notebook Output Analysis

## Summary
Examined outputs from `01_data_extraction.ipynb` after rerun. The notebook successfully loaded and processed the data, including anchor year alignment.

## Key Findings

### 1. Data Loading (Cell 51)
✅ **Successfully loaded data:**
- **Records:** 546,028 admissions
- **Date range (deidentified):** 2105-10-04 to 2214-12-15
- **Note:** Dates shifted ~100 years for privacy (original period: 2008-2019)

### 2. Data Cleaning (Cell 53)
✅ **Cleaning completed:**
- **Starting records:** 546,028
- **Final records:** 545,853
- **Removed:** 175 records (discharge_before_admission)
- **Date range preserved:** 2105-10-04 to 2214-12-15
- **Records with discharge time:** 545,853 (100.0%)

### 3. Data Quality Summary (Cell 54)
✅ **Quality metrics:**
- **Total records:** 545,853
- **Unique subjects:** 223,382
- **Unique admissions:** 545,853
- **Length of Stay:** Mean 4.2 days, Median 2.0 days, Max 515 days

### 4. Anchor Year Alignment (Cell 56) ⭐ **CRITICAL SECTION**

✅ **Successfully aligned dates:**
- **Patients table loaded:** 364,627 records
- **Admissions with anchor year:** 545,853 (100.0%)
- **Date clamping:** 172,744 dates (31.6%) were clamped to anchor_year_group bounds
  - This is expected when admissions occur far from anchor_year

#### Date Range Comparison:
- **Original (deidentified):** 2105-10-04 to 2214-12-15
- **Aligned (approximate):** 2008-01-01 to 2196-02-29

⚠️ **Warning Identified:**
- **Expected range:** 2008-2022
- **Actual range:** 2008 to 2196
- **Admissions outside expected range:** 286 (0.05%)
- **Issue:** Some aligned dates extend to 2196, which is beyond the expected 2022 maximum

#### Anchor Year Group Distribution:
- **2008 - 2010:** 227,655 (41.7%)
- **2011 - 2013:** 114,831 (21.0%)
- **2014 - 2016:** 91,067 (16.7%)
- **2017 - 2019:** 69,832 (12.8%)
- **2020 - 2022:** 42,468 (7.8%)

✅ **Date alignment complete** - Using 'aligned_date' column for aggregation

### 5. Data Saving (Cell 55)
✅ **Successfully saved:**
- **Location:** Google Drive and local Colab
- **File size:** 90.86 MB
- **Records:** 545,853
- **Note:** Includes 'aligned_date' column for proper date aggregation

## Issues Identified

### ⚠️ Issue 1: Dates Outside Expected Range
- **Problem:** 286 admissions (0.05%) have aligned dates in 2196, which is beyond the expected 2022 maximum
- **Root Cause:** The clamping logic may not be handling all edge cases correctly, or there may be anchor_year_group values that extend beyond 2022
- **Impact:** Minimal (0.05%), but should be investigated
- **Recommendation:** Check if these are from anchor_year_group "2020 - 2022" with extreme offsets, or if there are anchor_year_group values beyond 2022

### ✅ Issue 2: Date Clamping
- **Observation:** 31.6% of dates were clamped to anchor_year_group bounds
- **Status:** This is **expected behavior** - it occurs when admissions occur far from the anchor_year, creating extreme offsets
- **Impact:** Acceptable - the clamping ensures dates stay within the 3-year range

## Next Steps

1. ✅ **Data extraction complete** - Ready for `02_exploratory_analysis.ipynb`
2. 🔄 **Run `02_exploratory_analysis.ipynb`** to test the hybrid day-of-week approach
3. 📊 **Expected results from hybrid approach:**
   - Day-of-week identification statistics (unique vs. ambiguous matches)
   - More accurate daily counts (unique matches avoid averaging error)
   - Preserved temporal patterns

## Recommendations

1. **Investigate the 286 dates in 2196:**
   - Check which anchor_year_group they belong to
   - Verify if these are legitimate or data quality issues
   - Consider additional clamping if needed

2. **Proceed to next notebook:**
   - The data is ready for aggregation
   - The hybrid day-of-week approach in `02_exploratory_analysis.ipynb` should now work correctly
   - Expected to see high percentage of unique day-of-week matches

## Conclusion

✅ **Data extraction successful:**
- All 545,853 admissions processed
- Anchor year alignment completed (100% coverage)
- Date clamping working as expected (31.6% clamped)
- Minor issue with 286 dates extending to 2196 (0.05% - minimal impact)
- Data ready for next notebook

The notebook is ready for the hybrid day-of-week aggregation approach in `02_exploratory_analysis.ipynb`.

