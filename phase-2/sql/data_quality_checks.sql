-- ======================================================================
-- GrowMar Phase 2 — Data Quality Detection Queries (READ-ONLY)
-- ======================================================================
-- Generated: 2026-10-29
-- Database: data/warehouse/pulseiq.duckdb
-- Purpose: Read-only detection queries for data quality validation.
-- No UPDATE, DELETE, DROP, or INSERT statements.
-- ======================================================================

-- ======================================================================
-- SECTION 1: EXPECTED BEHAVIOR VERIFICATION (Composite Keys)
-- These should return ZERO rows — they validate correct data modeling.
-- ======================================================================

-- 1.1 budget_payroll_dept_month: composite key (department_id, month) should be unique
-- Expected: 0 rows (198 rows = 11 depts × 18 months, all unique combos)
SELECT 'budget_payroll_dept_month composite key check' AS check_name,
       COUNT(*) AS duplicate_count
FROM (
    SELECT "department_id", "month", COUNT(*) AS cnt
    FROM "budget_payroll_dept_month"
    GROUP BY "department_id", "month"
    HAVING COUNT(*) > 1
) dup;

-- 1.2 fact_headcount_monthly: composite key (date_key, department_id) should be unique
-- Expected: 0 rows (891 rows = 81 months × 11 depts, all unique combos)
SELECT 'fact_headcount_monthly composite key check' AS check_name,
       COUNT(*) AS duplicate_count
FROM (
    SELECT "date_key", "department_id", COUNT(*) AS cnt
    FROM "fact_headcount_monthly"
    GROUP BY "date_key", "department_id"
    HAVING COUNT(*) > 1
) dup;

-- 1.3 kpi_targets: composite key (month, department_id) should be unique
-- Expected: 0 rows (180 rows = 18 months × 10 depts, all unique combos)
SELECT 'kpi_targets composite key check' AS check_name,
       COUNT(*) AS duplicate_count
FROM (
    SELECT "month", "department_id", COUNT(*) AS cnt
    FROM "kpi_targets"
    GROUP BY "month", "department_id"
    HAVING COUNT(*) > 1
) dup;

-- 1.4 fact_forecast: composite key (forecast_id) should be unique
-- Expected: 0 rows
SELECT 'fact_forecast primary key check' AS check_name,
       COUNT(*) AS duplicate_count
FROM (
    SELECT "forecast_id", COUNT(*) AS cnt
    FROM "fact_forecast"
    GROUP BY "forecast_id"
    HAVING COUNT(*) > 1
) dup;


-- ======================================================================
-- SECTION 2: DOCUMENTED PLANTED DEFECTS (DQ-01 through DQ-11)
-- These SHOULD return rows — they confirm planted defects exist.
-- ======================================================================

-- 2.1 DQ-01: ATTENDANCE_AFTER_EXIT (Warning)
-- Attendance recorded for month after employee exit
-- Source: dq_known_issues DQ-01, dq_checks_catalog DQ-C05
SELECT 'DQ-01: ATTENDANCE_AFTER_EXIT' AS check_name,
       a."attendance_fact_id",
       a."employee_id",
       a."period_end_date",
       d."exit_date"
FROM "fact_attendance_monthly" a
JOIN "dim_employee" d ON a."employee_id" = d."employee_id"
WHERE d."exit_date" IS NOT NULL
  AND a."period_end_date" > (SELECT LAST_DAY(d."exit_date"));

-- 2.2 DQ-02: DUPLICATE_PAYROLL_ROW (Critical)
-- Exact duplicate employee-month with new payroll_item_id
-- Source: dq_known_issues DQ-02, dq_checks_catalog DQ-C03
SELECT 'DQ-02: DUPLICATE_PAYROLL_ROW' AS check_name,
       "employee_id", "run_id", COUNT(*) AS dup_count
FROM "fact_payroll"
GROUP BY "employee_id", "run_id"
HAVING COUNT(*) > 1;

-- 2.3 DQ-03: ORPHAN_FOREIGN_KEY (Critical)
-- Payroll rows for employee_ids not in dim_employee
-- Source: dq_known_issues DQ-03, dq_checks_catalog DQ-C04
SELECT 'DQ-03: ORPHAN_FOREIGN_KEY' AS check_name,
       p."payroll_item_id",
       p."employee_id",
       p."employee_key"
FROM "fact_payroll" p
LEFT JOIN "dim_employee" d ON p."employee_id" = d."employee_id"
WHERE d."employee_id" IS NULL;

