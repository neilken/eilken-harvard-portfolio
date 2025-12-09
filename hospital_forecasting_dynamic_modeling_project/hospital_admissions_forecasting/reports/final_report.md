# Hospital Patient Flow and Capacity Forecasting: A Time Series Analysis for Operational Optimization

**Course:** CSCI E-116 Dynamic Modeling and Forecasting in Big Data  
**Instructor:** William Yu  
**Date:** [Submission Date]

---

## 1. Introduction & Motivation

### 1.1 Problem Statement

Hospitals face significant challenges in managing patient flow and optimizing resource allocation. Inadequate forecasting of patient admissions leads to:

- Staffing inefficiencies (over-staffing during slow periods, under-staffing during peak periods)
- Bed capacity issues (patient wait times, overflow situations)
- Increased operational costs
- Reduced quality of care

### 1.2 Objectives

This project aims to:

1. Develop accurate forecasting models for daily hospital admissions
2. Enable data-driven capacity planning and resource allocation
3. Support operational decision-making through predictive analytics
4. Compare multiple forecasting approaches (ARIMA, LSTM, etc.)

### 1.3 Significance

Accurate admission forecasting helps hospitals:
- Optimize nurse and staff scheduling
- Plan for peak demand periods (flu season, holidays)
- Improve patient flow and reduce wait times
- Reduce operational costs through better resource utilization

---

## 2. Data Description

### 2.1 Data Source

**MIMIC-IV Database** (Medical Information Mart for Intensive Care)
- Source: Beth Israel Deaconess Medical Center (BIDMC)
- Period: 2008-2019
- Records: 400,000+ hospital admissions
- Data type: De-identified EMR/EHR-derived data

### 2.2 Variables

- **Admission timestamps:** Date and time of hospital admission
- **Discharge timestamps:** Date and time of discharge
- **Departments:** ICU, ED, Medical, Surgical (if available)
- **Demographics:** Age, gender (for potential features)

### 2.3 Data Processing

- Individual admission records aggregated to daily counts
- Missing dates handled (filled with zeros or interpolated)
- Data quality checks performed (outliers, missing values)

### 2.4 Final Dataset

- **Time series:** Daily admission counts
- **Date range:** [To be filled]
- **Total observations:** [To be filled]
- **Average daily admissions:** [To be filled]

---

## 3. Exploratory Data Analysis

### 3.1 Time Series Overview

[Time series plot will be inserted here]

### 3.2 Trend Analysis

[Trend analysis description]

### 3.3 Seasonality Patterns

#### Day of Week Patterns
[Day of week plot and analysis]

#### Monthly Patterns
[Monthly pattern plot and analysis]

### 3.4 Stationarity Analysis

- **ADF Test:** [Results]
- **KPSS Test:** [Results]
- **Conclusion:** [Stationary/Non-stationary, differencing requirements]

### 3.5 Key Patterns Identified

1. [Pattern 1]
2. [Pattern 2]
3. [Pattern 3]

---

## 4. Methodology

### 4.1 Models Selected

1. **Baseline Models:**
   - Naive Forecast
   - Seasonal Naive (weekly seasonality)
   - Moving Average

2. **ARIMA/SARIMA:**
   - Classic time series approach
   - Handles seasonal patterns
   - Parameter selection via ACF/PACF analysis

3. **VAR (Vector Autoregression):**
   - Multi-KPI forecasting (admissions, discharges, bed occupancy)
   - Captures relationships between operational metrics
   - Demonstrates advanced multivariate time series modeling
   - Lag selection via information criteria (AIC/BIC)
   - Granger causality tests to identify relationships between KPIs

### 4.2 Feature Engineering

- **Temporal features:** Day of week, month, holidays
- **Lag features:** Previous 1, 7, 30 days
- **Rolling statistics:** 7-day and 30-day moving averages
- **KPI features:** Bed occupancy, discharge rates, average length of stay (if available)
- **[External features if used]**

### 4.3 Train-Test Split

- **Training period:** [80% of data - earlier period]
- **Test period:** [20% of data - later period]
- **Rationale:** Preserve temporal order, use most recent data for testing

