# Patients Table Usage Verification

## ✅ YES - We Use patients.csv.gz for Date Alignment

The notebook **correctly loads and uses** the `patients.csv.gz` file to align dates properly.

## Complete Flow (Cell 14 in `01_data_extraction.ipynb`)

### Step 1: Load Patients Table
```python
# Tries multiple locations:
- /data/raw/patients.csv.gz (Google Drive)
- /data/raw/patients.csv.gz (Local)
- /data/raw/patients.csv (Google Drive, uncompressed)
- /data/raw/patients.csv (Local, uncompressed)

patients_df = pd.read_csv(file_path, compression='gzip', low_memory=False)
```

### Step 2: Validate Required Columns
```python
required_cols = ['subject_id', 'anchor_year', 'anchor_year_group']
# Checks that all required columns exist in patients table
```

### Step 3: Join with Admissions
```python
patients_subset = patients_df[required_cols].copy()
admissions_with_anchor = admissions_clean.merge(
    patients_subset,
    on='subject_id',
    how='left'  # Left join - keeps all admissions even if patient not found
)
```

### Step 4: Calculate Aligned Dates
```python
# For each admission:
1. Calculate offset: year_offset = admittime_year - anchor_year
2. Parse anchor_year_group: "2014 - 2016" → 2014
3. Calculate real year: real_year = anchor_group_start + year_offset
4. Create aligned_date with real year
```

## What Gets Used from patients.csv.gz

| Column | Purpose | Example |
|--------|---------|---------|
| `subject_id` | Join key to link admissions with patients | 10000032 |
| `anchor_year` | Deidentified reference year | 2180 |
| `anchor_year_group` | Real year range for alignment | "2014 - 2016" |

## Verification

✅ **Loads patients table** from `/data/raw/patients.csv.gz`  
✅ **Joins on subject_id** to link admissions with patient anchor info  
✅ **Uses anchor_year** to calculate year offset  
✅ **Uses anchor_year_group** to map to real years  
✅ **Creates aligned_date** column with properly aligned dates  

## Expected Behavior

### If patients.csv.gz is found:
- ✅ Loads the table
- ✅ Joins with admissions
- ✅ Calculates aligned dates using anchor_year and anchor_year_group
- ✅ Reports alignment statistics

### If patients.csv.gz is NOT found:
- ⚠️ Prints warning message
- ⚠️ Falls back to using deidentified dates (sets `aligned_date = admittime`)
- ⚠️ Continues processing (doesn't fail)

## File Location

The notebook looks for `patients.csv.gz` in:
1. `/content/drive/MyDrive/hospital_admissions_forecasting/data/raw/patients.csv.gz` (Google Drive)
2. `/content/hospital_admissions_forecasting/data/raw/patients.csv.gz` (Local Colab)

**You mentioned you placed it in `/data/raw`** - make sure it's in one of these exact paths when running in Colab.

## Summary

**YES**, the notebook uses `patients.csv.gz` to align dates properly. The implementation:

1. ✅ Loads the patients table
2. ✅ Joins it with admissions on `subject_id`
3. ✅ Uses `anchor_year` and `anchor_year_group` to calculate real years
4. ✅ Creates `aligned_date` column with properly aligned dates

The alignment will only work if:
- `patients.csv.gz` is in the correct location (`/data/raw/`)
- The file contains `subject_id`, `anchor_year`, and `anchor_year_group` columns
- The admissions have matching `subject_id` values

If the patients table is missing, the code gracefully falls back to using deidentified dates.