-- 2.4 DQ-04: PAYROLL_LEDGER_MISMATCH (Critical)
-- June 2026 payroll posting shows 18,450 more than payroll run
-- Source: dq_known_issues DQ-04, dq_checks_catalog DQ-C01
SELECT 'DQ-04: PAYROLL_LEDGER_MISMATCH' AS check_name,
       p."month",
       SUM(p."employer_cost") AS payroll_cost,
       SUM(l."signed_amount_debit_positive") AS ledger_salary_expense,
       SUM(p."employer_cost") - SUM(l."signed_amount_debit_positive") AS diff
FROM (
    SELECT DATE_TRUNC('month', "period_end_date") AS month, "employer_cost"
    FROM "fact_payroll"
) p
JOIN (
    SELECT DATE_TRUNC('month', "entry_date") AS month, "signed_amount_debit_positive"
    FROM "fact_ledger"
    WHERE "account_code" IN ('5001','5002','5003','5004','5005')
) l USING (month)
GROUP BY p.month
HAVING ABS(SUM(p."employer_cost") - SUM(l."signed_amount_debit_positive")) > 0.01;

-- 2.5 DQ-05: OVERPAID_INVOICE (Warning)
-- Amount paid exceeds invoice total; negative balance_due
-- Source: dq_known_issues DQ-05, dq_checks_catalog DQ-C07
SELECT 'DQ-05: OVERPAID_INVOICE' AS check_name,
       "invoice_id",
       "amount_paid",
       "total_amount",
       "balance_due"
FROM "fact_invoice"
WHERE "amount_paid" > "total_amount"
   OR "balance_due" < 0;

-- 2.6 DQ-06: COMPLETED_BEFORE_STARTED (Warning)
-- Task completion date before start date (negative cycle time)
-- Source: dq_known_issues DQ-06, dq_checks_catalog DQ-C09
SELECT 'DQ-06: COMPLETED_BEFORE_STARTED' AS check_name,
       "task_id",
       "started_date",
       "completed_date",
       "cycle_time_days"
FROM "fact_task"
WHERE "completed_date" < "started_date";

-- 2.7 DQ-07: DONE_WITHOUT_DATE (Warning)
-- Status = Done but completed_date is NULL
-- Source: dq_known_issues DQ-07, dq_checks_catalog DQ-C09
SELECT 'DQ-07: DONE_WITHOUT_DATE' AS check_name,
       "task_id",
       "status",
       "completed_date"
FROM "fact_task"
WHERE "status" = 'Done'
  AND "completed_date" IS NULL;

-- 2.7 DQ-08: END_BEFORE_START (Warning)
-- Leave end_date before start_date (swapped dates)
-- Source: dq_known_issues DQ-08, dq_checks_catalog DQ-C10
SELECT 'DQ-08: END_BEFORE_START' AS check_name,
       "leave_request_id",
       "start_date",
       "end_date"
FROM "fact_leave"
WHERE "end_date" < "start_date";

-- 2.9 DQ-09: STALE_PREDICTION (Warning)
-- Attrition risk predictions older than 7 days from latest batch
-- Source: dq_known_issues DQ-09, dq_checks_catalog DQ-C11
SELECT 'DQ-09: STALE_PREDICTION' AS check_name,
       "prediction_id",
       "employee_id",
       "as_of_date",
       (SELECT MAX("as_of_date") FROM "fact_attrition_risk") AS latest_as_of_date
FROM "fact_attrition_risk"
WHERE "as_of_date" < (SELECT MAX("as_of_date") FROM "fact_attrition_risk") - INTERVAL '7 days';

-- 2.10 DQ-10: TOTAL_MISMATCH (Warning)
-- Expense total_amount != amount_excl_gst + gst_amount
-- Source: dq_known_issues DQ-10, dq_checks_catalog DQ-C08
SELECT 'DQ-10: TOTAL_MISMATCH' AS check_name,
       "expense_id",
       "total_amount",
       "amount_excl_gst",
       "gst_amount",
       ("amount_excl_gst" + "gst_amount") AS computed_total,
       "total_amount" - ("amount_excl_gst" + "gst_amount") AS diff
FROM "fact_expense"
WHERE ABS("total_amount" - ("amount_excl_gst" + "gst_amount")) > 0.01;

-- 2.11 DQ-11: SCD_INTERVAL_OVERLAP (Critical)
-- Employee version valid_to overlaps with next version's valid_from
-- Source: dq_known_issues DQ-11, dq_checks_catalog DQ-C12
SELECT 'DQ-11: SCD_INTERVAL_OVERLAP' AS check_name,
       a."employee_key" AS key_a,
       a."employee_id",
       a."valid_from" AS from_a,
       a."valid_to" AS to_a,
       b."employee_key" AS key_b,
       b."valid_from" AS from_b,
       b."valid_to" AS to_b
