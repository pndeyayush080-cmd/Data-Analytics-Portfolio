-- Growmar Phase 1 — Governed Metric Layer
-- Source schema: raw
-- Do not modify raw source tables.

-- M01: Headcount by department and month
CREATE OR REPLACE VIEW m01_headcount AS
SELECT
    month_start_date,
    department_id,
    headcount_end AS headcount
FROM raw.fact_headcount_monthly
WHERE headcount_end >= 5;

-- M02: Hires by department and month
CREATE OR REPLACE VIEW m02_hires AS
SELECT
    month_start_date,
    department_id,
    hires
FROM raw.fact_headcount_monthly
WHERE headcount_end >= 5;

-- M03: Exits by department and month
CREATE OR REPLACE VIEW m03_exits AS
SELECT
    month_start_date,
    department_id,
    exits
FROM raw.fact_headcount_monthly
WHERE headcount_end >= 5;

-- M04: Monthly attrition rate
-- Official formula: exits / headcount_start * 100
CREATE OR REPLACE VIEW m04_attrition_rate_monthly AS
SELECT
    month_start_date,
    department_id,
    exits,
    headcount_start,
    ROUND(
        100.0 * exits / NULLIF(headcount_start, 0),
        2
    ) AS attrition_rate_pct
FROM raw.fact_headcount_monthly
WHERE headcount_start >= 10;

-- M05: Rolling 12-month attrition rate
-- Official formula: 12-month exits / average monthly ending headcount * 100
CREATE OR REPLACE VIEW m05_attrition_rate_rolling_12m AS
WITH monthly AS (
    SELECT
        month_start_date,
        department_id,
        exits,
        headcount_end,
        SUM(exits) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS exits_12m,
        AVG(headcount_end) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS avg_headcount_12m,
        COUNT(*) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS months_in_window
    FROM raw.fact_headcount_monthly
)
SELECT
    month_start_date,
    department_id,
    exits_12m,
    avg_headcount_12m,
    ROUND(
        100.0 * exits_12m / NULLIF(avg_headcount_12m, 0),
        2
    ) AS attrition_rate_pct
FROM monthly
WHERE months_in_window = 12
  AND avg_headcount_12m >= 10;

-- M06: Voluntary attrition rate, rolling 12 months
CREATE OR REPLACE VIEW m06_voluntary_attrition_rate AS
WITH monthly AS (
    SELECT
        month_start_date,
        department_id,
        voluntary_exits,
        headcount_end,
        SUM(voluntary_exits) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS voluntary_exits_12m,
        AVG(headcount_end) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS avg_headcount_12m,
        COUNT(*) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS months_in_window
    FROM raw.fact_headcount_monthly
)
SELECT
    month_start_date,
    department_id,
    voluntary_exits_12m,
    avg_headcount_12m,
    ROUND(
        100.0 * voluntary_exits_12m / NULLIF(avg_headcount_12m, 0),
        2
    ) AS voluntary_attrition_rate_pct
FROM monthly
WHERE months_in_window = 12
  AND avg_headcount_12m >= 10;

  -- M07: Gross pay by employee and month
CREATE OR REPLACE VIEW m07_gross_pay AS
SELECT
    period_end_date,
    department_id,
    employee_id,
    ROUND(SUM(gross_pay), 2) AS gross_pay
FROM raw.fact_payroll
GROUP BY 1, 2, 3;

-- M08: Net pay by employee and month
CREATE OR REPLACE VIEW m08_net_pay AS
SELECT
    period_end_date,
    department_id,
    employee_id,
    ROUND(SUM(net_pay), 2) AS net_pay
FROM raw.fact_payroll
GROUP BY 1, 2, 3;

-- M09: Employer payroll cost by employee and month
CREATE OR REPLACE VIEW m09_payroll_cost AS
SELECT
    period_end_date,
    department_id,
    employee_id,
    ROUND(SUM(employer_cost), 2) AS employer_cost
FROM raw.fact_payroll
GROUP BY 1, 2, 3;

-- M10: Cost per paid employee by department and month
CREATE OR REPLACE VIEW m10_cost_per_head AS
SELECT
    period_end_date,
    department_id,
    ROUND(SUM(employer_cost), 2) AS employer_cost,
    COUNT(DISTINCT employee_id) AS employees_paid,
    ROUND(
        SUM(employer_cost) / NULLIF(COUNT(DISTINCT employee_id), 0),
        2
    ) AS cost_per_head
FROM raw.fact_payroll
GROUP BY 1, 2
HAVING COUNT(DISTINCT employee_id) >= 5;

