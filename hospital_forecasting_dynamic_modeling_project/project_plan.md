# Hospital Admissions Forecasting Project Plan

## Project Overview

**Title:** Hospital Patient Flow and Capacity Forecasting: A Time Series Analysis for Operational Optimization

**Goal:** Develop predictive models to forecast daily hospital admissions using historical EMR/EHR data, enabling data-driven capacity planning and resource allocation decisions.

**Data Source:** MIMIC-IV Database (Beth Israel Deaconess Medical Center)
- 400,000+ hospital admissions (2008-2019)
- De-identified EMR/EHR-derived data
- Admission/discharge timestamps, departments, diagnoses
- Access: Requires CITI training and data use agreement (1-2 weeks)

**Deliverables:**
1. Written Report (5-20 pages)
2. Python Jupyter Notebook with complete analysis
3. Optional: PowerPoint Presentation (10 slides, 10 minutes)

**Submission Deadline:** December 18, midnight (Canvas)

---

## Project Structure

```
hospital_admissions_forecasting/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/                      # MIMIC data (not submitted if >50MB)
│   ├── processed/                # Aggregated time series
│   └── external/                 # Weather, flu data (optional)
├── notebooks/
│   ├── 01_data_extraction.ipynb
│   ├── 02_exploratory_analysis.ipynb
│   ├── 03_feature_engineering.ipynb
│   ├── 04_model_development.ipynb
│   ├── 05_model_evaluation.ipynb
│   └── 06_forecasting.ipynb
├── src/                          # Reusable modules
│   ├── data_processing/
│   ├── features/
│   ├── models/
│   └── evaluation/
├── models/                       # Saved trained models
├── results/                      # Forecasts and visualizations
└── reports/
    ├── final_report.md
    └── presentation/             # Optional slides
```

---

## Phase 1: Data Acquisition & Preparation (Week 1-2)

### 1.1 MIMIC Database Access
- [ ] Register at https://mimic.mit.edu/
- [ ] Complete CITI training (Human Subjects Research) - ~2-3 hours
- [ ] Sign data use agreement
- [ ] Download MIMIC-IV database
- [ ] Set up database connection (PostgreSQL or CSV exports)

### 1.2 Data Extraction
**File:** `notebooks/01_data_extraction.ipynb`

Tasks:
- Load MIMIC admissions table
- Extract admission/discharge timestamps
- Load transfers table (bed movements, optional)
- Load patient demographics (if needed for features)
- Document data structure and date ranges
- Save raw data to `data/raw/`

**Key SQL/Queries:**
- Extract admission dates from `admissions` table
- Count records per day
- Identify date range: 2008-2019
- Check data quality (missing values, outliers)

**Deliverable:** Clean individual admission records with timestamps

---

## Phase 2: Data Aggregation & Exploration (Week 2-3)

### 2.1 Time Series Aggregation
**File:** `notebooks/02_exploratory_analysis.ipynb`

Tasks:
- Aggregate individual records to daily admission counts
- Calculate related KPIs (daily discharges, average length of stay, bed occupancy)
- Create weekly/monthly aggregations (if needed)
- Handle missing dates (fill with zeros or interpolate)
- Create department-level time series (ICU, ED, Medical, Surgical) if available

**Code Structure:**
```python
# Aggregate to daily counts
daily_admissions = df.groupby(pd.to_datetime(df['admittime']).dt.date).size()

# Set as time series with datetime index
daily_admissions.index = pd.to_datetime(daily_admissions.index)
daily_admissions.columns = ['admissions']
```

### 2.2 Exploratory Data Analysis

**Visualizations:**
- Time series plot (full history)
- Decomposition (trend, seasonal, residual)
- Seasonality analysis:
  - Day of week patterns
  - Monthly patterns
  - Yearly trends
- ACF/PACF plots (for ARIMA model selection)
- Distribution of daily admissions

**Statistical Analysis:**
- Stationarity tests (ADF, KPSS)
- Summary statistics (mean, std, min, max)
- Identify outliers and structural breaks
- Correlation analysis (if multiple series)

**Key Insights to Document:**
- Average daily admissions
- Peak days/seasons
- Trend direction (increasing/decreasing)
- Seasonal patterns
- Anomalies or data quality issues

**Deliverable:** 
- Aggregated time series saved to `data/processed/daily_admissions.csv`
- KPI time series (discharges, bed occupancy, ALOS) if data available

---

## Phase 3: Feature Engineering (Week 3-4)

