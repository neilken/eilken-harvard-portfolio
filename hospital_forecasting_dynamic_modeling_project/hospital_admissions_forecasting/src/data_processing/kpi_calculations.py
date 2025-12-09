"""
Functions for calculating Key Performance Indicators (KPIs) from hospital admission data
"""

import pandas as pd
import numpy as np


def calculate_daily_discharges(admissions_df, discharge_column='dischtime'):
    """
    Calculate daily discharge counts from admission records.
    
    Parameters:
    -----------
    admissions_df : pd.DataFrame
        DataFrame containing individual admission records with discharge times
    discharge_column : str
        Name of the column containing discharge dates/timestamps
    
    Returns:
    --------
    pd.Series
        Daily discharge counts with datetime index
    """
    if discharge_column not in admissions_df.columns:
        return pd.Series(dtype=int)
    
    admissions_df = admissions_df.copy()
    admissions_df[discharge_column] = pd.to_datetime(admissions_df[discharge_column])
    
    # Extract date (remove time component)
    admissions_df['discharge_date'] = admissions_df[discharge_column].dt.date
    
    # Count discharges per day
    daily_discharges = admissions_df.groupby('discharge_date').size()
    
    # Convert to datetime index
    daily_discharges.index = pd.to_datetime(daily_discharges.index)
    daily_discharges = daily_discharges.sort_index()
    
    # Fill missing dates with zeros
    if len(daily_discharges) > 0:
        date_range = pd.date_range(start=daily_discharges.index.min(),
                                   end=daily_discharges.index.max(),
                                   freq='D')
        daily_discharges = daily_discharges.reindex(date_range, fill_value=0)
    
    return daily_discharges


def calculate_average_length_of_stay(admissions_df, 
                                     admission_column='admittime', 
                                     discharge_column='dischtime'):
    """
    Calculate average length of stay (ALOS) per day.
    
    Parameters:
    -----------
    admissions_df : pd.DataFrame
        DataFrame containing admission and discharge timestamps
    admission_column : str
        Name of admission timestamp column
    discharge_column : str
        Name of discharge timestamp column
    
    Returns:
    --------
    pd.Series
        Average length of stay per day (in days)
    """
    if discharge_column not in admissions_df.columns:
        return pd.Series(dtype=float)
    
    admissions_df = admissions_df.copy()
    admissions_df[admission_column] = pd.to_datetime(admissions_df[admission_column])
    admissions_df[discharge_column] = pd.to_datetime(admissions_df[discharge_column])
    
    # Calculate length of stay
    admissions_df['length_of_stay'] = (
        admissions_df[discharge_column] - admissions_df[admission_column]
    ).dt.days
    
    # Group by admission date and calculate average LOS
    admissions_df['admission_date'] = admissions_df[admission_column].dt.date
    daily_los = admissions_df.groupby('admission_date')['length_of_stay'].mean()
    
    # Convert to datetime index
    daily_los.index = pd.to_datetime(daily_los.index)
    daily_los = daily_los.sort_index()
    
    return daily_los


def calculate_bed_occupancy(daily_admissions, daily_discharges, 
                           initial_beds=500, initial_occupancy=0.75):
    """
    Calculate daily bed occupancy rate.
    
    Parameters:
    -----------
    daily_admissions : pd.Series
        Daily admission counts
    daily_discharges : pd.Series
        Daily discharge counts
    initial_beds : int
        Total number of beds available
    initial_occupancy : float
        Initial occupancy rate (0-1) to start calculation
    
    Returns:
    --------
    pd.Series
        Daily bed occupancy counts
    pd.Series
        Daily bed occupancy rates (0-1)
    """
    # Align dates
    date_range = pd.date_range(start=min(daily_admissions.index.min(), 
                                         daily_discharges.index.min() if len(daily_discharges) > 0 
                                         else daily_admissions.index.min()),
                               end=max(daily_admissions.index.max(),
                                      daily_discharges.index.max() if len(daily_discharges) > 0 
                                      else daily_admissions.index.max()),
                               freq='D')
    
    daily_admissions = daily_admissions.reindex(date_range, fill_value=0)
    daily_discharges = daily_discharges.reindex(date_range, fill_value=0)
    
    # Initialize bed occupancy
    initial_occupied = int(initial_beds * initial_occupancy)
    bed_occupancy = pd.Series(index=date_range, dtype=int)
    bed_occupancy.iloc[0] = initial_occupied
    
    # Calculate cumulative occupancy
    for i in range(1, len(date_range)):
        bed_occupancy.iloc[i] = (
            bed_occupancy.iloc[i-1] + 
            daily_admissions.iloc[i] - 
            daily_discharges.iloc[i]
        )
        # Ensure non-negative and not exceeding capacity
        bed_occupancy.iloc[i] = max(0, min(bed_occupancy.iloc[i], initial_beds))
    
    # Calculate occupancy rate
    bed_occupancy_rate = bed_occupancy / initial_beds
    
    return bed_occupancy, bed_occupancy_rate


def create_kpi_dataframe(daily_admissions, daily_discharges=None, 
                        bed_occupancy=None, avg_los=None):
    """
    Create a DataFrame with multiple KPIs for VAR modeling.
    
    Parameters:
    -----------
    daily_admissions : pd.Series
        Daily admission counts
    daily_discharges : pd.Series, optional
        Daily discharge counts
    bed_occupancy : pd.Series, optional
        Daily bed occupancy counts or rates
    avg_los : pd.Series, optional
        Average length of stay per day
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with all KPIs aligned by date
    """
    kpi_dict = {'admissions': daily_admissions}
    
    if daily_discharges is not None and len(daily_discharges) > 0:
        kpi_dict['discharges'] = daily_discharges
    
    if bed_occupancy is not None and len(bed_occupancy) > 0:
        kpi_dict['bed_occupancy'] = bed_occupancy
    
    if avg_los is not None and len(avg_los) > 0:
        kpi_dict['avg_length_of_stay'] = avg_los
    
    # Create DataFrame and align dates
    kpi_df = pd.DataFrame(kpi_dict)
    kpi_df = kpi_df.sort_index()
    
    # Forward fill missing values if needed
    kpi_df = kpi_df.ffill().fillna(0)
    
    return kpi_df


def derive_staffing_requirements(forecasted_admissions, staff_per_patient=1.5):
    """
    Derive staffing requirements from forecasted admissions.
    
    Parameters:
    -----------
    forecasted_admissions : pd.Series or array-like
        Forecasted daily admission counts
    staff_per_patient : float
        Staff-to-patient ratio (default: 1.5 nurses per patient)
    
    Returns:
    --------
    pd.Series
        Required staff counts
    """
    if isinstance(forecasted_admissions, pd.Series):
        staffing = forecasted_admissions * staff_per_patient
        return staffing.round().astype(int)
    else:
        return np.round(np.array(forecasted_admissions) * staff_per_patient).astype(int)