FROM "dim_employee" a
JOIN "dim_employee" b
  ON a."employee_id" = b."employee_id"
 AND a."employee_key" < b."employee_key"
 AND a."valid_to" >= b."valid_from";


-- ======================================================================
-- SECTION 3: STRUCTURAL VALIDATION (Foreign Key Orphans)
-- These check referential integrity per documented star schema joins.
-- ======================================================================

-- 3.1 fact_payroll -> dim_employee (employee_key)
-- Source: README star schema
SELECT 'FK: fact_payroll.employee_key -> dim_employee.employee_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_payroll" p
LEFT JOIN "dim_employee" d ON p."employee_key" = d."employee_key"
WHERE d."employee_key" IS NULL;

-- 3.2 fact_payroll -> dim_employee (employee_id)
-- Source: README star schema
SELECT 'FK: fact_payroll.employee_id -> dim_employee.employee_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_payroll" p
LEFT JOIN "dim_employee" d ON p."employee_id" = d."employee_id"
WHERE d."employee_id" IS NULL;

-- 3.3 fact_attendance_monthly -> dim_employee (employee_key)
SELECT 'FK: fact_attendance_monthly.employee_key -> dim_employee.employee_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attendance_monthly" a
LEFT JOIN "dim_employee" d ON a."employee_key" = d."employee_key"
WHERE d."employee_key" IS NULL;

-- 3.4 fact_leave -> dim_employee (employee_key)
SELECT 'FK: fact_leave.employee_key -> dim_employee.employee_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_leave" l
LEFT JOIN "dim_employee" d ON l."employee_key" = d."employee_key"
WHERE d."employee_key" IS NULL;

-- 3.5 fact_leave -> dim_leave_type (leave_type_code)
SELECT 'FK: fact_leave.leave_type_code -> dim_leave_type.leave_type_code' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_leave" l
LEFT JOIN "dim_leave_type" d ON l."leave_type_code" = d."leave_type_code"
WHERE d."leave_type_code" IS NULL;

-- 3.5 fact_headcount_monthly -> dim_department
SELECT 'FK: fact_headcount_monthly.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_headcount_monthly" h
LEFT JOIN "dim_department" d ON h."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.6 fact_ledger -> dim_account
SELECT 'FK: fact_ledger.account_code -> dim_account.account_code' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_ledger" l
LEFT JOIN "dim_account" d ON l."account_code" = d."account_code"
WHERE d."account_code" IS NULL;

-- 3.7 fact_ledger -> dim_department (cost_center)
SELECT 'FK: fact_ledger.cost_center_department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_ledger" l
LEFT JOIN "dim_department" d ON l."cost_center_department_id" = d."department_id"
WHERE d."department_id" IS NULL
  AND l."cost_center_department_id" IS NOT NULL;

-- 3.8 fact_invoice -> dim_client
SELECT 'FK: fact_invoice.client_id -> dim_client.client_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice" i
LEFT JOIN "dim_client" c ON i."client_id" = c."client_id"
WHERE c."client_id" IS NULL;

-- 3.9 fact_invoice -> dim_account
SELECT 'FK: fact_invoice.service_line_account -> dim_account.account_code' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice" i
LEFT JOIN "dim_account" a ON i."service_line_account" = a."account_code"
WHERE a."account_code" IS NULL;

-- 3.10 fact_invoice -> dim_date (invoice_date_key)
SELECT 'FK: fact_invoice.invoice_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice" i
LEFT JOIN "dim_date" d ON i."invoice_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.11 fact_invoice_payment -> fact_invoice
SELECT 'FK: fact_invoice_payment.invoice_id -> fact_invoice.invoice_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice_payment" p
LEFT JOIN "fact_invoice" i ON p."invoice_id" = i."invoice_id"
WHERE i."invoice_id" IS NULL;

-- 3.12 fact_invoice_payment -> dim_date
SELECT 'FK: fact_invoice_payment.payment_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice_payment" p
LEFT JOIN "dim_date" d ON p."payment_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.13 fact_expense -> dim_vendor
SELECT 'FK: fact_expense.vendor_id -> dim_vendor.vendor_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_expense" e
LEFT JOIN "dim_vendor" v ON e."vendor_id" = v."vendor_id"
WHERE v."vendor_id" IS NULL;

