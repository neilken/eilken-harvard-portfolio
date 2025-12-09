"""
VAR (Vector Autoregression) model implementation for forecasting multiple KPIs
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.stattools import grangercausalitytests
import warnings
warnings.filterwarnings('ignore')


def train_var_model(kpi_dataframe, maxlags=7, ic='aic'):
    """
    Train a VAR model on multiple KPIs.
    
    Parameters:
    -----------
    kpi_dataframe : pd.DataFrame
        DataFrame with multiple KPI time series (columns are different KPIs)
    maxlags : int
        Maximum number of lags to consider
    ic : str
        Information criterion for lag selection ('aic', 'bic', 'fpe', 'hqic')
    
    Returns:
    --------
    VARResults
        Fitted VAR model
    """
    # Ensure data is stationary (or difference if needed)
    # For now, we'll assume data is prepared beforehand
    
    # Create VAR model
    var_model = VAR(kpi_dataframe)
    
    # Fit model with optimal lag selection
    var_fitted = var_model.fit(maxlags=maxlags, ic=ic, verbose=False)
    
    return var_fitted


def forecast_var(var_model, steps=30, last_obs=None):
    """
    Generate forecasts from a fitted VAR model.
    
    Parameters:
    -----------
    var_model : VARResults
        Fitted VAR model
    steps : int
        Number of steps ahead to forecast
    last_obs : array-like, optional
        Last observations to use for forecasting (if None, uses model's data)
        Can be DataFrame or numpy array with shape (k_ar, n_variables)
    
    Returns:
    --------
    np.ndarray
        Forecasted values (shape: steps x n_variables)
        Note: Returns numpy array - caller should create DataFrame with appropriate index and column names
    """
    if last_obs is None:
        last_obs = var_model.y[-var_model.k_ar:]
    
    # Convert to numpy array if DataFrame
    if isinstance(last_obs, pd.DataFrame):
        last_obs = last_obs.values
    
    # Ensure last_obs is numpy array
    last_obs = np.array(last_obs)
    
    # Generate forecast
    forecast = var_model.forecast(last_obs, steps=steps)
    
    return forecast


def test_granger_causality(var_model, kpi_dataframe, maxlag=7):
    """
    Test for Granger causality between KPIs.
    
    Parameters:
    -----------
    var_model : VARResults
        Fitted VAR model
    kpi_dataframe : pd.DataFrame
        Original KPI data
    maxlag : int
        Maximum lag to test
    
    Returns:
    --------
    dict
        Dictionary of causality test results
    """
    results = {}
    kpi_names = list(kpi_dataframe.columns)
    
    # Test each pair
    for i, cause in enumerate(kpi_names):
        for j, effect in enumerate(kpi_names):
            if cause != effect:
                test_data = kpi_dataframe[[cause, effect]]
                try:
                    gc_test = grangercausalitytests(test_data, maxlag=maxlag, verbose=False)
                    # Extract p-values for each lag
                    p_values = [gc_test[lag+1][0]['ssr_ftest'][1] 
                               for lag in range(maxlag)]
                    results[f"{cause} -> {effect}"] = {
                        'p_values': p_values,
                        'min_p_value': min(p_values),
                        'significant': min(p_values) < 0.05
                    }
                except:
                    pass  # Skip if test fails
    
    return results

