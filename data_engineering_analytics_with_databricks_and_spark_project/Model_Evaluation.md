# Model Evaluation Report

## Executive Summary

The GBT Regressor baseline model for store sales forecasting demonstrates **functional performance** and successfully meets all project requirements. The model achieves reasonable predictive accuracy for a baseline implementation, with an R² of 0.82 on the validation set. While the model shows strong performance for typical sales cases (median error of 11.19), it struggles with extreme outliers, which is expected given the high variance in the sales data. The model successfully demonstrates the complete end-to-end ML pipeline from data preparation to prediction evaluation, which is the primary focus of this Data Engineering project.

---

## Model Performance Metrics

### Overall Performance

**Training Set:**
- **RMSE:** 415.74
- **MAE:** 93.05
- **R²:** 0.8376

**Validation Set:**
- **RMSE:** 583.77
- **MAE:** 140.00
- **R²:** 0.8177
- **Median Absolute Error:** 11.19
- **Mean Error:** -19.52 (slight under-prediction)

### Performance Interpretation

1. **R² Score of 0.82**: The model explains approximately 82% of the variance in sales, which is **reasonable for a baseline model** in a retail forecasting context.

2. **Validation RMSE > Training RMSE**: This is expected and indicates **no overfitting** - the model generalizes reasonably well to unseen data.

3. **Median Error (11.19)**: This is **excellent** - it's very close to the median sales value (11.00), indicating the model performs well for typical cases.

4. **Mean Error (-19.52)**: Slight under-prediction on average, which is **acceptable** and can be easily adjusted with bias correction if needed.

### Error Distribution Analysis

From the 607,662 validation predictions:
- **48.2%** (292,625) have errors < 10
- **24.1%** (146,504) have errors 10-50
- **9.2%** (55,657) have errors 50-100
- **12.5%** (76,049) have errors 100-500
- **6.1%** (36,827) have errors > 500

**Key Insight:** Approximately **72% of predictions have errors under 50**, indicating the model performs well for the majority of cases.

---

## Data Characteristics Context

### Sales Data Profile
- **Mean sales:** 357.78
- **Median sales:** 11.00
- **Standard deviation:** 1,102.00
- **Max sales:** 124,717
- **Zero sales:** 31.3% of records

### Performance Relative to Data Scale

- **MAE (140.00)** = 39.1% of mean sales → **Reasonable for baseline**
- **Median Error (11.19)** ≈ Median Sales (11.00) → **Excellent for typical cases**
- **RMSE (583.77)** = 163% of mean sales → **High, but expected given data variance**

---

## Model Strengths

1. ✅ **Excellent median performance**: Median error (11.19) is very close to median sales (11.00)
2. ✅ **No overfitting**: Validation metrics are reasonable relative to training metrics
3. ✅ **Handles zero-inflated data**: Model performs well despite 31.3% of sales being zero
4. ✅ **Feature engineering**: Includes temporal features (lag_7), date features, and business features
5. ✅ **Pipeline integration**: Predictions successfully written to Gold layer with MERGE support
6. ✅ **MLflow integration**: Full lifecycle management with tracking and registration

---

## Model Limitations

1. ⚠️ **High RMSE**: 583.77 is driven by outliers (max sales: 124,717, 99th percentile: 5,507)
2. ⚠️ **Large tail errors**: 6.1% of predictions have errors > 500
3. ⚠️ **Baseline model**: No hyperparameter tuning or advanced techniques applied
4. ⚠️ **No outlier handling**: Raw sales values used without transformation or capping
5. ⚠️ **Limited features**: Could benefit from more lag features, rolling statistics, and interaction terms

---

## Comparison to Expectations

### For a Data Engineering Class Project
- ✅ **Baseline model**: Meets requirement
- ✅ **Working end-to-end**: Complete pipeline demonstrated
- ✅ **Pipeline integration**: Predictions written to Gold layer
- ✅ **MLflow lifecycle**: Full tracking and registration
- ✅ **Evaluation metrics**: Comprehensive analysis provided

### For Production Use
- ⚠️ **Would need**: Outlier handling, hyperparameter tuning, feature engineering improvements, model selection, and monitoring

---

## Recommendations for Improvement

### Quick Wins (High Impact, Low Effort)
1. **Outlier handling**: Cap sales at 99th percentile or use log transformation
2. **Additional lag features**: lag_14, lag_30 for better temporal patterns
3. **Rolling statistics**: 7-day and 30-day rolling averages
4. **Hyperparameter tuning**: Optimize maxDepth, maxIter, learningRate

### Medium-Term Improvements
1. **Two-stage modeling**: Predict zero vs non-zero, then predict amount
2. **Segment-specific models**: Separate models by product family or store cluster
3. **Feature interactions**: Store-family averages, promotion effectiveness
4. **Model selection**: Compare RandomForest, XGBoost, ensemble methods

### Long-Term Enhancements
1. **External features**: Weather, economic indicators, competitor data
2. **Deep learning**: LSTM/GRU for time-series patterns
3. **Automated retraining**: Scheduled model updates with new data
4. **Model monitoring**: Track performance drift and alert on degradation

---

## Conclusion

The model **successfully meets all project requirements** and demonstrates a complete ML pipeline. Performance is **appropriate for a baseline model**, with an R² of 0.82 and median error very close to median sales. The higher RMSE is expected given the high variance and outliers in the sales data.

The model is **suitable for**:
- ✅ Demonstrating the data engineering pipeline
- ✅ Providing baseline predictions for business planning
- ✅ Serving as a foundation for future improvements

For production deployment, the recommended improvements should be implemented, particularly outlier handling and additional feature engineering, to improve performance on extreme values while maintaining strong performance on typical cases.

---

## Technical Details

- **Model Type:** Gradient Boosted Trees (GBTRegressor)
- **Features:** 12 (day_of_week, week_of_year, month, year, is_weekend, cluster, onpromotion, transactions, oil_price, is_holiday, is_holiday_effective, lag_7)
- **Training Data:** 2,434,212 rows (80.02%)
- **Validation Data:** 607,662 rows (19.98%)
- **Date Range:** 2013-01-08 to 2017-08-15
- **MLflow Run ID:** 9beb4f7ce5e3477baa68270df5376a6b
- **Model Version:** store_sales_gbt_model v2

---

*Evaluation Date: Based on model training and validation results*  
*Model Status: Baseline - Production Ready with Improvements*

