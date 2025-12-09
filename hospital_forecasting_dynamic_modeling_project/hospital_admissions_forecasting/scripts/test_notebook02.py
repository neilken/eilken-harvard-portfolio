"""
Test script to run notebook 02 exploratory analysis logic
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import sys
import os

# Import project modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from src.data_processing.aggregate import aggregate_to_daily

# Set paths
data_raw_path = os.path.join(project_root, 'data', 'raw')
data_processed_path = os.path.join(project_root, 'data', 'processed')
results_path = os.path.join(project_root, 'results', 'visualizations', 'eda_plots')
os.makedirs(results_path, exist_ok=True)
os.makedirs(data_processed_path, exist_ok=True)

print("=" * 60)
print("Testing Notebook 02: Exploratory Analysis")
print("=" * 60)

# Load cleaned data
admissions_file = os.path.join(data_raw_path, 'admissions_clean.csv')
if not os.path.exists(admissions_file):
    admissions_file = os.path.join(data_raw_path, 'admissions.csv')

if os.path.exists(admissions_file):
    df = pd.read_csv(admissions_file, parse_dates=['admittime'])
    if 'dischtime' in df.columns:
        df['dischtime'] = pd.to_datetime(df['dischtime'])
    print(f"✓ Loaded {len(df):,} admission records")
    print(f"Date range: {df['admittime'].min()} to {df['admittime'].max()}")
else:
    print(f"✗ File not found: {admissions_file}")
    exit(1)

# Aggregate to daily time series
print("\n=== Aggregating to Daily Time Series ===")
daily_admissions = aggregate_to_daily(df, date_column='admittime')
daily_admissions = daily_admissions.to_frame(name='admissions')

print(f"Daily time series created: {len(daily_admissions)} days")
print(f"Date range: {daily_admissions.index.min()} to {daily_admissions.index.max()}")
print(f"Average daily admissions: {daily_admissions['admissions'].mean():.2f}")
print(f"Total admissions: {daily_admissions['admissions'].sum():,}")

# Save aggregated time series
output_file = os.path.join(data_processed_path, 'daily_admissions.csv')
daily_admissions.to_csv(output_file)
print(f"\n✓ Saved to: {output_file}")

# Basic statistics
print("\n=== Summary Statistics ===")
print(daily_admissions['admissions'].describe())

print("\n" + "=" * 60)
print("✓ Notebook 02 test completed successfully!")
print("=" * 60)