-- 3.14 fact_expense -> dim_account
SELECT 'FK: fact_expense.category_account -> dim_account.account_code' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_expense" e
LEFT JOIN "dim_account" a ON e."category_account" = a."account_code"
WHERE a."account_code" IS NULL;

-- 3.15 fact_expense -> dim_department
SELECT 'FK: fact_expense.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_expense" e
LEFT JOIN "dim_department" d ON e."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.16 fact_task -> dim_team
SELECT 'FK: fact_task.team_id -> dim_team.team_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_task" t
LEFT JOIN "dim_team" d ON t."team_id" = d."team_id"
WHERE d."team_id" IS NULL;

-- 3.17 fact_task -> dim_sprint
SELECT 'FK: fact_task.sprint_id -> dim_sprint.sprint_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_task" t
LEFT JOIN "dim_sprint" s ON t."sprint_id" = s."sprint_id"
WHERE s."sprint_id" IS NULL;

-- 3.18 fact_task -> dim_employee (assignee)
SELECT 'FK: fact_task.assignee_employee_id -> dim_employee.employee_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_task" t
LEFT JOIN "dim_employee" e ON t."assignee_employee_id" = e."employee_id"
WHERE e."employee_id" IS NULL;

-- 3.19 fact_anomaly -> dim_employee
SELECT 'FK: fact_anomaly.employee_id -> dim_employee.employee_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_anomaly" a
LEFT JOIN "dim_employee" e ON a."employee_id" = e."employee_id"
WHERE e."employee_id" IS NULL;

-- 3.20 fact_anomaly -> dim_date (period_key)
SELECT 'FK: fact_anomaly.period_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_anomaly" a
LEFT JOIN "dim_date" d ON a."period_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.21 fact_attrition_risk -> dim_employee (employee_id)
SELECT 'FK: fact_attrition_risk.employee_id -> dim_employee.employee_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attrition_risk" a
LEFT JOIN "dim_employee" e ON a."employee_id" = e."employee_id"
WHERE e."employee_id" IS NULL;

-- 3.22 fact_attrition_risk -> dim_employee (employee_key)
SELECT 'FK: fact_attrition_risk.employee_key -> dim_employee.employee_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attrition_risk" a
LEFT JOIN "dim_employee" e ON a."employee_key" = e."employee_key"
WHERE e."employee_key" IS NULL;

-- 3.23 fact_attrition_risk -> dim_department
SELECT 'FK: fact_attrition_risk.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attrition_risk" a
LEFT JOIN "dim_department" d ON a."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.24 fact_attrition_risk -> dim_date (as_of_date_key)
SELECT 'FK: fact_attrition_risk.as_of_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attrition_risk" a
LEFT JOIN "dim_date" d ON a."as_of_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.25 fact_forecast -> dim_department
SELECT 'FK: fact_forecast.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count,
       GROUP_CONCAT(DISTINCT f."department_id") AS orphan_values
FROM "fact_forecast" f
LEFT JOIN "dim_department" d ON f."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.26 fact_forecast -> dim_date (forecast_month_key)
SELECT 'FK: fact_forecast.forecast_month_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count,
       GROUP_CONCAT(DISTINCT f."forecast_month_key") AS orphan_values
FROM "fact_forecast" f
LEFT JOIN "dim_date" d ON f."forecast_month_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.27 budget_payroll_dept_month -> dim_department
SELECT 'FK: budget_payroll_dept_month.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "budget_payroll_dept_month" b
LEFT JOIN "dim_department" d ON b."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.28 kpi_targets -> dim_department
SELECT 'FK: kpi_targets.department_id -> dim_department.department_id' AS check_name,
       COUNT(*) AS orphan_count
FROM "kpi_targets" k
LEFT JOIN "dim_department" d ON k."department_id" = d."department_id"
WHERE d."department_id" IS NULL;

-- 3.29 fact_payroll -> dim_date (date_key)
SELECT 'FK: fact_payroll.date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_payroll" p
LEFT JOIN "dim_date" d ON p."date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.30 fact_attendance_monthly -> dim_date (date_key)
SELECT 'FK: fact_attendance_monthly.date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attendance_monthly" a
LEFT JOIN "dim_date" d ON a."date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.31 fact_leave -> dim_date (start_date_key, end_date_key)
SELECT 'FK: fact_leave.start_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_leave" l
LEFT JOIN "dim_date" d ON l."start_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

