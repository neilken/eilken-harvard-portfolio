# Hospital Bed Occupancy Forecasting

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comparative analysis of time series forecasting models for predicting weekly hospital bed occupancy at AdventHealth Orlando, using 197 weeks of data (July 2020 – April 2024).

**Course:** CSCI E-116 Dynamic Modeling and Forecasting in Big Data  
**Institution:** Harvard University Extension School  
**Date:** December 2025

---

## 🎯 Key Findings

| Model | MAE (%) | RMSE (%) | Bias (%) | Rank |
|-------|---------|----------|----------|------|
| **Structural State-Space** | **1.75** | **2.21** | **-0.04** | **1** |
| Seasonal Naive (Baseline) | 1.81 | 2.35 | -0.22 | 2 |
| LSTM | 1.97 | 2.31 | +0.47 | 3 |
| SARIMAX | 2.07 | 2.59 | -0.40 | 4 |
| VAR | 2.97 | 3.83 | +1.30 | 5 |

**Key Insight:** All models achieve < 3% error, but a simple "same week last year" baseline nearly matches sophisticated models—revealing that hospital occupancy is dominated by stable 52-week seasonality.

---

## 📁 Project Structure

```
hospital_occupancy_forecasting/
├── 📓 notebooks/           # Jupyter notebooks (run in order)
│   ├── 01a_data_extraction.ipynb
│   ├── 01b_data_preprocessing.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_feature_engineering.ipynb
│   ├── 04a_baseline_models.ipynb
│   ├── 04b_arimax_models.ipynb
│   ├── 04c_ssm_model.ipynb
│   ├── 04d_var_model.ipynb
│   ├── 04e_lstm_models.ipynb
│   ├── 05_model_evaluation.ipynb
│   └── 06_additional_theoretical_forecasting.ipynb
├── 📊 data/
│   ├── raw/                # Original HHS COVID-19 hospital data
│   ├── processed/          # Cleaned datasets and features
│   └── external/           # CDC flu data, NOAA weather data
├── 📈 models/              # Saved model artifacts (.pkl, .h5)
├── 📄 docs/                # Documentation and reports
│   ├── FINAL_REPORT.md
│   ├── PRESENTATION_SLIDES.md
│   └── *_DOCUMENTATION.md
├── 🖼️ results/             # Visualizations and evaluation outputs
├── 🔧 src/                 # Reusable Python modules
└── requirements.txt
```

---

## 🔄 Notebook Pipeline

The notebooks should be run **in order**. Each notebook builds on the outputs of previous ones.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA PREPARATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐     ┌───────────────────────┐                     │
│  │ 01a_data_extraction  │───▶│ 01b_data_preprocessing│                     │
│  │                      │     │                       │                     │
│  │ • Load HHS COVID-19  │     │ • Weekly aggregation  │                     │
│  │   hospital data      │     │ • Create KPIs         │                     │
│  │ • Fetch CDC flu data │     │ • Merge external data │                     │
│  │ • Fetch NOAA weather │     │ • Quality validation  │                     │
│  └──────────────────────┘     └───────────────────────┘                     │
│                                       │                                     │
│                                       ▼                                     │
│                         ┌───────────────────────┐                           │
│                         │      02_eda           │                           │
│                         │                       │                           │
│                         │ • Descriptive stats   │                           │
│                         │ • Trend/seasonality   │                           │
│                         │ • Stationarity tests  │                           │
│                         │ • Correlation analysis│                           │
│                         │ • Granger causality   │                           │
│                         └───────────────────────┘                           │
│                                       │                                     │
│                                       ▼                                     │
│                     ┌───────────────────────────┐                           │
│                     │  03_feature_engineering   │                           │
│                     │                           │                           │
│                     │ • Train/test split (80/20)│                           │
│                     │ • Temporal features       │                           │
│                     │ • Lag features            │                           │
│                     │ • Rolling statistics      │                           │
│                     │ • Feature selection       │                           │
│                     │   (111 → 36 features)     │                           │
│                     └───────────────────────────┘                           │
│                                       │                                     │
└───────────────────────────────────────┼─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────────────┐
│                           MODEL DEVELOPMENT                                 │
├───────────────────────────────────────┼─────────────────────────────────────┤
│                                       ▼                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ │
│  │04a_baseline│ │04b_arimax  │ │ 04c_ssm    │ │ 04d_var    │ │ 04e_lstm   │ │
│  │            │ │            │ │            │ │            │ │            │ │
│  │ Seasonal   │ │ SARIMAX    │ │ Structural │ │ Vector     │ │ LSTM       │ │
│  │ Naive      │ │ + exog     │ │ State-Space│ │ Autoregress│ │ Neural Net │ │
│  │ (52-week)  │ │ features   │ │ (Kalman)   │ │ (COVID %)  │ │            │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘ │
│        │              │              │              │              │        │
│        └──────────────┴──────────────┴──────────────┴──────────────┘        │
│                                       │                                     │
│                                       ▼                                     │
│                        ┌──────────────────────────┐                         │
│                        │   05_model_evaluation    │                         │
│                        │                          │                         │
│                        │ • Gather all metrics     │                         │
│                        │ • Compare models         │                         │
│                        │ • Rank by composite score│                         │
│                        │ • Generate visualizations│                         │
│                        └──────────────────────────┘                         │
│                                       │                                     │
│                                       ▼                                     │
│            ┌────────────────────────────────────────────────┐               │
│            │   06_additional_theoretical_forecasting        │               │
│            │                                                │               │
│            │ • Future forecasting with best model           │               │
│            │ • Staffing needs projection                    │               │
│            │ • Confidence intervals                         │               │
│            └────────────────────────────────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📓 Notebook Descriptions