### 3.1 Temporal Features
**File:** `notebooks/03_feature_engineering.ipynb`

Create features:
- Day of week (1-7)
- Month (1-12)
- Day of month (1-31)
- Week of year (1-52)
- Is weekend (binary)
- Is holiday (US federal holidays)
- Quarter (Q1-Q4)

### 3.2 Lag Features
- Lag 1, 7, 30 days (previous admissions)
- Rolling statistics (7-day, 30-day moving averages)
- Rolling standard deviations

### 3.3 KPI Features (If Available)
- Bed occupancy rates (lagged values)
- Discharge rates (lagged values)
- Average length of stay (as external regressor)
- These KPIs can enhance admission forecasting models

### 3.4 External Features (Optional but Recommended)
- Weather data (temperature, precipitation) - from public APIs
- Flu season indicators (CDC data)
- Local events/calendars

### 3.5 Feature Selection
- Correlation analysis
- Feature importance (if using tree-based models)
- Remove highly correlated features

**Deliverable:** Feature-engineered dataset saved to `data/processed/admissions_with_features.csv`

---

## Phase 4: Model Development (Week 4-5)

### 4.1 Train-Test Split
- Use time series cross-validation (rolling window)
- Train: ~70-80% of data (earlier period)
- Test: ~20-30% of data (later period)
- Avoid random splits (preserve temporal order)

### 4.2 Baseline Models
**File:** `notebooks/04_model_development.ipynb`

Implement simple benchmarks:
1. **Naive Forecast:** Last value
2. **Seasonal Naive:** Same value from previous week/month
3. **Moving Average:** Simple moving average
4. **Linear Trend:** Simple linear regression on time

**Purpose:** Establish baseline performance for comparison

### 4.3 Classical Time Series Models

#### ARIMA/SARIMA
- ACF/PACF analysis for parameter selection
- Auto ARIMA (pmdarima) for automatic selection
- SARIMA for seasonal patterns (weekly, annual)
- Grid search for optimal (p,d,q)(P,D,Q,s) parameters

**Python Libraries:**
- `statsmodels.tsa.arima.model.ARIMA`
- `pmdarima.auto_arima`

#### Structural Time Series Models
- Trend + Seasonal components
- State-space framework

### 4.4 Advanced Models

#### LSTM (Long Short-Term Memory)
- Architecture: 1-2 LSTM layers
- Sequence length: 7-30 days
- Hyperparameters: epochs, batch size, learning rate
- Early stopping to prevent overfitting

**Python Libraries:**
- `tensorflow/keras`
- `pytorch` (alternative)

#### VAR (Vector Autoregression) - Multi-KPI Forecasting
- Forecast multiple KPIs simultaneously (admissions, discharges, bed occupancy)
- Model interactions between operational metrics
- Granger causality tests between KPIs
- Can also be used for department-level time series (ICU, ED, etc.)

#### Hierarchical Time Series (Optional Advanced)
- Hospital → Department → Unit levels
- Reconciliation methods

### 4.5 Model Training Best Practices
- Save all trained models to `models/` directory
- Log hyperparameters and performance metrics
- Use cross-validation for hyperparameter tuning

**Deliverable:** Trained models saved as `.pkl` files or `.h5` files

---

## Phase 5: Model Evaluation (Week 5-6)

### 5.1 Evaluation Metrics
**File:** `notebooks/05_model_evaluation.ipynb`

Calculate for each model:
- **RMSE** (Root Mean Squared Error)
- **MAE** (Mean Absolute Error)
- **MAPE** (Mean Absolute Percentage Error)
- **R²** (Coefficient of determination)
- Directional accuracy (if applicable)

### 5.2 Time Series Cross-Validation
- Rolling window approach
- Expanding window approach
- Multiple train-test splits
- Document CV strategy in report

### 5.3 Model Comparison
- Create comparison table (all metrics)
- Statistical tests (Diebold-Mariano test for forecast accuracy)
- Visual comparison (forecast vs actual plots)

### 5.4 Residual Analysis
- Residual plots (check for patterns)
- ACF of residuals (should be white noise)
- Q-Q plots (normality check)
- Ljung-Box test (autocorrelation in residuals)

### 5.5 Out-of-Sample Validation
- Hold-out test set performance
- Compare training vs test performance (check for overfitting)
- Generate confidence intervals for forecasts

**Deliverable:** Model comparison table and evaluation visualizations

---

