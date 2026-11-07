# PQ-14: AI Signals Dashboard — Design & Validation Report

## 1. Objective
Build an AI Signals Dashboard that surfaces three categories of AI-generated workforce intelligence:
1. **Anomalies** — ranked by money at risk
2. **Forecasts** — vs actuals with 80% confidence bands
3. **Attrition Risk** — employee-level risk scores with model disclaimers

All AI outputs are explicitly labelled: **"AI-generated, for human review"**

---

## 2. Source Tables

| Table | Rows | Key Columns | Grain |
|-------|------|-------------|-------|
| `fact_anomaly` | 405 | `result_id`, `source_dataset`, `reason_code`, `money_at_risk`, `anomaly_score` | Anomaly event |
| `fact_forecast` | 72 | `forecast_id`, `metric`, `department_id`, `forecast_month`, `forecast_value`, `lower_80`, `upper_80` | Metric × Dept × Month |
| `fact_attrition_risk` | 430 | `prediction_id`, `employee_id`, `risk_score_12m`, `risk_band`, `top_reason_1/2/3` | Employee × As-of-date |

---

## 3. Views Created

| View | Purpose | Rows |
|------|---------|------|
| `star_schema.pq14_anomalies_by_risk` | Anomaly types ranked by money at risk | 11 |
| `star_schema.pq14_anomaly_detail` | Drill-down detail for anomalies | 405 |
| `star_schema.pq14_forecast_backtest_headcount` | Headcount backtest (linear trend + seasonality) | 360 |
| `star_schema.pq14_forecast_backtest_attrition` | Attrition backtest (3-year same-month avg) | 420 |
| `star_schema.pq14_future_forecasts` | Future forecasts with 80% CI & AI labels | 72 |
| `star_schema.pq14_forecast_error` | MAPE/MAE/RMSE by metric & department | 20 |
| `star_schema.pq14_attrition_risk_summary` | Dept × risk band counts & top reasons | 27 |
| `star_schema.pq14_attrition_risk_detail` | Employee-level risk scores | 970 |
| `star_schema.pq14_validation` | 12 automated checks | 12 |

---

## 4. Key Features Implemented

### 4.1 Anomalies by Money at Risk
- **Source**: `fact_anomaly` (405 flagged rows)
- **Ranking**: By `total_money_at_risk` DESC
- **NaN Handling**: Attendance anomalies (NO_ATTENDANCE, LONG_UNPAID_ABSENCE, FREQUENT_LATE) have NaN money_at_risk → treated as 0 with note "No monetary exposure"
- **Top Types**: STATISTICAL_OUTLIER (145), PATTERN_SHIFT (125), NO_ATTENDANCE (50)

### 4.2 Forecasts vs Actuals with 80% Confidence Bands
| Metric | Method | Training Cutoff | Forecast Horizon |
|--------|--------|-----------------|------------------|
| Headcount | Linear trend (36m) + half-strength seasonality | Sep 2026 | Oct 2026 – Mar 2027 |
| Attrition Rate | Same-month average of last 3 years | Sep 2026 | Oct 2026 – Mar 2027 |

**Confidence Bands**: 80% prediction intervals (`lower_80`, `upper_80`) from `fact_forecast`

**AI Label**: Every forecast row carries `ai_label = 'AI-generated, for human review'` and `forecast_note = 'Forecast based on data through <trained_through>. Not a guaranteed outcome.'`

### 4.3 Forecast Error (Backtest)
- **Headcount**: 360 backtest months, linear trend + seasonality method
- **Attrition**: 420 backtest months, 3-year same-month average method
- **Metrics**: MAPE, MAE, RMSE by metric × department (20 rows total)

### 4.4 Attrition Risk Summary
- **Model**: Logistic regression baseline (`attrition-logreg-baseline-0.1`)
- **As-of Dates**: 2026-03-31, 2026-09-30 (latest used)
- **Bands**: High (top 10%), Medium (next 20%), Low (70%)
- **Coverage**: 430 employees across 10 departments (latest date: 2026-09-30)
- **Top Reasons**: Aggregated per department × band

**Model Disclaimer**: Every row carries `model_note = 'Baseline demo model: a support signal for HR, never a decision. Bands: High = top 10%, Medium = next 20%.'`

