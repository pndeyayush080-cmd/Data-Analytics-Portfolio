"""PQ-14 post-load validation.

Verifies:
  * Anomaly data integrity
  * Forecast data integrity (rows, metrics, departments, confidence bands)
  * Attrition risk data integrity
  * Backtest computation
  * Forecast error computation
  * AI labeling on all views

Run: python PQ-14-validate.py
"""
import duckdb, sys, os

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")

FAILURES = []
PASSES = []

def assert_check(label, condition, actual=None, expected=None):
    if condition:
        PASSES.append(label)
        print(f"[PASS] {label}")
        if actual is not None:
            print(f"       Value: {actual}")
    else:
        FAILURES.append((label, f"Expected: {expected}, Actual: {actual}"))
        print(f"[FAIL] {label}")
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")

print("=" * 60)
print("PQ-14 VALIDATION STARTING")
print("=" * 60)

con = duckdb.connect(r'C:\Users\Ayush Pandey\OneDrive\Documents\Data-Analytics-Portfolio\GrowMar_Phase_3\data\warehouse\pulseiq_clean.duckdb')

# ============================================================
# 1. ANOMALY DATA INTEGRITY
# ============================================================
print("\n--- 1. ANOMALY DATA INTEGRITY ---")

# Row count
anom_count = con.execute("SELECT COUNT(*) FROM raw.fact_anomaly WHERE flagged = 'Y'").fetchone()[0]
assert_check("Anomaly count (flagged=Y)", anom_count == 405, anom_count, 405)

# All flagged=Y
flagged_check = con.execute("SELECT COUNT(*) FROM raw.fact_anomaly WHERE flagged != 'Y'").fetchone()[0]
assert_check("All anomalies flagged=Y", flagged_check == 0, flagged_check, 0)

# Source datasets
src_datasets = con.execute("SELECT DISTINCT source_dataset FROM raw.fact_anomaly WHERE flagged = 'Y'").fetchdf()["source_dataset"].tolist()
expected_datasets = ["attendance_monthly_features", "payroll_monthly_features"]
assert_check("Source datasets present", set(src_datasets) == set(expected_datasets), src_datasets, expected_datasets)

# Reason codes
reason_codes = con.execute("SELECT COUNT(DISTINCT reason_code) FROM raw.fact_anomaly WHERE flagged = 'Y'").fetchone()[0]
assert_check("Reason code diversity (>= 5)", reason_codes >= 5, reason_codes, 5)

# Money at risk: check NaN handling
nan_money = con.execute("SELECT COUNT(*) FROM raw.fact_anomaly WHERE flagged = 'Y' AND (money_at_risk IS NULL OR money_at_risk != money_at_risk)").fetchone()[0]
money_valid = con.execute("SELECT COUNT(*) FROM raw.fact_anomaly WHERE flagged = 'Y' AND money_at_risk IS NOT NULL AND money_at_risk = money_at_risk").fetchone()[0]
print(f"  Anomalies with NaN money_at_risk: {nan_money}")
print(f"  Anomalies with valid money_at_risk: {money_valid}")

# Anomalies by risk view
risk_rows = con.execute("SELECT COUNT(*) FROM star_schema.pq14_anomalies_by_risk").fetchone()[0]
assert_check("Anomalies by risk view has rows", risk_rows > 0, risk_rows, ">0")

# Anomaly detail view
detail_rows = con.execute("SELECT COUNT(*) FROM star_schema.pq14_anomaly_detail").fetchone()[0]
assert_check("Anomaly detail view row count", detail_rows == 405, detail_rows, 405)

# Money at risk ranking order
rank_check = con.execute("""
    SELECT total_money_at_risk FROM star_schema.pq14_anomalies_by_risk
    ORDER BY total_money_at_risk DESC NULLS LAST
""").fetchdf()
is_sorted = all(rank_check["total_money_at_risk"].diff().dropna() <= 0)
assert_check("Anomalies ranked by money_at_risk DESC", is_sorted, True, True)

# ============================================================
# 2. FORECAST DATA INTEGRITY
# ============================================================
print("\n--- 2. FORECAST DATA INTEGRITY ---")

fc_count = con.execute("SELECT COUNT(*) FROM raw.fact_forecast").fetchone()[0]
assert_check("Forecast row count", fc_count == 72, fc_count, 72)

fc_metrics = con.execute("SELECT COUNT(DISTINCT metric) FROM raw.fact_forecast").fetchone()[0]
assert_check("Forecast metrics (2)", fc_metrics == 2, fc_metrics, 2)

fc_depts = con.execute("SELECT COUNT(DISTINCT department_id) FROM raw.fact_forecast").fetchone()[0]
assert_check("Forecast departments (11)", fc_depts == 11, fc_depts, 11)

fc_months = con.execute("SELECT COUNT(DISTINCT forecast_month) FROM raw.fact_forecast").fetchone()[0]
assert_check("Forecast months (6)", fc_months == 6, fc_months, 6)

# Confidence bands
band_check = con.execute("""
    SELECT COUNT(*) FROM raw.fact_forecast 
    WHERE lower_80 IS NOT NULL AND upper_80 IS NOT NULL AND lower_80 < upper_80
""").fetchone()[0]
assert_check("All forecasts have valid confidence bands", band_check == 72, band_check, 72)