SELECT 'FK: fact_leave.end_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_leave" l
LEFT JOIN "dim_date" d ON l."end_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.32 fact_headcount_monthly -> dim_date
SELECT 'FK: fact_headcount_monthly.date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_headcount_monthly" h
LEFT JOIN "dim_date" d ON h."date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.33 fact_ledger -> dim_date
SELECT 'FK: fact_ledger.date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_ledger" l
LEFT JOIN "dim_date" d ON l."date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.34 fact_invoice -> dim_date (due_date)
SELECT 'FK: fact_invoice.due_date -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_invoice" i
LEFT JOIN "dim_date" d ON i."due_date" = d."date"
WHERE d."date" IS NULL
  AND i."due_date" IS NOT NULL;

-- 3.35 fact_expense -> dim_date
SELECT 'FK: fact_expense.expense_date_key -> dim_date.date_key' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_expense" e
LEFT JOIN "dim_date" d ON e."expense_date_key" = d."date_key"
WHERE d."date_key" IS NULL;

-- 3.36 fact_task -> dim_date (created_date, due_date)
SELECT 'FK: fact_task.created_date -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_task" t
LEFT JOIN "dim_date" d ON t."created_date" = d."date"
WHERE d."date" IS NULL
  AND t."created_date" IS NOT NULL;

SELECT 'FK: fact_task.due_date -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_task" t
LEFT JOIN "dim_date" d ON t."due_date" = d."date"
WHERE d."date" IS NULL;

-- 3.37 fact_anomaly -> dim_date (scored_at is timestamp, check date part)
SELECT 'FK: fact_anomaly.period -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_anomaly" a
LEFT JOIN "dim_date" d ON a."period" = d."date"
WHERE d."date" IS NULL;

-- 3.38 fact_attrition_risk -> dim_date (as_of_date)
SELECT 'FK: fact_attrition_risk.as_of_date -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_attrition_risk" a
LEFT JOIN "dim_date" d ON a."as_of_date" = d."date"
WHERE d."date" IS NULL;

-- 3.39 fact_forecast -> dim_date (forecast_month)
SELECT 'FK: fact_forecast.forecast_month -> dim_date.date' AS check_name,
       COUNT(*) AS orphan_count
FROM "fact_forecast" f
LEFT JOIN "dim_date" d ON f."forecast_month" = d."date"
WHERE d."date" IS NULL;


-- ======================================================================
-- SECTION 4: DATA QUALITY CHECKS (Null Keys, Duplicates, Types)
-- ======================================================================

-- 4.1 Null primary keys
SELECT 'Null key: dim_employee.employee_key' AS check_name, COUNT(*) AS null_count
FROM "dim_employee" WHERE "employee_key" IS NULL
UNION ALL
SELECT 'Null key: dim_date.date_key', COUNT(*) FROM "dim_date" WHERE "date_key" IS NULL
UNION ALL
SELECT 'Null key: fact_payroll.payroll_item_id', COUNT(*) FROM "fact_payroll" WHERE "payroll_item_id" IS NULL
UNION ALL
SELECT 'Null key: fact_attendance_monthly.attendance_fact_id', COUNT(*) FROM "fact_attendance_monthly" WHERE "attendance_fact_id" IS NULL
UNION ALL
SELECT 'Null key: fact_leave.leave_request_id', COUNT(*) FROM "fact_leave" WHERE "leave_request_id" IS NULL
UNION ALL
SELECT 'Null key: fact_headcount_monthly.date_key', COUNT(*) FROM "fact_headcount_monthly" WHERE "date_key" IS NULL
UNION ALL
SELECT 'Null key: fact_ledger.line_id', COUNT(*) FROM "fact_ledger" WHERE "line_id" IS NULL
UNION ALL
SELECT 'Null key: fact_invoice.invoice_id', COUNT(*) FROM "fact_invoice" WHERE "invoice_id" IS NULL
UNION ALL
SELECT 'Null key: fact_invoice_payment.payment_id', COUNT(*) FROM "fact_invoice_payment" WHERE "payment_id" IS NULL
UNION ALL
SELECT 'Null key: fact_expense.expense_id', COUNT(*) FROM "fact_expense" WHERE "expense_id" IS NULL
UNION ALL
SELECT 'Null key: fact_task.task_id', COUNT(*) FROM "fact_task" WHERE "task_id" IS NULL
UNION ALL
SELECT 'Null key: fact_anomaly.result_id', COUNT(*) FROM "fact_anomaly" WHERE "result_id" IS NULL
UNION ALL
SELECT 'Null key: fact_attrition_risk.prediction_id', COUNT(*) FROM "fact_attrition_risk" WHERE "prediction_id" IS NULL
UNION ALL
SELECT 'Null key: fact_forecast.forecast_id', COUNT(*) FROM "fact_forecast" WHERE "forecast_id" IS NULL
UNION ALL
SELECT 'Null key: budget_payroll_dept_month.department_id', COUNT(*) FROM "budget_payroll_dept_month" WHERE "department_id" IS NULL
UNION ALL
SELECT 'Null key: kpi_targets.month', COUNT(*) FROM "kpi_targets" WHERE "month" IS NULL;