-- M11: Overtime pay share by department and month
CREATE OR REPLACE VIEW m11_overtime_share AS
SELECT
    period_end_date,
    department_id,
    ROUND(SUM(overtime_pay), 2) AS overtime_pay,
    ROUND(SUM(employer_cost), 2) AS employer_cost,
    ROUND(
        100.0 * SUM(overtime_pay) / NULLIF(SUM(employer_cost), 0),
        2
    ) AS overtime_share_pct
FROM raw.fact_payroll
GROUP BY 1, 2
HAVING COUNT(DISTINCT employee_id) >= 5;

-- M12: Variable pay share by department and month
CREATE OR REPLACE VIEW m12_variable_pay_share AS
SELECT
    period_end_date,
    department_id,
    ROUND(SUM(variable_pay), 2) AS variable_pay,
    ROUND(SUM(gross_pay), 2) AS gross_pay,
    ROUND(
        100.0 * SUM(variable_pay) / NULLIF(SUM(gross_pay), 0),
        2
    ) AS variable_pay_share_pct
FROM raw.fact_payroll
GROUP BY 1, 2
HAVING COUNT(DISTINCT employee_id) >= 5;

-- M13: Attendance rate by department and month
CREATE OR REPLACE VIEW m13_attendance_rate AS
SELECT
    period_end_date,
    department_id,
    SUM(present_days) AS present_days,
    SUM(half_days_unpaid) AS half_days_unpaid,
    SUM(scheduled_days) AS scheduled_days,
    ROUND(
        (SUM(present_days) + 0.5 * SUM(half_days_unpaid))
        / NULLIF(SUM(scheduled_days), 0),
        4
    ) AS attendance_rate
FROM raw.fact_attendance_monthly
GROUP BY 1, 2
HAVING COUNT(DISTINCT employee_id) >= 5;

-- M14: Late arrival rate by department and month
CREATE OR REPLACE VIEW m14_late_arrival_rate AS
SELECT
    period_end_date,
    department_id,
    SUM(late_arrivals) AS late_arrivals,
    SUM(present_days) AS present_days,
    ROUND(
        SUM(late_arrivals) / NULLIF(SUM(present_days), 0),
        4
    ) AS late_arrival_rate
FROM raw.fact_attendance_monthly
GROUP BY 1, 2
HAVING COUNT(DISTINCT employee_id) >= 5;

-- M15: Leave without pay days by employee and month
CREATE OR REPLACE VIEW m15_leave_without_pay_days AS
SELECT
    period_end_date,
    department_id,
    employee_id,
    ROUND(SUM(lop_days), 2) AS leave_without_pay_days
FROM raw.fact_payroll
GROUP BY 1, 2, 3;

-- M16: Revenue by month
CREATE OR REPLACE VIEW m16_revenue AS
SELECT
    DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
    -SUM(signed_amount_debit_positive) AS revenue
FROM raw.fact_ledger
WHERE account_code BETWEEN 4001 AND 4004
GROUP BY 1;

-- M17: Net profit by month
CREATE OR REPLACE VIEW m17_net_profit AS
SELECT
    DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
    -SUM(signed_amount_debit_positive) AS net_profit
FROM raw.fact_ledger
WHERE (account_code BETWEEN 4000 AND 4999)
   OR (account_code BETWEEN 5000 AND 5999)
GROUP BY 1;

-- M18: Operating margin by month
CREATE OR REPLACE VIEW m18_operating_margin AS
SELECT
    p.month_start_date,
    p.net_profit,
    r.revenue,
    ROUND(
        100.0 * p.net_profit / NULLIF(r.revenue, 0),
        2
    ) AS operating_margin_pct
FROM m17_net_profit p
JOIN m16_revenue r USING (month_start_date);

-- M19: Payroll cost as percentage of revenue
-- Use ledger payroll accounts 5001–5005, as specified in the dictionary.

CREATE OR REPLACE VIEW m19_payroll_pct_revenue AS
WITH payroll_ledger AS (
    SELECT
        DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
        SUM(signed_amount_debit_positive) AS payroll_cost
    FROM raw.fact_ledger
    WHERE account_code BETWEEN 5001 AND 5005
    GROUP BY 1
)
SELECT
    r.month_start_date,
    p.payroll_cost,
    r.revenue,
    ROUND(100.0 * p.payroll_cost / NULLIF(r.revenue, 0), 2)
        AS payroll_pct_revenue
FROM m16_revenue r
LEFT JOIN payroll_ledger p USING (month_start_date);