### 4.4 Cross-Validation

- **Method:** Time series cross-validation (rolling window)
- **Strategy:** [Describe CV approach]
- **Folds:** [Number of folds]

### 4.5 Evaluation Metrics

- **RMSE** (Root Mean Squared Error)
- **MAE** (Mean Absolute Error)
- **MAPE** (Mean Absolute Percentage Error) - primary metric for interpretability
- **R²** (Coefficient of determination)

---

## 5. Results

### 5.1 Model Performance Comparison

| Model | RMSE | MAE | MAPE | R² |
|-------|------|-----|------|-----|
| Naive Baseline | [Value] | [Value] | [Value]% | [Value] |
| Seasonal Naive | [Value] | [Value] | [Value]% | [Value] |
| Moving Average | [Value] | [Value] | [Value]% | [Value] |
| ARIMA/SARIMA | [Value] | [Value] | [Value]% | [Value] |
| LSTM | [Value] | [Value] | [Value]% | [Value] |
| VAR (Multi-KPI) | [Value] | [Value] | [Value]% | [Value] |

### 5.2 Best Model Selection

**Selected Model:** [Model name]

**Justification:**
- Best performance on [primary metric]
- Good balance of accuracy and interpretability
- Robust to [specific characteristics]

### 5.3 Forecast Visualization

[Forecast vs actual plot will be inserted here]

### 5.4 Out-of-Sample Performance

- **Test set RMSE:** [Value]
- **Test set MAPE:** [Value]%
- **Training vs Test:** [Comparison showing no overfitting]

### 5.5 KPI Forecasts

If VAR model was used, present forecasts for:
- **Daily Admissions:** [Forecast summary]
- **Daily Discharges:** [Forecast summary]
- **Bed Occupancy Rate:** [Forecast summary]

**Derived Operational KPIs:**
- **Staffing Requirements:** [Calculated from admission forecasts]
- **Capacity Utilization:** [Forecasted occupancy vs capacity]

---

## 6. Discussion & Insights

### 6.1 Key Findings

1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

### 6.2 Business Implications

#### Staffing Optimization
- Forecasting enables proactive nurse scheduling
- Derived KPIs provide specific staffing requirements (e.g., 68 nurses needed next week)
- Estimated cost savings: [X]% reduction in labor costs through optimized scheduling

#### Capacity Planning
- Peak period identification allows advance preparation
- Bed occupancy forecasts enable proactive bed management
- Multi-KPI forecasting (admissions + discharges) provides comprehensive capacity view
- Bed allocation can be optimized based on forecasts

#### Operational Efficiency
- Data-driven decision making using operational KPIs
- Improved patient flow management through discharge forecasting
- Capacity alerts when occupancy exceeds optimal thresholds (e.g., >85%)

### 6.3 Limitations

1. **Data scope:** Single hospital (BIDMC)
2. **External factors:** [Factors not included]
3. **Model assumptions:** [Assumptions made]
4. **Forecast horizon:** Limited to 30 days

### 6.4 Future Work

1. **Multi-hospital analysis:** Extend to multiple hospitals
2. **Department-level forecasting:** ICU, ED, surgery-specific models
3. **External factors:** Integrate weather, flu data, local events
4. **Real-time deployment:** Deploy model for operational use
5. **Hierarchical forecasting:** Hospital → Department → Unit levels

### 6.5 Conclusions

[Summary of key contributions and insights]

---

## 7. References

1. MIMIC-IV Database Documentation: https://mimic.mit.edu/
2. [Additional references]
3. [Class materials and notes]

---

## Appendix

### A. Additional Visualizations

[Additional plots and diagnostics]

### B. Model Diagnostics

[Residual plots, ACF of residuals, etc.]

### C. Code Availability

All code is available in the accompanying Jupyter notebooks:
- `01_data_extraction.ipynb`
- `02_exploratory_analysis.ipynb`
- `03_feature_engineering.ipynb`
- `04_model_development.ipynb`
- `05_model_evaluation.ipynb`
- `06_forecasting.ipynb`