## Phase 6: Forecasting & Finalization (Week 6)

### 6.1 Final Forecast Generation
**File:** `notebooks/06_forecasting.ipynb`

- Select best model based on evaluation
- Generate forecasts for next 30 days
- Calculate confidence intervals (95%)
- Visualize forecasts with historical data

### 6.2 Forecast Visualization
- Historical data (last 90 days)
- Forecasted values with confidence bands
- Highlight uncertainty regions
- Save to `results/forecasts/`

### 6.3 Business Insights
- Interpret forecast patterns
- Identify peak periods
- Calculate derived operational KPIs (staffing requirements, capacity utilization)
- Provide actionable recommendations
- Discuss limitations and assumptions

### 6.4 KPI-Derived Metrics
- **Bed occupancy forecasts:** Based on admission forecasts and average length of stay
- **Staffing requirements:** Derived from forecasted admissions using staff-to-patient ratios
- **Capacity alerts:** Flag periods when occupancy exceeds optimal thresholds

**Deliverable:** 
- Final forecast CSV and visualization saved to `results/forecasts/`
- Derived KPI metrics and operational insights

---

## Phase 7: Report Writing (Week 6-7)

### 7.1 Report Structure
**File:** `reports/final_report.md` (convert to PDF)

#### 1. Introduction & Motivation (2-3 pages)
- Problem statement: Hospital capacity management challenges
- Objectives: Forecasting for operational optimization
- Significance: Staffing, bed management, cost reduction
- Data source: MIMIC database description

#### 2. Data Description (1-2 pages)
- MIMIC database overview
- Data collection period: 2008-2019
- Variables: Daily admission counts, temporal features
- Data quality: Missing values, outliers handled
- Aggregation process: Individual records → daily time series

#### 3. Exploratory Data Analysis (2-3 pages)
- Time series plots
- Decomposition (trend, seasonal, residual)
- Seasonality patterns (day of week, monthly)
- Stationarity analysis
- Key patterns identified

#### 4. Methodology (3-4 pages)
- Models selected and justification:
  - Baseline models (why needed)
  - ARIMA/SARIMA (for seasonal patterns)
  - LSTM (for complex non-linear patterns)
  - Other models tried
- Feature engineering approach
- Train-test split strategy
- Cross-validation approach
- Evaluation metrics

#### 5. Results (3-4 pages)
- Model comparison table (all metrics)
- Best model identification
- Forecast plots (actual vs predicted)
- Out-of-sample performance
- Confidence intervals interpretation

#### 6. Discussion & Insights (2-3 pages)
- Key findings
- Business implications:
  - Staffing optimization
  - Capacity planning
  - Cost implications
- Limitations
- Future work
- Conclusions

#### 7. References & Appendix
- MIMIC database citation
- Packages/libraries used
- Additional plots/tables

**Total Target:** 15-18 pages including figures

### 7.2 Visualizations Required
- Time series plot (full history)
- Decomposition plots
- Seasonality plots (day of week, monthly)
- ACF/PACF plots
- Forecast comparison (all models)
- Final forecast with confidence intervals
- Residual plots
- Model diagnostics

**Quality Standards:**
- High resolution (300 DPI for publication)
- Clear labels and legends
- Professional appearance
- Consistent color scheme

---

## Phase 8: Code Documentation (Week 7)

### 8.1 Jupyter Notebook Organization
**File:** Single master notebook or separate notebooks per phase

**Structure:**
- Clear section headers
- Markdown explanations between code cells
- Inline comments for complex code
- Document assumptions and decisions

### 8.2 Code Quality
- PEP 8 style guide (Python)
- Meaningful variable names
- Functions for reusable code
- Error handling
- Reproducibility:
  - Set random seeds
  - Document versions (requirements.txt)
  - Clear data paths

### 8.3 Requirements File
**File:** `requirements.txt`

Include:
```
pandas>=1.5.0
numpy>=1.24.0
matplotlib>=3.6.0
seaborn>=0.12.0
statsmodels>=0.14.0
pmdarima>=2.0.0
tensorflow>=2.12.0
scikit-learn>=1.2.0
jupyter>=1.0.0
```

---

## Phase 9: Presentation (Optional, Week 7-8)

### 9.1 Slide Structure (10 slides max)

1. **Title Slide**
   - Project title
   - Your name
   - Course information

2. **Problem Statement**
   - Hospital capacity challenges
   - Need for forecasting

3. **Objectives**
   - Forecast daily admissions
   - Support capacity planning