-- M20: Days sales outstanding (DSO), trailing 90 days.
-- AR account 1100 retains the invoice debit and payment credit through each
-- reporting date, so it is the time-correct closing-receivables balance.  An
-- invoice debit to AR is the sales amount including GST.  Restrict the view to
-- completed 90-day windows; the ledger begins on 2025-04-01.
CREATE OR REPLACE VIEW m20_dso AS
WITH ledger_bounds AS (
    SELECT
        MIN(entry_date) AS first_posting_date,
        MAX(entry_date) AS last_posting_date
    FROM raw.fact_ledger
),
report_months AS (
    SELECT DISTINCT d.month_end_date AS report_date
    FROM raw.dim_date d
    CROSS JOIN ledger_bounds b
    WHERE d.month_end_date >= b.first_posting_date + INTERVAL '89 days'
      AND d.month_end_date <= b.last_posting_date
),
receivables AS (
    SELECT
        r.report_date,
        SUM(l.signed_amount_debit_positive) AS closing_receivables
    FROM report_months r
    JOIN raw.fact_ledger l
      ON l.account_code = 1100
     AND l.entry_date <= r.report_date
    GROUP BY 1
),
sales_90d AS (
    SELECT
        r.report_date,
        SUM(l.signed_amount_debit_positive) AS revenue_incl_gst_90d
    FROM report_months r
    JOIN raw.fact_ledger l
      ON l.account_code = 1100
     AND l.source_type = 'INVOICE'
     AND l.entry_date BETWEEN r.report_date - INTERVAL '89 days'
                          AND r.report_date
    GROUP BY 1
)
SELECT
    r.report_date,
    ROUND(r.closing_receivables, 2) AS closing_receivables,
    ROUND(s.revenue_incl_gst_90d, 2) AS revenue_incl_gst_90d,
    ROUND(
        90.0 * r.closing_receivables / NULLIF(s.revenue_incl_gst_90d, 0),
        2
    ) AS dso_days
FROM receivables r
JOIN sales_90d s USING (report_date);

-- M21: Overdue receivables at each month-end
CREATE OR REPLACE VIEW m21_overdue_receivables AS
WITH report_dates AS (
    SELECT DISTINCT month_end_date AS report_date
    FROM raw.dim_date
)
SELECT
    r.report_date,
    i.client_id,
    SUM(i.balance_due) AS overdue_receivables
FROM report_dates r
JOIN raw.fact_invoice i
  ON i.due_date < r.report_date
 AND i.status NOT IN ('DRAFT', 'CANCELLED')
 AND i.balance_due > 0
GROUP BY 1, 2;

-- M22: Task completion rate by team and sprint
CREATE OR REPLACE VIEW m22_task_completion_rate AS
SELECT
    t.team_id,
    t.sprint_id,
    COUNT(*) FILTER (WHERE t.status = 'Done') AS tasks_done,
    COUNT(*) FILTER (WHERE t.status <> 'Cancelled') AS tasks_planned,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.status = 'Done')
        / NULLIF(COUNT(*) FILTER (WHERE t.status <> 'Cancelled'), 0),
        2
    ) AS task_completion_rate_pct
FROM raw.fact_task t
GROUP BY 1, 2
HAVING COUNT(*) FILTER (WHERE t.status <> 'Cancelled') >= 5;

-- M23: On-time delivery rate by team and sprint
CREATE OR REPLACE VIEW m23_on_time_delivery_rate AS
SELECT
    team_id,
    sprint_id,
    COUNT(*) FILTER (WHERE status = 'Done') AS tasks_done,
    COUNT(*) FILTER (
        WHERE status = 'Done' AND completed_on_time = 'Y'
    ) AS tasks_done_on_time,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE status = 'Done' AND completed_on_time = 'Y'
        ) / NULLIF(COUNT(*) FILTER (WHERE status = 'Done'), 0),
        2
    ) AS on_time_delivery_rate_pct
FROM raw.fact_task
GROUP BY 1, 2
HAVING COUNT(*) FILTER (WHERE status = 'Done') >= 5;

-- M24: Velocity by team and sprint
CREATE OR REPLACE VIEW m24_velocity AS
SELECT
    team_id,
    sprint_id,
    SUM(story_points) FILTER (WHERE status = 'Done') AS velocity_points
FROM raw.fact_task
GROUP BY 1, 2;

-- M25: Average cycle time by team and sprint
CREATE OR REPLACE VIEW m25_average_cycle_time AS
SELECT
    team_id,
    sprint_id,
    ROUND(AVG(cycle_time_days), 2) AS avg_cycle_time_days
