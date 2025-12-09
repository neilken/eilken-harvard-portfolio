"""
Configuration settings for the hospital admissions forecasting project
"""

import os

# Project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_RAW_PATH = os.path.join(PROJECT_ROOT, 'data', 'raw')
DATA_PROCESSED_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed')
DATA_EXTERNAL_PATH = os.path.join(PROJECT_ROOT, 'data', 'external')
MODELS_PATH = os.path.join(PROJECT_ROOT, 'models')
RESULTS_PATH = os.path.join(PROJECT_ROOT, 'results')
REPORTS_PATH = os.path.join(PROJECT_ROOT, 'reports')

# Create directories if they don't exist
for path in [DATA_RAW_PATH, DATA_PROCESSED_PATH, DATA_EXTERNAL_PATH, MODELS_PATH, RESULTS_PATH, REPORTS_PATH]:
    os.makedirs(path, exist_ok=True)

# Model parameters
FORECAST_HORIZON = 30  # days
TRAIN_TEST_SPLIT = 0.8  # 80% train, 20% test

# Random seed for reproducibility
RANDOM_SEED = 42

# Date format
DATE_FORMAT = '%Y-%m-%d'

# Training speed optimization settings
# Set to True for faster training (reduced parameter search space)
# ULTRA_FAST: Set to True for ~2 minute training (very aggressive optimization)
ULTRA_FAST_TRAINING = True
FAST_TRAINING = ULTRA_FAST_TRAINING  # Backwards compatibility

# Skip SARIMA in ultra-fast mode (saves 1-2 minutes)
SKIP_SARIMA_IN_ULTRA_FAST = True

# ARIMA parameters (ultra-fast mode for ~2 min training)
if ULTRA_FAST_TRAINING:
    # Ultra-fast: Minimal search space + approximation methods
    ARIMA_MAX_P = 2  # Very reduced search space (4 combinations)
    ARIMA_MAX_Q = 2  # Very reduced search space
    ARIMA_N_JOBS = -1  # Use all CPU cores for parallel processing
    ARIMA_USE_APPROXIMATION = True  # Use faster approximation method
    ARIMA_METHOD = 'lbfgs'  # Faster optimizer
else:
    # Standard fast mode
    ARIMA_MAX_P = 3
    ARIMA_MAX_Q = 3
    ARIMA_N_JOBS = -1
    ARIMA_USE_APPROXIMATION = False
    ARIMA_METHOD = 'lbfgs'

# SARIMA parameters (ultra-fast mode - consider skipping SARIMA for speed)
if ULTRA_FAST_TRAINING:
    SARIMA_MAX_P = 1  # Minimal search space
    SARIMA_MAX_Q = 1  # Minimal search space
    SARIMA_MAX_P_SEASONAL = 1  # Minimal search space
    SARIMA_MAX_Q_SEASONAL = 1  # Minimal search space
    SARIMA_MAX_ORDER = 5  # Very reduced
    SARIMA_N_JOBS = -1  # Parallel processing
    SARIMA_USE_APPROXIMATION = True  # Use approximation
else:
    SARIMA_MAX_P = 2
    SARIMA_MAX_Q = 2
    SARIMA_MAX_P_SEASONAL = 1
    SARIMA_MAX_Q_SEASONAL = 1
    SARIMA_MAX_ORDER = 8
    SARIMA_N_JOBS = -1
    SARIMA_USE_APPROXIMATION = False

# VAR parameters
VAR_MAX_LAGS = 5  # Reduced from 7 for faster VAR training
VAR_IC = 'aic'  # Information criterion