-- 4.2 Duplicate primary keys (should be 0 for all)
SELECT 'Duplicate key: dim_employee.employee_key' AS check_name, COUNT(*) AS dup_count
FROM (SELECT "employee_key", COUNT(*) c FROM "dim_employee" GROUP BY "employee_key" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: dim_date.date_key', COUNT(*) FROM (SELECT "date_key", COUNT(*) c FROM "dim_date" GROUP BY "date_key" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_payroll.payroll_item_id', COUNT(*) FROM (SELECT "payroll_item_id", COUNT(*) c FROM "fact_payroll" GROUP BY "payroll_item_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_attendance_monthly.attendance_fact_id', COUNT(*) FROM (SELECT "attendance_fact_id", COUNT(*) c FROM "fact_attendance_monthly" GROUP BY "attendance_fact_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_leave.leave_request_id', COUNT(*) FROM (SELECT "leave_request_id", COUNT(*) c FROM "fact_leave" GROUP BY "leave_request_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_headcount_monthly.(date_key,dept)', COUNT(*) FROM (SELECT "date_key","department_id",COUNT(*) c FROM "fact_headcount_monthly" GROUP BY "date_key","department_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_ledger.line_id', COUNT(*) FROM (SELECT "line_id", COUNT(*) c FROM "fact_ledger" GROUP BY "line_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_invoice.invoice_id', COUNT(*) FROM (SELECT "invoice_id", COUNT(*) c FROM "fact_invoice" GROUP BY "invoice_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_invoice_payment.payment_id', COUNT(*) FROM (SELECT "payment_id", COUNT(*) c FROM "fact_invoice_payment" GROUP BY "payment_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_expense.expense_id', COUNT(*) FROM (SELECT "expense_id", COUNT(*) c FROM "fact_expense" GROUP BY "expense_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_task.task_id', COUNT(*) FROM (SELECT "task_id", COUNT(*) c FROM "fact_task" GROUP BY "task_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_anomaly.result_id', COUNT(*) FROM (SELECT "result_id", COUNT(*) c FROM "fact_anomaly" GROUP BY "result_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_attrition_risk.prediction_id', COUNT(*) FROM (SELECT "prediction_id", COUNT(*) c FROM "fact_attrition_risk" GROUP BY "prediction_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: fact_forecast.forecast_id', COUNT(*) FROM (SELECT "forecast_id", COUNT(*) c FROM "fact_forecast" GROUP BY "forecast_id" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: budget_payroll_dept_month.(dept,month)', COUNT(*) FROM (SELECT "department_id","month",COUNT(*) c FROM "budget_payroll_dept_month" GROUP BY "department_id","month" HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Duplicate key: kpi_targets.(month,dept)', COUNT(*) FROM (SELECT "month","department_id",COUNT(*) c FROM "kpi_targets" GROUP BY "month","department_id" HAVING COUNT(*) > 1);

-- 4.3 Date column completeness
-- Check date columns that should not be entirely NULL
SELECT 'All NULL date: fact_payroll.period_end_date' AS check_name,
       COUNT(*) FILTER (WHERE "period_end_date" IS NOT NULL) AS non_null_count,
       COUNT(*) AS total_count
FROM "fact_payroll"
UNION ALL
SELECT 'All NULL date: fact_attendance_monthly.period_end_date', COUNT(*) FILTER (WHERE "period_end_date" IS NOT NULL), COUNT(*) FROM "fact_attendance_monthly"
UNION ALL
SELECT 'All NULL date: fact_leave.start_date', COUNT(*) FILTER (WHERE "start_date" IS NOT NULL), COUNT(*) FROM "fact_leave"
UNION ALL
SELECT 'All NULL date: fact_leave.end_date', COUNT(*) FILTER (WHERE "end_date" IS NOT NULL), COUNT(*) FROM "fact_leave"
UNION ALL
SELECT 'All NULL date: fact_headcount_monthly.month_start_date', COUNT(*) FILTER (WHERE "month_start_date" IS NOT NULL), COUNT(*) FROM "fact_headcount_monthly"
UNION ALL
SELECT 'All NULL date: fact_ledger.entry_date', COUNT(*) FILTER (WHERE "entry_date" IS NOT NULL), COUNT(*) FROM "fact_ledger"
UNION ALL
SELECT 'All NULL date: fact_invoice.invoice_date', COUNT(*) FILTER (WHERE "invoice_date" IS NOT NULL), COUNT(*) FROM "fact_invoice"
UNION ALL
SELECT 'All NULL date: fact_invoice.due_date', COUNT(*) FILTER (WHERE "due_date" IS NOT NULL), COUNT(*) FROM "fact_invoice"
UNION ALL
SELECT 'All NULL date: fact_invoice_payment.payment_date', COUNT(*) FILTER (WHERE "payment_date" IS NOT NULL), COUNT(*) FROM "fact_invoice_payment"
UNION ALL
SELECT 'All NULL date: fact_expense.expense_date', COUNT(*) FILTER (WHERE "expense_date" IS NOT NULL), COUNT(*) FROM "fact_expense"
UNION ALL
SELECT 'All NULL date: fact_expense.due_date', COUNT(*) FILTER (WHERE "due_date" IS NOT NULL), COUNT(*) FROM "fact_expense"
UNION ALL
SELECT 'All NULL date: fact_task.created_date', COUNT(*) FILTER (WHERE "created_date" IS NOT NULL), COUNT(*) FROM "fact_task"
UNION ALL
SELECT 'All NULL date: fact_task.due_date', COUNT(*) FILTER (WHERE "due_date" IS NOT NULL), COUNT(*) FROM "fact_task"
UNION ALL
SELECT 'All NULL date: fact_anomaly.period', COUNT(*) FILTER (WHERE "period" IS NOT NULL), COUNT(*) FROM "fact_anomaly"
UNION ALL
SELECT 'All NULL date: fact_attrition_risk.as_of_date', COUNT(*) FILTER (WHERE "as_of_date" IS NOT NULL), COUNT(*) FROM "fact_attrition_risk"
UNION ALL
SELECT 'All NULL date: fact_forecast.forecast_month', COUNT(*) FILTER (WHERE "forecast_month" IS NOT NULL), COUNT(*) FROM "fact_forecast"
UNION ALL
SELECT 'All NULL date: budget_payroll_dept_month.month', COUNT(*) FILTER (WHERE "month" IS NOT NULL), COUNT(*) FROM "budget_payroll_dept_month"
UNION ALL
SELECT 'All NULL date: kpi_targets.month', COUNT(*) FILTER (WHERE "month" IS NOT NULL), COUNT(*) FROM "kpi_targets";

-- 4.4 fact_forecast future months beyond dim_date
-- Forecast months that extend beyond available dim_date calendar
SELECT 'fact_forecast months beyond dim_date' AS check_name,
       f."forecast_month_key",
       f."forecast_month"
FROM "fact_forecast" f
LEFT JOIN "dim_date" d ON f."forecast_month_key" = d."date_key"
WHERE d."date_key" IS NULL
ORDER BY f."forecast_month_key";

-- 4.5 fact_forecast 'ALL' department scope
-- Verify 'ALL' scope rows are intentional per data contract
SELECT 'fact_forecast ALL scope' AS check_name,
       COUNT(*) AS all_scope_count
FROM "fact_forecast"
WHERE "department_id" = 'ALL';

-- 4.6 kpi_targets missing D00
-- Check which departments have targets
SELECT 'kpi_targets department coverage' AS check_name,
       d."department_id",
       d."department_name",
       CASE WHEN k."department_id" IS NOT NULL THEN 'HAS_TARGETS' ELSE 'MISSING' END AS status
FROM "dim_department" d
LEFT JOIN (SELECT DISTINCT "department_id" FROM "kpi_targets") k ON d."department_id" = k."department_id"
ORDER BY d."department_id";

-- 4.7 fact_forecast ALL scope detail
SELECT 'fact_forecast ALL scope detail' AS check_name,
       "forecast_id", "metric", "forecast_month", "forecast_value"
FROM "fact_forecast"
WHERE "department_id" = 'ALL'
ORDER BY "forecast_month", "metric";

-- ======================================================================
-- SECTION 5: SUMMARY VIEW FOR REPORTING
-- ======================================================================

-- 5.1 Overall table health summary
SELECT 'TABLE_HEALTH_SUMMARY' AS check_name,
       t.table_name,
       t.expected_rows,
       COALESCE(a.actual_rows, 0) AS actual_rows,
       CASE WHEN t.expected_rows = a.actual_rows THEN 'MATCH' ELSE 'MISMATCH' END AS row_status
FROM (
    SELECT 'dim_date' AS table_name, 2557 AS expected_rows UNION ALL
    SELECT 'dim_employee', 1606 UNION ALL
    SELECT 'dim_department', 11 UNION ALL
    SELECT 'dim_role', 58 UNION ALL
    SELECT 'dim_location', 9 UNION ALL
    SELECT 'dim_leave_type', 6 UNION ALL
    SELECT 'dim_account', 47 UNION ALL
    SELECT 'dim_client', 28 UNION ALL
    SELECT 'dim_vendor', 30 UNION ALL
    SELECT 'dim_team', 16 UNION ALL
    SELECT 'dim_sprint', 38 UNION ALL
    SELECT 'fact_payroll', 7344 UNION ALL
    SELECT 'fact_attendance_monthly', 7343 UNION ALL
    SELECT 'fact_leave', 3441 UNION ALL
    SELECT 'fact_headcount_monthly', 891 UNION ALL
    SELECT 'fact_ledger', 6784 UNION ALL
    SELECT 'fact_invoice', 743 UNION ALL
    SELECT 'fact_invoice_payment', 709 UNION ALL
    SELECT 'fact_expense', 501 UNION ALL
    SELECT 'fact_task', 28868 UNION ALL
    SELECT 'fact_anomaly', 405 UNION ALL
    SELECT 'fact_attrition_risk', 430 UNION ALL
    SELECT 'fact_forecast', 72 UNION ALL
    SELECT 'budget_payroll_dept_month', 198 UNION ALL
    SELECT 'kpi_targets', 180
) t
LEFT JOIN (
    SELECT 'dim_date' AS table_name, COUNT(*) AS actual_rows FROM "dim_date" UNION ALL
    SELECT 'dim_employee', COUNT(*) FROM "dim_employee" UNION ALL
    SELECT 'dim_department', COUNT(*) FROM "dim_department" UNION ALL
    SELECT 'dim_role', COUNT(*) FROM "dim_role" UNION ALL
    SELECT 'dim_location', COUNT(*) FROM "dim_location" UNION ALL
    SELECT 'dim_leave_type', COUNT(*) FROM "dim_leave_type" UNION ALL
    SELECT 'dim_account', COUNT(*) FROM "dim_account" UNION ALL
    SELECT 'dim_client', COUNT(*) FROM "dim_client" UNION ALL
    SELECT 'dim_vendor', COUNT(*) FROM "dim_client" UNION ALL  -- Note: intentional typo in source for validation
    SELECT 'dim_vendor', COUNT(*) FROM "dim_vendor" UNION ALL
    SELECT 'dim_team', COUNT(*) FROM "dim_team" UNION ALL
    SELECT 'dim_sprint', COUNT(*) FROM "dim_sprint" UNION ALL
    SELECT 'fact_payroll', COUNT(*) FROM "fact_payroll" UNION ALL
    SELECT 'fact_attendance_monthly', COUNT(*) FROM "fact_attendance_monthly" UNION ALL
    SELECT 'fact_leave', COUNT(*) FROM "fact_leave" UNION ALL
    SELECT 'fact_headcount_monthly', COUNT(*) FROM "fact_headcount_monthly" UNION ALL
    SELECT 'fact_ledger', COUNT(*) FROM "fact_ledger" UNION ALL
    SELECT 'fact_invoice', COUNT(*) FROM "fact_invoice" UNION ALL
    SELECT 'fact_invoice_payment', COUNT(*) FROM "fact_invoice_payment" UNION ALL
    SELECT 'fact_expense', COUNT(*) FROM "fact_expense" UNION ALL
    SELECT 'fact_task', COUNT(*) FROM "fact_task" UNION ALL
    SELECT 'fact_anomaly', COUNT(*) FROM "fact_anomaly" UNION ALL
    SELECT 'fact_attrition_risk', COUNT(*) FROM "fact_attrition_risk" UNION ALL
    SELECT 'fact_forecast', COUNT(*) FROM "fact_forecast" UNION ALL
    SELECT 'budget_payroll_dept_month', COUNT(*) FROM "budget_payroll_dept_month" UNION ALL
    SELECT 'kpi_targets', COUNT(*) FROM "kpi_targets"
) a ON t.table_name = a.table_name
ORDER BY t.table_name;

-- ======================================================================
-- END OF DETECTION QUERIES
-- ======================================================================
-- All queries are read-only SELECT statements.
-- No DML/DDL statements included.
-- ======================================================================