FROM raw.fact_task
WHERE status = 'Done'
  AND started_date IS NOT NULL
  AND completed_date IS NOT NULL
  AND completed_date >= started_date
GROUP BY team_id, sprint_id
HAVING COUNT(*) >= 5;

-- M26: Anomaly flag rate by source and month
CREATE OR REPLACE VIEW m26_anomaly_flag_rate AS
SELECT
    DATE_TRUNC('month', period)::DATE AS month_start_date,
    source_dataset,
    COUNT(*) AS records_scored,
    COUNT(*) FILTER (WHERE flagged = 'Y') AS records_flagged,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE flagged = 'Y')
        / NULLIF(COUNT(*), 0),
        2
    ) AS anomaly_flag_rate_pct
FROM raw.fact_anomaly
GROUP BY 1, 2;

-- M27: High-risk share by department
-- Suppress groups below 10; never expose named employees.
CREATE OR REPLACE VIEW m27_high_risk_share AS
SELECT
    department_id,
    COUNT(DISTINCT employee_id) AS employees_scored,
    COUNT(DISTINCT employee_id) FILTER (WHERE risk_band = 'High')
        AS high_risk_employees,
    ROUND(
        100.0 * COUNT(DISTINCT employee_id) FILTER (WHERE risk_band = 'High')
        / NULLIF(COUNT(DISTINCT employee_id), 0),
        2
    ) AS high_risk_share_pct
FROM raw.fact_attrition_risk
GROUP BY department_id
HAVING COUNT(DISTINCT employee_id) >= 10;

-- M28: Forecast MAPE by department and month.
-- Retain future forecasts as explicitly not yet evaluable instead of dropping
-- them or claiming that a missing actual equals zero.
CREATE OR REPLACE VIEW m28_forecast_mape AS
SELECT
    f.department_id,
    f.forecast_month,
    f.metric,
    f.forecast_value,
    h.headcount_end AS actual_headcount,
    CASE
        WHEN h.headcount_end IS NULL THEN 'NOT_YET_EVALUABLE'
        WHEN h.headcount_end = 0 THEN 'NOT_EVALUABLE_ZERO_ACTUAL'
        ELSE 'EVALUABLE'
    END AS evaluation_status,
    CASE
        WHEN h.headcount_end > 0 THEN ROUND(
            100.0 * ABS(h.headcount_end - f.forecast_value)
            / h.headcount_end,
            2
        )
        ELSE NULL
    END AS forecast_mape_pct
FROM raw.fact_forecast f
LEFT JOIN raw.fact_headcount_monthly h
  ON h.department_id = f.department_id
 AND h.month_start_date = f.forecast_month
WHERE f.metric = 'headcount_end';