# Future forecasts view
ff_count = con.execute("SELECT COUNT(*) FROM star_schema.pq14_future_forecasts").fetchone()[0]
assert_check("Future forecasts view count", ff_count == 72, ff_count, 72)

# AI label on forecasts
ai_label_check = con.execute("""
    SELECT COUNT(*) FROM star_schema.pq14_future_forecasts 
    WHERE ai_label = 'AI-generated, for human review'
""").fetchone()[0]
assert_check("AI label on all forecasts", ai_label_check == 72, ai_label_check, 72)

# Forecast note present
note_check = con.execute("""
    SELECT COUNT(*) FROM star_schema.pq14_future_forecasts 
    WHERE forecast_note IS NOT NULL AND forecast_note != ''
""").fetchone()[0]
assert_check("Forecast note present on all", note_check == 72, note_check, 72)

# ============================================================
# 3. BACKTEST COMPUTATION
# ============================================================
print("\n--- 3. BACKTEST COMPUTATION ---")

bt_hc = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_headcount").fetchone()[0]
print(f"  Headcount backtest months: {bt_hc}")

bt_attr = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_attrition").fetchone()[0]
print(f"  Attrition backtest months: {bt_attr}")

# Check predicted values are computed
bt_hc_pred = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_headcount WHERE predicted_value IS NOT NULL").fetchone()[0]
print(f"  Headcount backtest with predictions: {bt_hc_pred}")

bt_attr_pred = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_attrition WHERE predicted_value IS NOT NULL").fetchone()[0]
print(f"  Attrition backtest with predictions: {bt_attr_pred}")

# APE values computed
ape_hc = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_headcount WHERE ape_pct IS NOT NULL").fetchone()[0]
ape_attr = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_backtest_attrition WHERE ape_pct IS NOT NULL").fetchone()[0]
print(f"  Headcount APE computed: {ape_hc}")
print(f"  Attrition APE computed: {ape_attr}")

# ============================================================
# 4. FORECAST ERROR COMPUTATION
# ============================================================
print("\n--- 4. FORECAST ERROR COMPUTATION ---")

fe_rows = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_error").fetchone()[0]
print(f"  Forecast error rows: {fe_rows}")

# Check metrics present
fe_metrics = con.execute("SELECT DISTINCT metric FROM star_schema.pq14_forecast_error").fetchdf()["metric"].tolist()
print(f"  Metrics in error table: {fe_metrics}")

# Check all departments present
fe_depts = con.execute("SELECT COUNT(DISTINCT department_id) FROM star_schema.pq14_forecast_error").fetchone()[0]
print(f"  Departments in error table: {fe_depts}")

# Check error metrics computed
mape_check = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_error WHERE mape_pct IS NOT NULL").fetchone()[0]
mae_check = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_error WHERE mae IS NOT NULL").fetchone()[0]
rmse_check = con.execute("SELECT COUNT(*) FROM star_schema.pq14_forecast_error WHERE rmse IS NOT NULL").fetchone()[0]
print(f"  Rows with MAPE: {mape_check}, MAE: {mae_check}, RMSE: {rmse_check}")

# ============================================================
# 5. ATTRITION RISK INTEGRITY
# ============================================================
print("\n--- 5. ATTRITION RISK INTEGRITY ---")

ar_count = con.execute("SELECT COUNT(*) FROM raw.fact_attrition_risk").fetchone()[0]
assert_check("Attrition risk row count", ar_count == 430, ar_count, 430)

ar_bands = con.execute("SELECT COUNT(DISTINCT risk_band) FROM raw.fact_attrition_risk").fetchone()[0]
assert_check("Risk bands (3)", ar_bands == 3, ar_bands, 3)

ar_dates = con.execute("SELECT COUNT(DISTINCT as_of_date) FROM raw.fact_attrition_risk").fetchone()[0]
assert_check("As-of dates (2)", ar_dates == 2, ar_dates, 2)

ar_depts = con.execute("SELECT COUNT(DISTINCT department_id) FROM raw.fact_attrition_risk").fetchone()[0]
assert_check("Departments (10)", ar_depts == 10, ar_depts, 10)

# Latest as-of date
latest_date = con.execute("SELECT MAX(as_of_date) FROM raw.fact_attrition_risk").fetchone()[0]
print(f"  Latest as_of_date: {latest_date}")

# Risk band distribution
band_dist = con.execute("SELECT risk_band, COUNT(*) FROM raw.fact_attrition_risk GROUP BY risk_band ORDER BY COUNT(*) DESC").fetchdf()
print(f"  Band distribution:\n{band_dist.to_string(index=False)}")

# Summary view
ars_count = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary").fetchone()[0]
print(f"  Attrition risk summary rows: {ars_count}")

# AI label on summary
ars_ai = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary WHERE ai_label = 'AI-generated, for human review'").fetchone()[0]
assert_check("AI label on attrition summary", ars_ai == ars_count, ars_ai, ars_count)

