-- ============================================================================
-- PQ-14: AI Signals Dashboard
-- Anomalies, Forecasts, and Attrition Risk views for AI-generated insights
-- ============================================================================

-- ============================================================================
-- 1. ANOMALIES RANKED BY MONEY AT RISK
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_anomalies_by_risk AS
WITH anomaly_clean AS (
    SELECT
        result_id,
        source_dataset,
        record_id,
        employee_id,
        period,
        anomaly_score,
        flagged,
        reason_code,
        reason_text,
        CASE 
            WHEN money_at_risk IS NULL OR money_at_risk != money_at_risk THEN 0  -- NaN check
            ELSE money_at_risk
        END AS money_at_risk,
        model_version,
        scored_at,
        CASE 
            WHEN money_at_risk IS NULL OR money_at_risk != money_at_risk THEN 'No monetary exposure (attendance anomaly)'
            ELSE 'Monetary exposure quantified'
        END AS money_at_risk_note
    FROM raw.fact_anomaly
    WHERE flagged = 'Y'
)
SELECT
    reason_code,
    COUNT(*) AS anomaly_count,
    SUM(money_at_risk) AS total_money_at_risk,
    AVG(money_at_risk) AS avg_money_at_risk,
    MAX(money_at_risk) AS max_money_at_risk,
    SUM(CASE WHEN money_at_risk = 0 THEN 1 ELSE 0 END) AS no_monetary_exposure_count
FROM anomaly_clean
GROUP BY reason_code
ORDER BY total_money_at_risk DESC NULLS LAST;

-- ============================================================================
-- 2. ANOMALY DETAIL VIEW (for drill-down)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_anomaly_detail AS
SELECT
    result_id,
    source_dataset,
    record_id,
    employee_id,
    period,
    anomaly_score,
    flagged,
    reason_code,
    reason_text,
    CASE 
        WHEN money_at_risk IS NULL OR money_at_risk != money_at_risk THEN 0
        ELSE money_at_risk
    END AS money_at_risk,
    model_version,
    scored_at,
    CASE 
        WHEN money_at_risk IS NULL OR money_at_risk != money_at_risk THEN 'No monetary exposure (attendance anomaly)'
        ELSE 'Monetary exposure quantified'
    END AS money_at_risk_note
FROM raw.fact_anomaly
WHERE flagged = 'Y'
ORDER BY money_at_risk DESC NULLS LAST, anomaly_score DESC;

-- ============================================================================
-- 3. FORECAST VS ACTUAL BACKTEST - HEADCOUNT
-- Apply forecasting methods to historical data to compute backtest errors
-- Linear regression (36-month window): y = intercept + slope * x
-- For each month, fit on prior 36 months, predict next month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_forecast_backtest_headcount AS
WITH historical AS (
    SELECT
        h.department_id,
        h.month_start_date AS month,
        h.headcount_end AS actual_value
    FROM raw.fact_headcount_monthly h
    WHERE h.month_start_date <= DATE '2026-09-01'
      AND h.department_id IN ('ALL','D01','D02','D03','D04','D05','D06','D07','D08','D09','D10')
),
backtest AS (
    SELECT
        h.department_id,
        h.month,
        h.actual_value,
        -- Linear regression on prior 36 months: predict next month (month_idx = n+1)
        CASE 
            WHEN h.month >= DATE '2023-10-01' THEN
                (
                    WITH prior_data AS (
                        SELECT 
                            h2.headcount_end AS actual_value,
                            ROW_NUMBER() OVER (ORDER BY h2.month_start_date) AS month_idx
                        FROM raw.fact_headcount_monthly h2
                        WHERE h2.department_id = h.department_id
                          AND h2.month_start_date < h.month
                          AND h2.month_start_date >= h.month - INTERVAL '36 months'
                    ),
                    regression AS (
                        SELECT
                            COUNT(*) AS n,
                            SUM(month_idx) AS sum_x,
                            SUM(actual_value) AS sum_y,
                            SUM(month_idx * actual_value) AS sum_xy,
                            SUM(month_idx * month_idx) AS sum_x2
                        FROM prior_data
                    )
                    SELECT 
                        (sum_y - slope * sum_x) / n + slope * (n + 1)
                    FROM (
                        SELECT 
                            n, sum_x, sum_y, sum_xy, sum_x2,
                            (n * sum_xy - sum_x * sum_y) * 1.0 / (n * sum_x2 - sum_x * sum_x) AS slope
                        FROM regression
                    ) r
                )
            ELSE NULL
        END AS predicted_value
    FROM historical h
)
SELECT
    department_id,
    month,
    actual_value,
    predicted_value,
    CASE 
        WHEN predicted_value IS NOT NULL AND actual_value != 0
        THEN ROUND(ABS(actual_value - predicted_value) * 100.0 / actual_value, 2)
        ELSE NULL
    END AS ape_pct
