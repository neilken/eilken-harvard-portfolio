"""
Functions for aggregating individual admission records into time series
"""

import pandas as pd
import numpy as np


def aggregate_to_daily(admissions_df, date_column='admittime'):
    """
    Aggregate individual admission records to daily counts.
    
    Parameters:
    -----------
    admissions_df : pd.DataFrame
        DataFrame containing individual admission records
    date_column : str
        Name of the column containing admission dates/timestamps
    
    Returns:
    --------
    pd.Series
        Daily admission counts with datetime index
    """
    # Ensure date column is datetime
    admissions_df = admissions_df.copy()
    admissions_df[date_column] = pd.to_datetime(admissions_df[date_column])
    
    # Extract date (remove time component)
    admissions_df['admission_date'] = admissions_df[date_column].dt.date
    
    # Count admissions per day
    daily_counts = admissions_df.groupby('admission_date').size()
    
    # Convert to datetime index
    daily_counts.index = pd.to_datetime(daily_counts.index)
    daily_counts = daily_counts.sort_index()
    
    # Fill missing dates with zeros
    date_range = pd.date_range(start=daily_counts.index.min(),
                               end=daily_counts.index.max(),
                               freq='D')
    daily_counts = daily_counts.reindex(date_range, fill_value=0)
    
    return daily_counts


def aggregate_to_weekly(daily_series):
    """Aggregate daily series to weekly counts"""
    return daily_series.resample('W').sum()


def aggregate_to_monthly(daily_series):
    """Aggregate daily series to monthly counts"""
    return daily_series.resample('M').sum()

