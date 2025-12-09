"""
Generate mock MIMIC-IV admissions data for testing and development
This creates realistic synthetic data matching MIMIC-IV structure while waiting for actual access.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# Define data path (can be overridden)
# This allows the script to work standalone
if __name__ == '__main__':
    # Get the project root (two levels up from scripts/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_RAW_PATH = os.path.join(project_root, 'data', 'raw')
else:
    # When imported, DATA_RAW_PATH should be provided by caller
    DATA_RAW_PATH = None


def generate_mock_admissions(
    start_date='2008-01-01',
    end_date='2019-12-31',
    avg_daily_admissions=120,
    seed=42
):
    """
    Generate mock MIMIC-IV admissions data with realistic patterns.
    
    Parameters:
    -----------
    start_date : str
        Start date for admissions (YYYY-MM-DD)
    end_date : str
        End date for admissions (YYYY-MM-DD)
    avg_daily_admissions : int
        Average number of admissions per day
    seed : int
        Random seed for reproducibility
    
    Returns:
    --------
    pd.DataFrame
        Mock admissions data matching MIMIC-IV structure
    """
    np.random.seed(seed)
    
    # Convert dates
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    date_range = pd.date_range(start=start, end=end, freq='D')
    total_days = len(date_range)
    
    # Calculate total admissions (with some variation)
    total_admissions = int(avg_daily_admissions * total_days * np.random.uniform(0.95, 1.05))
    
    # Generate admission times with realistic patterns
    admissions = []
    
    # Admission types distribution (realistic proportions)
    admission_types = ['EMERGENCY', 'URGENT', 'ELECTIVE', 'NEWBORN', 'OBSERVATION']
    admission_type_probs = [0.45, 0.15, 0.25, 0.10, 0.05]
    
    # Admission locations
    admission_locations = [
        'EMERGENCY ROOM', 'PHYSICIAN REFERRAL', 'CLINIC REFERRAL',
        'HMO REFERRAL', 'TRANSFER FROM HOSPITAL', 'TRANSFER FROM SKILLED NURSING FACILITY',
        'TRANSFER FROM OTHER HEALTH FACILITY', 'TRANSFER FROM CRITICAL ACCESS HOSPITAL',
        'PHYSICIAN REFERRAL/NORMAL DELIVERY', 'CLINIC REFERRAL/NORMAL DELIVERY'
    ]
    
    # Discharge locations
    discharge_locations = [
        'HOME', 'HOME HEALTH CARE', 'REHAB/DISTINCT PART HOSP',
        'SKILLED NURSING FACILITY', 'DEAD/EXPIRED', 'HOME WITH HOME IV PROVIDER',
        'HOSPICE-MEDICAL FACILITY', 'HOSPICE-HOME', 'LEFT AGAINST MEDICAL ADICE',
        'OTHER FACILITY', 'SHORT TERM HOSPITAL'
    ]
    
    # Insurance types
    insurance_types = ['Medicare', 'Medicaid', 'Private', 'Self Pay', 'Government']
    insurance_probs = [0.35, 0.25, 0.30, 0.05, 0.05]
    
    # Languages
    languages = ['ENGLISH', 'SPANISH', 'PORTUGUESE', 'CHINESE', 'OTHER', 'UNKNOWN']
    language_probs = [0.85, 0.05, 0.02, 0.02, 0.04, 0.02]
    
    # Religions
    religions = ['UNOBTAINABLE', 'NOT SPECIFIED', 'CATHOLIC', 'PROTESTANT QUAKER',
                'JEWISH', 'EPISCOPALIAN', 'CHRISTIAN SCIENTIST', 'METHODIST',
                'GREEK ORTHODOX', 'OTHER']
    
    # Marital status
    marital_statuses = ['MARRIED', 'SINGLE', 'DIVORCED', 'WIDOWED', 'UNKNOWN (DEFAULT)']
    marital_probs = [0.40, 0.30, 0.10, 0.15, 0.05]
    
    # Ethnicity
    ethnicities = ['WHITE', 'BLACK/AFRICAN AMERICAN', 'HISPANIC OR LATINO',
                  'ASIAN', 'OTHER', 'UNKNOWN/NOT SPECIFIED']
    ethnicity_probs = [0.55, 0.15, 0.15, 0.08, 0.05, 0.02]
    
    # Generate admissions with realistic patterns
    subject_id_counter = 20000000  # Start with realistic MIMIC subject_id range
    hadm_id_counter = 20000000
    
    for i in range(total_admissions):
        # Select a random date with day-of-week and seasonal patterns
        days_from_start = np.random.randint(0, total_days)
        base_date = date_range[days_from_start]
        
        # Day of week effect (fewer on weekends)
        day_of_week = base_date.dayofweek
        if day_of_week in [5, 6]:  # Weekend
            if np.random.random() > 0.7:  # 30% chance to skip weekend
                continue
        
        # Monthly/seasonal effect (higher in winter months)
        month = base_date.month
        seasonal_factor = 1.0
        if month in [11, 12, 1, 2]:  # Winter/flu season
            seasonal_factor = 1.15
        elif month in [6, 7, 8]:  # Summer
            seasonal_factor = 0.90
        
        # Apply seasonal adjustment
        if np.random.random() > seasonal_factor / 1.2:
            continue
        
        # Generate admission time (more during day, fewer at night)
        # Probabilities for each hour (will be normalized)
        hour_weights = [0.02, 0.02, 0.02, 0.02, 0.02, 0.03, 0.04, 0.05,  # 0-7: low
                       0.06, 0.07, 0.08, 0.08, 0.07, 0.06, 0.06, 0.06,  # 8-15: high
                       0.06, 0.06, 0.06, 0.05, 0.04, 0.03, 0.03, 0.03]  # 16-23: medium
        hour_probs = np.array(hour_weights) / np.sum(hour_weights)  # Normalize to sum to 1.0
        hour = np.random.choice(range(24), p=hour_probs)
        minute = np.random.randint(0, 60)
        second = np.random.randint(0, 60)
        
        admittime = base_date.replace(hour=hour, minute=minute, second=second)
        
        # Generate length of stay (realistic distribution)
        # Most stays are short, but some are longer
        los_days = np.random.exponential(scale=3.5)
        los_days = max(0, min(int(los_days), 365))  # Cap at 1 year
        
        # Some patients have very short stays (same day)
        if np.random.random() < 0.15:
            los_days = 0
        
        dischtime = admittime + timedelta(days=los_days)
        
        # Ensure discharge is within date range
        if dischtime > end:
            dischtime = end - timedelta(hours=np.random.randint(1, 23))
            los_days = (dischtime - admittime).days
        
        # Select admission type
        admission_type = np.random.choice(admission_types, p=admission_type_probs)
        
        # ED registration times (for emergency admissions)
        edregtime = None
        edouttime = None
        if admission_type == 'EMERGENCY' and np.random.random() < 0.8:
            # ED visit before admission
            ed_arrival = admittime - timedelta(hours=np.random.uniform(0.5, 4))
            edregtime = ed_arrival
            edouttime = admittime
        
        # Hospital expire flag (mortality rate ~2-3%)
        hospital_expire_flag = 1 if np.random.random() < 0.025 else 0
        
        # If expired, adjust discharge time
        if hospital_expire_flag:
            dischtime = admittime + timedelta(days=min(los_days, np.random.randint(1, 30)))
        
        # Create admission record
        admission_record = {
            'subject_id': subject_id_counter,
            'hadm_id': hadm_id_counter,
            'admittime': admittime,
            'dischtime': dischtime,
            'admission_type': admission_type,
            'admission_location': np.random.choice(admission_locations),
            'discharge_location': np.random.choice(discharge_locations) if not hospital_expire_flag else 'DEAD/EXPIRED',
            'insurance': np.random.choice(insurance_types, p=insurance_probs),
            'language': np.random.choice(languages, p=language_probs),
            'religion': np.random.choice(religions),
            'marital_status': np.random.choice(marital_statuses, p=marital_probs),
            'ethnicity': np.random.choice(ethnicities, p=ethnicity_probs),
            'edregtime': edregtime,
            'edouttime': edouttime,
            'hospital_expire_flag': hospital_expire_flag
        }
        
        admissions.append(admission_record)
        
        # Increment counters
        subject_id_counter += np.random.randint(1, 5)  # Not every ID is used
        hadm_id_counter += 1
        
        # Progress indicator
        if (i + 1) % 10000 == 0:
            print(f"Generated {i+1:,} / {total_admissions:,} admissions...")
    
    # Create DataFrame
    df = pd.DataFrame(admissions)
    
    # Sort by admission time
    df = df.sort_values('admittime').reset_index(drop=True)
    
    # Add some missing values (realistic data has missing values)
    # 5% missing for optional fields
    optional_fields = ['language', 'religion', 'marital_status', 'edregtime', 'edouttime']
    for field in optional_fields:
        missing_mask = np.random.random(len(df)) < 0.05
        df.loc[missing_mask, field] = None
    
    print(f"\nGenerated {len(df):,} admission records")
    print(f"Date range: {df['admittime'].min()} to {df['admittime'].max()}")
    print(f"Average daily admissions: {len(df) / total_days:.1f}")
    
    return df


def main(output_path=None):
    """Generate and save mock MIMIC-IV admissions data"""
    print("="*60)
    print("Generating Mock MIMIC-IV Admissions Data")
    print("="*60)
    print("\nNote: This is synthetic data for development/testing purposes.")
    print("Actual MIMIC-IV data should be used for final analysis.\n")
    
    # Generate data
    mock_data = generate_mock_admissions(
        start_date='2008-01-01',
        end_date='2019-12-31',
        avg_daily_admissions=120,
        seed=42
    )
    
    # Determine output path
    if output_path is None:
        if DATA_RAW_PATH is None:
            # Fallback: use current directory/data/raw
            output_path = os.path.join('data', 'raw')
        else:
            output_path = DATA_RAW_PATH
    
    os.makedirs(output_path, exist_ok=True)
    
    # Save to CSV
    output_file = os.path.join(output_path, 'admissions.csv')
    mock_data.to_csv(output_file, index=False)
    
    file_size_mb = os.path.getsize(output_file) / (1024**2)
    print(f"\n✓ Saved mock data to: {output_file}")
    print(f"  File size: {file_size_mb:.2f} MB")
    print(f"  Records: {len(mock_data):,}")
    
    # Print summary statistics
    print("\n" + "="*60)
    print("Data Summary")
    print("="*60)
    print(f"\nDate range: {mock_data['admittime'].min()} to {mock_data['admittime'].max()}")
    print(f"Total records: {len(mock_data):,}")
    
    # Daily admissions summary
    daily_counts = mock_data.groupby(mock_data['admittime'].dt.date).size()
    print(f"\nDaily admissions statistics:")
    print(f"  Mean: {daily_counts.mean():.1f}")
    print(f"  Median: {daily_counts.median():.1f}")
    print(f"  Min: {daily_counts.min()}")
    print(f"  Max: {daily_counts.max()}")
    print(f"  Std: {daily_counts.std():.1f}")
    
    # Length of stay summary
    mock_data['length_of_stay'] = (
        pd.to_datetime(mock_data['dischtime']) - 
        pd.to_datetime(mock_data['admittime'])
    ).dt.days
    print(f"\nLength of stay statistics:")
    print(f"  Mean: {mock_data['length_of_stay'].mean():.1f} days")
    print(f"  Median: {mock_data['length_of_stay'].median():.1f} days")
    
    # Admission types
    print(f"\nAdmission types distribution:")
    print(mock_data['admission_type'].value_counts())
    
    print("\n" + "="*60)
    print("Mock data generation complete!")
    print("="*60)
    print(f"\nYou can now use this data in your notebooks.")
    print(f"Update notebook 01 to load from: {output_file}")


if __name__ == '__main__':
    main()