FROM backtest
WHERE predicted_value IS NOT NULL
ORDER BY department_id, month;

-- ============================================================================
-- 4. FORECAST VS ACTUAL BACKTEST - ATTRITION RATE
-- Method: same-month average of available prior 1, 2, 3 years
-- Only uses available prior years; missing years are excluded from average
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_forecast_backtest_attrition AS
WITH historical AS (
    SELECT
        h.department_id,
        h.month_start_date AS month,
        h.attrition_rate_monthly_pct AS actual_value
    FROM raw.fact_headcount_monthly h
    WHERE h.month_start_date <= DATE '2026-09-01'
      AND h.department_id IN ('ALL','D01','D02','D03','D04','D05','D06','D07','D08','D09','D10')
      AND h.headcount_start > 0
),
backtest AS (
    SELECT
        h.department_id,
        h.month,
        h.actual_value,
        -- Same-month average of available prior 1, 2, 3 years
        -- Only includes years that have data (no zero-fill for missing years)
        CASE 
            WHEN h.month >= DATE '2023-04-01' THEN
                (
                    SELECT AVG(h2.attrition_rate_monthly_pct)
                    FROM raw.fact_headcount_monthly h2
                    WHERE h2.department_id = h.department_id
                      AND h2.month_start_date IN (
                          h.month - INTERVAL '1 year',
                          h.month - INTERVAL '2 year',
                          h.month - INTERVAL '3 year'
                      )
                      AND h2.headcount_start > 0
                      AND h2.attrition_rate_monthly_pct IS NOT NULL
                )
            ELSE NULL
        END AS predicted_value
    FROM historical h
)
SELECT
    department_id,
    month,
    actual_value,
    predicted_value,
    CASE 
        WHEN predicted_value IS NOT NULL AND actual_value != 0
        THEN ROUND(ABS(actual_value - predicted_value), 2)
        ELSE NULL
    END AS absolute_error,
    CASE 
        WHEN predicted_value IS NOT NULL AND actual_value != 0
        THEN ROUND(ABS(actual_value - predicted_value) * 100.0 / actual_value, 2)
        ELSE NULL
    END AS ape_pct
FROM backtest
WHERE predicted_value IS NOT NULL
ORDER BY department_id, month;

-- ============================================================================
-- 5. FUTURE FORECASTS WITH CONFIDENCE BANDS (from fact_forecast)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_future_forecasts AS
SELECT
    f.forecast_id,
    f.metric,
    f.department_id,
    f.forecast_month,
    f.forecast_value,
    f.lower_80,
    f.upper_80,
    f.method,
    f.trained_through,
    f.model_version,
    'AI-generated, for human review' AS ai_label,
    'Forecast based on data through ' || f.trained_through || '. Not a guaranteed outcome.' AS forecast_note
FROM raw.fact_forecast f
WHERE f.forecast_month > DATE '2026-09-01'
ORDER BY f.metric, f.department_id, f.forecast_month;

-- ============================================================================
-- 6. FORECAST ERROR TABLE (Backtest Summary)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_forecast_error AS
SELECT
    'headcount_end' AS metric,
    department_id,
    COUNT(*) AS backtest_months,
    ROUND(AVG(ape_pct), 2) AS mape_pct,
    ROUND(AVG(ABS(actual_value - predicted_value)), 2) AS mae,
    ROUND(SQRT(AVG(POWER(actual_value - predicted_value, 2))), 2) AS rmse
FROM star_schema.pq14_forecast_backtest_headcount
WHERE predicted_value IS NOT NULL
GROUP BY department_id

UNION ALL

SELECT
    'attrition_rate_monthly_pct' AS metric,
    department_id,
    COUNT(*) AS backtest_months,
    ROUND(AVG(ape_pct), 2) AS mape_pct,
    ROUND(AVG(ABS(actual_value - predicted_value)), 2) AS mae,
    ROUND(SQRT(AVG(POWER(actual_value - predicted_value, 2))), 2) AS rmse
FROM star_schema.pq14_forecast_backtest_attrition
WHERE predicted_value IS NOT NULL
GROUP BY department_id

ORDER BY metric, department_id;