### Stage 1: Data Preparation

| Notebook | Purpose | Key Outputs |
|----------|---------|-------------|
| **01a_data_extraction** | Load raw HHS hospital data, fetch CDC flu rates (Delphi Epidata API), fetch NOAA weather data | `weekly_occupancy.csv`, `flu_data.csv`, `weather_data.csv` |
| **01b_data_preprocessing** | Aggregate to weekly frequency, create KPIs (occupancy rate, COVID %), merge external data | `weekly_kpis.csv`, `weekly_occupancy_with_external.csv` |
| **02_eda** | Comprehensive exploratory analysis: descriptive stats, decomposition, stationarity tests, correlation, Granger causality | EDA visualizations, analysis findings |
| **03_feature_engineering** | Create 111 candidate features, apply systematic selection (constant, correlation, VIF, importance), reduce to 36 features | `occupancy_with_features.csv`, model-specific feature sets |

### Stage 2: Model Development

| Notebook | Model | Description |
|----------|-------|-------------|
| **04a_baseline_models** | Seasonal Naive (52-week) | Benchmark: uses same week from previous year |
| **04b_arimax_models** | SARIMAX | Seasonal ARIMA with exogenous regressors (ILI, weather, cyclical encodings) |
| **04c_ssm_model** | Structural State-Space | Unobserved components model with Kalman filter (trend + 52-week seasonality) |
| **04d_var_model** | VAR | Vector Autoregression jointly modeling bed occupancy + COVID patient % |
| **04e_lstm_models** | LSTM | Recurrent neural network for sequence prediction |

### Stage 3: Evaluation & Forecasting

| Notebook | Purpose |
|----------|---------|
| **05_model_evaluation** | Compare all models on test set (MAE, RMSE, MAPE, Bias), generate rankings |
| **06_additional_theoretical_forecasting** | Generate future forecasts with best model, project staffing needs |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Google Colab (recommended) or local Jupyter environment

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/hospital-occupancy-forecasting.git
cd hospital-occupancy-forecasting

# Install dependencies
pip install -r requirements.txt
```

### Running the Notebooks

**Option 1: Google Colab (Recommended)**
1. Upload notebooks to Google Colab
2. Mount Google Drive for persistent storage
3. Run notebooks in order (01a → 01b → 02 → 03 → 04a-e → 05 → 06)

**Option 2: Local Jupyter**
```bash
jupyter notebook
# Navigate to notebooks/ folder and run in order
```

---

## 📊 Data Sources

| Source | Data | Description |
|--------|------|-------------|
| **HHS** | Hospital Capacity | COVID-19 Reported Patient Impact and Hospital Capacity by Facility (healthdata.gov) |
| **CDC** | Flu Rates | FluView ILI rates via Delphi Epidata API (HHS Region 4 - Southeast) |
| **NOAA** | Weather | Climate Data Online - Orlando, FL temperature data |

**Target Hospital:** AdventHealth Orlando  
**Study Period:** July 19, 2020 – April 21, 2024 (197 weeks)  
**Target Variable:** Weekly average bed occupancy (~2,254 beds average)

---

## 📈 Model Details

### Rolling Forecast with Hybrid Retraining

All models are evaluated using a realistic deployment simulation:
- **Train/Test Split:** 80/20 (157 weeks train, 40 weeks test)
- **Forecast Horizon:** 4 weeks
- **Retraining:** Every 2 weeks + error-triggered (if MAE > 1.2× historical)
- **Expanding Window:** Each retrain includes all data up to current point

### Feature Engineering Highlights

- **111 → 36 features** through systematic selection
- **Data leakage prevention:** All features use `.shift(1)` or explicit lags
- **Model-specific feature sets:** ARIMAX (7), LSTM (14), VAR (7)

---

## 📄 Documentation

Detailed documentation for each notebook is available in `docs/`:

- `01a_data_extraction_DOCUMENTATION.md`
- `01b_data_preprocessing_DOCUMENTATION.md`
- `02_eda_DOCUMENTATION.md`
- `03_feature_engineering_DOCUMENTATION.md`
- `FINAL_REPORT.md` - Complete written report
- `PRESENTATION_SLIDES.md` - 10-slide presentation script

---

## 🏆 Results Summary

**Winner: Structural State-Space Model**
- 1.75% MAE (~41 beds average error)
- Near-zero bias (-0.04%)
- Directly models the dominant 52-week seasonality

**Key Insight:** Model complexity doesn't guarantee better forecasts. A simple "same week last year" baseline (1.81% MAE) nearly matches sophisticated deep learning approaches.

---

## 🔮 Future Work

- [ ] Additional features (ED admissions, scheduled surgeries)
- [ ] Ensemble methods for improved robustness
- [ ] Production pipeline with automated retraining
- [ ] Multi-hospital validation
- [ ] Longer forecast horizons (8-12 weeks)

---

## 📚 References

1. U.S. Department of Health and Human Services. COVID-19 Reported Patient Impact and Hospital Capacity. healthdata.gov.
2. Centers for Disease Control and Prevention. FluView Interactive. Delphi Epidata API.
3. National Oceanic and Atmospheric Administration. Climate Data Online.
4. Hyndman, R.J., & Athanasopoulos, G. (2021). Forecasting: Principles and Practice, 3rd ed. OTexts.
5. Harvey, A.C. (1990). Forecasting, Structural Time Series Models and the Kalman Filter. Cambridge.
6. Hochreiter, S., & Schmidhuber, J. (1997). Long Short-Term Memory. Neural Computation, 9(8).

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Harvard Extension School, CSCI E-116
- HHS for providing open hospital capacity data
- CDC and NOAA for external data sources

