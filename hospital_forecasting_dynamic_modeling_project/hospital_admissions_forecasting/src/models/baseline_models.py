"""
Baseline forecasting models for comparison
"""

import numpy as np
import pandas as pd


def naive_forecast(train_data, horizon):
    """
    Naive forecast: use the last observed value.
    
    Parameters:
    -----------
    train_data : array-like
        Training time series data (pandas Series, numpy array, or list)
    horizon : int
        Number of periods to forecast
    
    Returns:
    --------
    np.array
        Forecast values
    """
    # Handle pandas Series with iloc to avoid deprecation warnings
    if isinstance(train_data, pd.Series):
        last_value = train_data.iloc[-1]
    else:
        last_value = train_data[-1]
    return np.full(horizon, last_value)


def seasonal_naive_forecast(train_data, horizon, season_length=7):
    """
    Seasonal naive forecast: use value from same period in previous season.
    
    Parameters:
    -----------
    train_data : array-like
        Training time series data
    horizon : int
        Number of periods to forecast
    season_length : int
        Length of seasonal pattern (default: 7 for weekly)
    
    Returns:
    --------
    np.array
        Forecast values
    """
    if len(train_data) < season_length:
        # If not enough data, use naive forecast
        return naive_forecast(train_data, horizon)
    
    forecasts = []
    for i in range(horizon):
        # Use value from same position in previous season
        idx = len(train_data) - season_length + (i % season_length)
        # Handle pandas Series with iloc to avoid deprecation warnings
        if isinstance(train_data, pd.Series):
            forecasts.append(train_data.iloc[idx])
        else:
            forecasts.append(train_data[idx])
    
    return np.array(forecasts)


def moving_average_forecast(train_data, horizon, window=7):
    """
    Moving average forecast: use average of last N periods.
    
    Parameters:
    -----------
    train_data : array-like
        Training time series data
    horizon : int
        Number of periods to forecast
    window : int
        Window size for moving average (default: 7)
    
    Returns:
    --------
    np.array
        Forecast values
    """
    if len(train_data) < window:
        # If not enough data, use naive forecast
        return naive_forecast(train_data, horizon)
    
    # Handle pandas Series with iloc to avoid deprecation warnings
    if isinstance(train_data, pd.Series):
        avg = np.mean(train_data.iloc[-window:])
    else:
        avg = np.mean(train_data[-window:])
    return np.full(horizon, avg)