-- ============================================================================
-- 7. ATTRITION RISK SUMMARY
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_attrition_risk_summary AS
WITH latest AS (
    SELECT MAX(as_of_date) AS max_date FROM raw.fact_attrition_risk
)
SELECT
    a.department_id,
    d.department_name,
    a.risk_band,
    COUNT(*) AS employee_count,
    ROUND(AVG(a.risk_score_12m), 4) AS avg_risk_score,
    STRING_AGG(DISTINCT a.top_reason_1, ' | ') AS top_reasons_1,
    STRING_AGG(DISTINCT a.top_reason_2, ' | ') AS top_reasons_2,
    a.as_of_date,
    'AI-generated, for human review' AS ai_label,
    a.model_version,
    a.model_note
FROM raw.fact_attrition_risk a
JOIN latest l ON a.as_of_date = l.max_date
JOIN raw.dim_department d ON a.department_id = d.department_id
GROUP BY a.department_id, d.department_name, a.risk_band, a.as_of_date, a.model_version, a.model_note
ORDER BY a.department_id, 
    CASE a.risk_band WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 END;

-- ============================================================================
-- 8. ATTRITION RISK DETAIL (for drill-down)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_attrition_risk_detail AS
WITH latest AS (
    SELECT MAX(as_of_date) AS max_date FROM raw.fact_attrition_risk
)
SELECT
    a.prediction_id,
    a.employee_id,
    e.employee_key,
    a.department_id,
    d.department_name,
    a.as_of_date,
    a.risk_score_12m,
    a.risk_band,
    a.top_reason_1,
    a.top_reason_2,
    a.top_reason_3,
    a.model_version,
    a.model_note,
    'AI-generated, for human review' AS ai_label
FROM raw.fact_attrition_risk a
JOIN latest l ON a.as_of_date = l.max_date
JOIN raw.dim_employee e ON a.employee_id = e.employee_id
JOIN raw.dim_department d ON a.department_id = d.department_id
ORDER BY a.risk_score_12m DESC, a.department_id, a.employee_id;

-- ============================================================================
-- 9. VALIDATION VIEW
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq14_validation AS
SELECT 'Anomaly Count' AS check_name, COUNT(*) AS value, 405 AS expected,
    CASE WHEN COUNT(*) = 405 THEN 'PASS' ELSE 'FAIL' END AS status
FROM raw.fact_anomaly WHERE flagged = 'Y'

UNION ALL
SELECT 'Anomaly Money at Risk Valid', COUNT(*) FILTER (WHERE money_at_risk IS NOT NULL AND money_at_risk = money_at_risk), 0,
    'INFO' FROM raw.fact_anomaly WHERE flagged = 'Y'

UNION ALL
SELECT 'Forecast Rows', COUNT(*), 72,
    CASE WHEN COUNT(*) = 72 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_forecast

UNION ALL
SELECT 'Forecast Metrics', COUNT(DISTINCT metric), 2,
    CASE WHEN COUNT(DISTINCT metric) = 2 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_forecast

UNION ALL
SELECT 'Forecast Departments', COUNT(DISTINCT department_id), 11,
    CASE WHEN COUNT(DISTINCT department_id) = 11 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_forecast

UNION ALL
SELECT 'Forecast Confidence Bands', 
    COUNT(*) FILTER (WHERE lower_80 IS NOT NULL AND upper_80 IS NOT NULL AND lower_80 < upper_80), 72,
    CASE WHEN COUNT(*) FILTER (WHERE lower_80 IS NOT NULL AND upper_80 IS NOT NULL AND lower_80 < upper_80) = 72 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_forecast

UNION ALL
SELECT 'Attrition Risk Rows', COUNT(*), 430,
    CASE WHEN COUNT(*) = 430 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_attrition_risk

UNION ALL
SELECT 'Attrition Risk Bands', 
    COUNT(DISTINCT risk_band), 3,
    CASE WHEN COUNT(DISTINCT risk_band) = 3 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_attrition_risk

UNION ALL
SELECT 'Attrition Risk As-of Dates', 
    COUNT(DISTINCT as_of_date), 2,
    CASE WHEN COUNT(DISTINCT as_of_date) = 2 THEN 'PASS' ELSE 'FAIL' END
FROM raw.fact_attrition_risk

UNION ALL
SELECT 'Backtest Headcount Months', COUNT(*), 0, 'INFO'
FROM star_schema.pq14_forecast_backtest_headcount

UNION ALL
SELECT 'Backtest Attrition Months', COUNT(*), 0, 'INFO'
FROM star_schema.pq14_forecast_backtest_attrition

UNION ALL
SELECT 'Forecast Error Rows', COUNT(*), 0, 'INFO'
FROM star_schema.pq14_forecast_error;