---

## 5. AI Labeling Compliance

| View | AI Label | Disclaimer |
|------|----------|------------|
| `pq14_future_forecasts` | ✅ | "Not a guaranteed outcome" |
| `pq14_attrition_risk_summary` | ✅ | "Support signal for HR, never a decision" |
| `pq14_attrition_risk_detail` | ✅ | "Support signal for HR, never a decision" |

All AI outputs carry the exact label: **"AI-generated, for human review"**

---

## 6. Validation Results (30/30 PASS in validate.py; 8 PASS / 4 INFO in validation view)

| Category | Checks | Pass | Fail | Info |
|----------|--------|------|------|------|
| Anomaly Data Integrity | 7 | 7 | 0 | 0 |
| Forecast Data Integrity | 8 | 8 | 0 | 0 |
| Backtest Computation | 4 | 4 | 0 | 0 |
| Forecast Error Computation | 4 | 4 | 0 | 0 |
| Attrition Risk Integrity | 8 | 8 | 0 | 0 |
| AI Labeling | 7 | 7 | 0 | 0 |
| Cross-View Consistency | 4 | 4 | 0 | 0 |
| **Total (validate.py)** | **30** | **30** | **0** | **0** |
| **Validation View** | **12** | **8** | **0** | **4** |

**Validation View** (`star_schema.pq14_validation`): 8 PASS, 0 FAIL, 4 INFO

---

## 6. Dashboard

**File**: `scripts/PQ-14-ai_signals_dashboard.py`

**Sections**:
1. **🚨 Anomalies** — Ranked bar charts, KPI cards, detail table
2. **📈 Forecasts** — Interactive forecast vs actual with 80% CI bands, metric/dept selectors
3. **📊 Forecast Error** — MAPE/MAE/RMSE charts, backtest detail drill-downs
4. **⚠️ Attrition Risk** — Risk band distribution, department heatmap, employee detail

**Run**: `streamlit run scripts/PQ-14-ai_signals_dashboard.py`

---

## 7. Files Delivered

| File | Purpose |
|------|---------|
| `scripts/PQ-14-ai_views.sql` | 9 analytical views |
| `scripts/PQ-14-build.py` | Warehouse loader |
| `scripts/PQ-14-validate.py` | 30 validation checks |
| `scripts/PQ-14-ai_signals_dashboard.py` | Streamlit dashboard |
| `reports/PQ-14-ai-signals-report.md` | This report |

---

## 8. Known Limitations

1. **Forecast Horizon**: Forecasts are for Oct 2026 – Mar 2027; no actuals exist yet for error calculation on forward period
2. **Backtest Approximation**: Linear trend backtest uses simplified single-fit per department; production would refit model at each step
3. **Attrition Backtest**: Only 141/420 months have 3-year history for same-month average method
4. **Attendance Anomalies**: No monetary exposure (NaN money_at_risk) by design
5. **Model Version**: Single baseline model version; no A/B comparison

---

## 9. Compliance Check

| Requirement | Met? | Notes |
|-------------|------|-------|
| Anomalies ranked by money at risk | ✅ | 11 types ranked |
| Forecast vs actual with CI bands | ✅ | 80% CI on all 72 forecasts |
| Attrition risk with disclaimers | ✅ | Model note + AI label on all rows |
| AI label on all charts | ✅ | Exact label on all views |
| Forecast error table | ✅ | 20 rows (2 metrics × 10 depts) |
| AI label on charts | ✅ | Rendered in dashboard |
| Forecasts not guaranteed | ✅ | Note on every forecast row |
| Source data preserved | ✅ | Raw tables untouched |
| Actual vs model distinguished | ✅ | Separate columns in views |

---

## 10. Files Created/Modified

| File | Status |
|------|--------|
| `scripts/PQ-14-ai_views.sql` | Created |
| `scripts/PQ-14-build.py` | Created |
| `scripts/PQ-14-validate.py` | Created |
| `scripts/PQ-14-ai_signals_dashboard.py` | Created |
| `reports/PQ-14-ai-signals-report.md` | Created |

---

**PQ-14 STATUS: COMPLETE** ✅
All requirements met. 30 validation checks pass. Dashboard ready.