-- Metric catalog: the one authoritative inventory for all Task 4 views.
CREATE OR REPLACE VIEW metric_catalog AS
SELECT * FROM (VALUES
    ('M01', 'm01_headcount', 'Headcount', 'Active employees at month end.', 'fact_headcount_monthly / dim_employee', 'HR Analytics', 'Department x month', 5),
    ('M02', 'm02_hires', 'Hires', 'Employees hired during the month.', 'fact_headcount_monthly', 'HR Analytics', 'Department x month', 5),
    ('M03', 'm03_exits', 'Exits', 'Employees exiting during the month.', 'fact_headcount_monthly', 'HR Analytics', 'Department x month', 5),
    ('M04', 'm04_attrition_rate_monthly', 'Attrition rate (monthly)', 'Exits divided by starting headcount.', 'fact_headcount_monthly', 'HR Analytics', 'Department x month', 10),
    ('M05', 'm05_attrition_rate_rolling_12m', 'Attrition rate (rolling 12 months)', 'Trailing 12-month exits divided by average ending headcount.', 'fact_headcount_monthly', 'HR Analytics', 'Department x month', 10),
    ('M06', 'm06_voluntary_attrition_rate', 'Voluntary attrition rate', 'Trailing voluntary exits divided by average ending headcount.', 'fact_headcount_monthly', 'HR Analytics', 'Department x month', 10),
    ('M07', 'm07_gross_pay', 'Gross pay', 'Total earnings before deductions.', 'fact_payroll', 'Payroll', 'Employee x month', 5),
    ('M08', 'm08_net_pay', 'Net pay', 'Take-home pay after deductions.', 'fact_payroll', 'Payroll', 'Employee x month', 5),
    ('M09', 'm09_payroll_cost', 'Payroll cost (employer cost)', 'Full employer cost.', 'fact_payroll', 'Finance', 'Employee x month', 5),
    ('M10', 'm10_cost_per_head', 'Cost per head', 'Employer cost divided by paid employees.', 'fact_payroll', 'Finance', 'Department x month', 5),
    ('M11', 'm11_overtime_share', 'Overtime share', 'Overtime pay divided by employer cost.', 'fact_payroll', 'Payroll', 'Department x month', 5),
    ('M12', 'm12_variable_pay_share', 'Variable pay share', 'Variable pay divided by gross pay.', 'fact_payroll', 'Payroll', 'Department x month', 5),
    ('M13', 'm13_attendance_rate', 'Attendance rate', 'Present-day equivalent divided by scheduled days.', 'fact_attendance_monthly', 'HR Analytics', 'Department x month', 5),
    ('M14', 'm14_late_arrival_rate', 'Late arrival rate', 'Late arrivals divided by present days.', 'fact_attendance_monthly', 'HR Analytics', 'Department x month', 5),
    ('M15', 'm15_leave_without_pay_days', 'Leave without pay days', 'Unpaid leave days.', 'fact_payroll', 'Payroll', 'Employee x month', 5),
    ('M16', 'm16_revenue', 'Revenue', 'Ledger income from accounts 4001-4004.', 'fact_ledger', 'Finance', 'Account x month', NULL),
    ('M17', 'm17_net_profit', 'Net profit', 'Revenue less 5xxx expenses, including 4900 income.', 'fact_ledger', 'Finance', 'Month', NULL),
    ('M18', 'm18_operating_margin', 'Operating margin', 'Net profit divided by revenue.', 'fact_ledger', 'Finance', 'Month', NULL),
    ('M19', 'm19_payroll_pct_revenue', 'Payroll as % of revenue', 'Ledger payroll cost divided by revenue.', 'fact_payroll + fact_ledger', 'Finance', 'Month', NULL),
    ('M20', 'm20_dso', 'Days sales outstanding (DSO)', 'Closing AR divided by trailing 90-day GST-inclusive credit sales times 90.', 'fact_invoice, fact_ledger', 'Finance', 'Month', NULL),
    ('M21', 'm21_overdue_receivables', 'Overdue receivables', 'Unpaid balances past due at report date.', 'fact_invoice', 'Finance', 'Client x date', NULL),
    ('M22', 'm22_task_completion_rate', 'Task completion rate', 'Done tasks divided by non-cancelled planned tasks.', 'fact_task', 'Engineering Ops', 'Team x sprint', 5),
    ('M23', 'm23_on_time_delivery_rate', 'On-time delivery rate', 'On-time done tasks divided by done tasks.', 'fact_task', 'Engineering Ops', 'Team x sprint', 5),
    ('M24', 'm24_velocity', 'Velocity', 'Done story points.', 'fact_task', 'Engineering Ops', 'Team x sprint', NULL),
    ('M25', 'm25_average_cycle_time', 'Average cycle time', 'Average valid done-task cycle time.', 'fact_task', 'Engineering Ops', 'Team x sprint', 5),
    ('M26', 'm26_anomaly_flag_rate', 'Anomaly flag rate', 'Flagged scored records divided by all scored records.', 'fact_anomaly', 'AI/ML', 'Source x month', NULL),
    ('M27', 'm27_high_risk_share', 'High-risk share', 'High-risk employees divided by employees scored.', 'fact_attrition_risk', 'AI/ML', 'Department', 10),
    ('M28', 'm28_forecast_mape', 'Forecast error (MAPE)', 'Absolute headcount forecast error divided by actual.', 'fact_forecast vs fact_headcount', 'AI/ML', 'Department x month', NULL)
) AS catalog(metric_id, view_name, metric_name, business_definition, source_table, owner_team, grain, minimum_group_size);

-- Day 5 dashboard support views.
-- Aggregated outputs only; raw tables remain unchanged.

CREATE OR REPLACE VIEW v_workforce_location_mix AS
SELECT
    work_location,
    COUNT(DISTINCT employee_key) AS employee_count
FROM raw.dim_employee
WHERE employment_status = 'Active'
  AND work_location IS NOT NULL
GROUP BY work_location
HAVING COUNT(DISTINCT employee_key) >= 5;

CREATE OR REPLACE VIEW v_workforce_work_mode_mix AS
SELECT
    work_mode,
    COUNT(DISTINCT employee_key) AS employee_count
FROM raw.dim_employee
WHERE employment_status = 'Active'
  AND work_mode IS NOT NULL
GROUP BY work_mode
HAVING COUNT(DISTINCT employee_key) >= 5;

