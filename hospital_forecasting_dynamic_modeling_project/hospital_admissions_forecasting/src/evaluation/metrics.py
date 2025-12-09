"""
Evaluation metrics for time series forecasting
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


def calculate_rmse(actual, predicted):
    """Calculate Root Mean Squared Error"""
    return np.sqrt(mean_squared_error(actual, predicted))


def calculate_mae(actual, predicted):
    """Calculate Mean Absolute Error"""
    return mean_absolute_error(actual, predicted)


def calculate_mape(actual, predicted):
    """Calculate Mean Absolute Percentage Error"""
    # Avoid division by zero
    mask = actual != 0
    if mask.sum() == 0:
        return np.nan
    return np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100


def calculate_r2(actual, predicted):
    """Calculate R-squared (coefficient of determination)"""
    return r2_score(actual, predicted)


def calculate_all_metrics(actual, predicted):
    """
    Calculate all evaluation metrics.
    
    Returns:
    --------
    dict
        Dictionary containing RMSE, MAE, MAPE, and R²
    """
    return {
        'RMSE': calculate_rmse(actual, predicted),
        'MAE': calculate_mae(actual, predicted),
        'MAPE': calculate_mape(actual, predicted),
        'R2': calculate_r2(actual, predicted)
    }


def print_metrics(metrics_dict):
    """Pretty print metrics dictionary"""
    print("\n=== Model Performance Metrics ===")
    for metric, value in metrics_dict.items():
        if metric == 'MAPE':
            print(f"{metric}: {value:.2f}%")
        elif metric == 'R2':
            print(f"{metric}: {value:.4f}")
        else:
            print(f"{metric}: {value:.2f}")