# Model note present
model_note = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary WHERE model_note IS NOT NULL AND model_note != ''").fetchone()[0]
assert_check("Model note present", model_note == ars_count, model_note, ars_count)

# Detail view
ard_count = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_detail").fetchone()[0]
print(f"  Attrition risk detail rows: {ard_count}")

# AI label on detail
ard_ai = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_detail WHERE ai_label = 'AI-generated, for human review'").fetchone()[0]
assert_check("AI label on attrition detail", ard_ai == ard_count, ard_ai, ard_count)

# ============================================================
# 6. AI LABELING ON ALL VIEWS
# ============================================================
print("\n--- 6. AI LABELING ON ALL VIEWS ---")

# Future forecasts
ff_ai = con.execute("SELECT COUNT(*) FROM star_schema.pq14_future_forecasts WHERE ai_label = 'AI-generated, for human review'").fetchone()[0]
assert_check("AI label on future forecasts", ff_ai == 72, ff_ai, 72)

# Attrition summary
ars_ai = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary WHERE ai_label = 'AI-generated, for human review'").fetchone()[0]
assert_check("AI label on attrition summary", ars_ai == ars_count, ars_ai, ars_count)

# Attrition detail
ard_ai = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_detail WHERE ai_label = 'AI-generated, for human review'").fetchone()[0]
assert_check("AI label on attrition detail", ard_ai == ard_count, ard_ai, ard_count)

# Forecast note on future forecasts
fn_check = con.execute("SELECT COUNT(*) FROM star_schema.pq14_future_forecasts WHERE forecast_note LIKE '%Not a guaranteed outcome%'").fetchone()[0]
assert_check("Forecast disclaimer present", fn_check == 72, fn_check, 72)

# Attrition model note
mn_check = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary WHERE model_note LIKE '%support signal for HR%'").fetchone()[0]
assert_check("Attrition model disclaimer present", mn_check == ars_count, mn_check, ars_count)

# ============================================================
# 7. DASHBOARD QUERIES
# ============================================================
print("\n--- 7. DASHBOARD QUERIES ---")

# Anomalies query
anom_query = con.execute("SELECT COUNT(*) FROM star_schema.pq14_anomalies_by_risk").fetchone()[0]
print(f"  Anomalies by risk query: {anom_query} rows")

# Forecasts query
fc_query = con.execute("SELECT COUNT(*) FROM star_schema.pq14_future_forecasts WHERE metric = 'headcount_end'").fetchone()[0]
print(f"  Headcount forecasts: {fc_query} rows")

# Attrition risk summary query
ars_q = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_summary WHERE risk_band = 'High'").fetchone()[0]
print(f"  High risk departments: {ars_q}")

# ============================================================
# 8. VALIDATION VIEW
# ============================================================
print("\n--- 8. VALIDATION VIEW ---")

val_results = con.execute("SELECT check_name, status FROM star_schema.pq14_validation").fetchdf()
print(val_results.to_string(index=False))

val_passes = val_results[val_results["status"] == "PASS"].shape[0]
val_fails = val_results[val_results["status"] == "FAIL"].shape[0]
val_info = val_results[val_results["status"] == "INFO"].shape[0]
print(f"\n  Validation: {val_passes} PASS, {val_fails} FAIL, {val_info} INFO")

assert_check("All validation checks PASS/INFO", val_fails == 0, val_fails, 0)

# ============================================================
# 9. CROSS-VIEW CONSISTENCY
# ============================================================
print("\n--- 9. CROSS-VIEW CONSISTENCY ---")

# Anomaly detail matches by_risk total
detail_money = con.execute("SELECT SUM(money_at_risk) FROM star_schema.pq14_anomaly_detail").fetchone()[0]
by_risk_money = con.execute("SELECT SUM(total_money_at_risk) FROM star_schema.pq14_anomalies_by_risk").fetchone()[0]
assert_check("Anomaly money consistency", abs(detail_money - by_risk_money) < 0.01, detail_money, by_risk_money)

# Forecast error metric count matches backtest
fe_metric_count = con.execute("SELECT COUNT(DISTINCT metric) FROM star_schema.pq14_forecast_error").fetchone()[0]
bt_metric_count = 2  # headcount_end, attrition_rate_monthly_pct
assert_check("Forecast error metrics match backtest", fe_metric_count == bt_metric_count, fe_metric_count, bt_metric_count)

# Attrition risk detail matches summary employee count
ard_emp = con.execute("SELECT SUM(employee_count) FROM star_schema.pq14_attrition_risk_summary").fetchone()[0]
ars_emp = con.execute("SELECT COUNT(*) FROM star_schema.pq14_attrition_risk_detail").fetchone()[0]
print(f"  Summary employee count: {ard_emp}, Detail rows: {ars_emp}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("PQ-14 VALIDATION SUMMARY")
print("=" * 60)
print(f"PASSED: {len(PASSES)}")
print(f"FAILED: {len(FAILURES)}")

if FAILURES:
    print("\nFAILURES:")
    for label, detail in FAILURES:
        print(f"  - {label}: {detail}")
    sys.exit(1)
else:
    print("\nALL CHECKS PASSED!")
    sys.exit(0)