4. **Data Overview**
   - MIMIC database
   - Sample size and period
   - Key variables

5. **Key Patterns** (EDA highlights)
   - Main seasonal patterns
   - Trends identified

6. **Methodology**
   - Models used (brief overview)
   - Key approach

7. **Results**
   - Model comparison
   - Best model performance
   - Sample forecast

8. **Insights**
   - Key findings
   - Business value

9. **Forecast Example**
   - Visualization of next 30 days
   - Confidence intervals

10. **Conclusion**
    - Summary
    - Future work
    - Questions

### 9.2 Presentation Tips
- Practice timing (10 minutes)
- Clear visuals
- Focus on business impact
- Prepare for questions

---

## Key Technical Decisions

### Models to Implement (Priority Order)
1. **Baseline Models** (Required)
   - Naive, Seasonal Naive, Moving Average

2. **ARIMA/SARIMA** (Required)
   - Classic time series approach
   - Good for seasonal patterns

3. **LSTM** (Highly Recommended)
   - Demonstrates advanced techniques
   - Can capture complex patterns

4. **VAR** (Multi-KPI Forecasting)
   - Forecast admissions, discharges, bed occupancy together
   - Demonstrate advanced multivariate time series modeling
   - Can also model department-level interactions

5. **Hierarchical Time Series** (Optional Advanced)
   - If department data available
   - Shows advanced methodology

### Evaluation Strategy
- Primary: Out-of-sample test set
- Secondary: Time series cross-validation
- Metrics: RMSE, MAE, MAPE (focus on MAPE for interpretability)

### Forecast Horizon
- Primary: 30 days ahead
- Show confidence intervals
- Discuss uncertainty

---

## Timeline Summary

| Week | Phase | Key Deliverables |
|------|-------|------------------|
| 1-2 | Data Acquisition | MIMIC access, data extraction |
| 2-3 | EDA & Aggregation | Daily time series, key patterns |
| 3-4 | Feature Engineering | Feature-engineered dataset |
| 4-5 | Model Development | Trained models (ARIMA, LSTM, etc.) |
| 5-6 | Model Evaluation | Comparison table, validation results |
| 6 | Forecasting | Final 30-day forecast |
| 6-7 | Report Writing | Complete written report |
| 7 | Code Documentation | Clean, documented notebooks |
| 7-8 | Presentation (Optional) | Slides and recording |

**Total Duration:** 7-8 weeks

---

## Success Criteria

### Technical Excellence
- Multiple models implemented (minimum: 3)
- Rigorous evaluation (out-of-sample validation)
- Model comparison and justification
- Confidence intervals provided

### Business Relevance
- Clear problem statement
- Actionable insights
- Operational recommendations
- Practical forecast horizon

### Communication
- Well-structured report
- Clear visualizations
- Compelling narrative
- Professional presentation (if applicable)

---

## Risk Mitigation

### Data Access Delays
- **Risk:** MIMIC registration takes longer than expected
- **Mitigation:** 
  - Start registration immediately
  - Have backup: CMS/HCUP data (immediate access)
  - Can proceed with alternative data source if needed

### Model Complexity
- **Risk:** Models take too long to train
- **Mitigation:**
  - Start with simpler models first
  - Use cloud computing if needed
  - Focus on 2-3 core models, not all possible models

### Time Management
- **Risk:** Running behind schedule
- **Mitigation:**
  - Follow timeline strictly
  - Prioritize core deliverables
  - Start report writing early (don't wait until end)

---

## Resources & References

### Data Sources
- MIMIC Database: https://mimic.mit.edu/
- CMS Data: https://data.cms.gov/
- HCUP: https://hcup-us.ahrq.gov/

### Python Libraries
- Time Series: statsmodels, pmdarima
- Deep Learning: tensorflow, keras
- Data: pandas, numpy
- Visualization: matplotlib, seaborn, plotly

### Learning Resources
- MIMIC documentation and tutorials
- Statsmodels documentation
- Time series forecasting textbooks
- Class materials and notes

---

## Next Steps (Immediate Actions)

1. **This Week:**
   - Register for MIMIC database access
   - Complete CITI training
   - Set up project directory structure
   - Install required Python packages

2. **Once MIMIC Access Granted:**
   - Download data
   - Begin data extraction notebook
   - Start exploratory analysis

3. **Ongoing:**
   - Document decisions and insights
   - Save intermediate results
   - Keep code organized
   - Start report sections early

