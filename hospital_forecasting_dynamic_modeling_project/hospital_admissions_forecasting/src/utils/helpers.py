"""
Helper utility functions
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime


def set_random_seeds(seed=42):
    """Set random seeds for reproducibility"""
    import random
    random.seed(seed)
    np.random.seed(seed)
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
    except ImportError:
        pass


def set_random_seed(seed=42):
    """Alias for set_random_seeds for backward compatibility"""
    set_random_seeds(seed)


def print_separator(title=""):
    """Print a visual separator with optional title"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"{'='*60}\n")


def validate_date_range(start_date, end_date):
    """Validate that start_date is before end_date"""
    if pd.to_datetime(start_date) >= pd.to_datetime(end_date):
        raise ValueError("start_date must be before end_date")
    return True


def get_project_root():
    """
    DEPRECATED: This function is no longer used. Local storage is not supported.
    This project requires Google Colab environment.
    
    Returns:
    --------
    str: Raises RuntimeError (local storage not supported)
    """
    raise RuntimeError(
        "get_project_root() is deprecated. This project requires Google Colab. "
        "Local storage is not supported. Please run notebooks in Colab."
    )


def is_colab():
    """
    Detect if running in Google Colab environment.
    
    Returns:
    --------
    bool: True if running in Colab, False otherwise
    """
    try:
        import sys
        return 'google.colab' in sys.modules or os.path.exists('/content')
    except:
        return False


def get_data_paths():
    """
    Get standardized data directory paths for Colab session storage.
    Creates directories if they don't exist.
    
    Returns:
    --------
    dict: Dictionary with keys:
        - 'project_root': Project root directory
        - 'data_dir': Main data directory
        - 'raw': Raw data directory
        - 'processed': Processed data directory
        - 'external': External data directory
        - 'storage_type': Always 'COLAB_SESSION'
    
    Raises:
    -------
    RuntimeError: If not running in Colab environment
    """
    if not is_colab():
        raise RuntimeError(
            "This project requires Google Colab environment. "
            "Local storage is not supported. Please run notebooks in Colab."
        )
    
    # Use Colab session storage only
    project_root = '/content/hospital_admissions_forecasting'
    data_dir = os.path.join(project_root, 'data')
    storage_type = 'COLAB_SESSION'
    
    # Create directory structure
    raw_dir = os.path.join(data_dir, 'raw')
    processed_dir = os.path.join(data_dir, 'processed')
    external_dir = os.path.join(data_dir, 'external')
    
    for dir_path in [data_dir, raw_dir, processed_dir, external_dir]:
        os.makedirs(dir_path, exist_ok=True)
    
    return {
        'project_root': project_root,
        'data_dir': data_dir,
        'raw': raw_dir,
        'processed': processed_dir,
        'external': external_dir,
        'storage_type': storage_type
    }


def print_data_paths_config():
    """
    Print standardized data path configuration.
    Use this in notebooks to display current path settings.
    """
    paths = get_data_paths()
    
    print("=" * 60)
    print("DATA PATH CONFIGURATION (COLAB SESSION STORAGE)")
    print("=" * 60)
    print(f"Project Root: {paths['project_root']}")
    print(f"Data Directory: {paths['data_dir']}")
    print(f"Raw Data: {paths['raw']}")
    print(f"Processed Data: {paths['processed']}")
    print(f"External Data: {paths['external']}")
    print("\n💡 Note: Colab session storage is ephemeral (lost when session ends).")
    print("   Upload data: from google.colab import files; files.upload()")
    print("   Download results: files.download('path/to/file')")
    print("=" * 60)


def load_raw_admissions(file_name='admissions.csv', fallback_to_clean=True):
    """
    Load raw admissions data from CSV file.
    
    Parameters:
    -----------
    file_name : str, default 'admissions.csv'
        Name of the admissions CSV file in raw data directory
    fallback_to_clean : bool, default True
        If True, try to load 'admissions_clean.csv' if main file not found
    
    Returns:
    --------
    pd.DataFrame: Admissions data with parsed dates
    """
    paths = get_data_paths()
    file_path = os.path.join(paths['raw'], file_name)
    
    if not os.path.exists(file_path) and fallback_to_clean:
        clean_file = os.path.join(paths['raw'], 'admissions_clean.csv')
        if os.path.exists(clean_file):
            file_path = clean_file
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Admissions file not found: {file_path}\n"
            f"Please run notebook 00_generate_mock_data.ipynb or 01_data_extraction.ipynb first."
        )
    
    df = pd.read_csv(file_path, parse_dates=['admittime'])
    if 'dischtime' in df.columns:
        df['dischtime'] = pd.to_datetime(df['dischtime'])
    
    return df


def load_daily_admissions(file_name='daily_admissions.csv'):
    """
    Load daily aggregated admissions time series.
    
    Parameters:
    -----------
    file_name : str, default 'daily_admissions.csv'
        Name of the daily admissions CSV file in processed data directory
    
    Returns:
    --------
    pd.DataFrame: Daily admissions time series with date index
    """
    paths = get_data_paths()
    file_path = os.path.join(paths['processed'], file_name)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Daily admissions file not found: {file_path}\n"
            f"Please run notebook 02_exploratory_analysis.ipynb first."
        )
    
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    return df


def load_daily_kpis(file_name='daily_kpis.csv'):
    """
    Load daily KPI data (admissions, discharges, bed occupancy, etc.).
    
    Parameters:
    -----------
    file_name : str, default 'daily_kpis.csv'
        Name of the KPI CSV file in processed data directory
    
    Returns:
    --------
    pd.DataFrame: Daily KPI data with date index, or None if file doesn't exist
    """
    paths = get_data_paths()
    file_path = os.path.join(paths['processed'], file_name)
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    return df


def load_features_data(file_name='admissions_with_features.csv'):
    """
    Load feature-engineered admissions data.
    
    Parameters:
    -----------
    file_name : str, default 'admissions_with_features.csv'
        Name of the features CSV file in processed data directory
    
    Returns:
    --------
    pd.DataFrame: Feature-engineered data with date index, or None if file doesn't exist
    """
    paths = get_data_paths()
    file_path = os.path.join(paths['processed'], file_name)
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    return df

