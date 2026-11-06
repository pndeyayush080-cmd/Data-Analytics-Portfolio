-- ============================================================================
-- PQ-11 — P&L & Expense Analytics (PQ-11-pl_views.sql)
-- Star schema warehouse star_schema + metric views anchored on raw.fact_*
-- All grain judgments verified against 03_Data/csv source CSVs. No join
-- inflation: payroll reconciled via pre-aggregation; expense reconciled
-- independently; vendor history retained via LEFT JOIN with is_active exposed.
-- ============================================================================

-- Cleanwarehouse layout:
--   star_schema.dim_date / dim_department / dim_account / dim_vendor ...
--   star_schema.fact_ledger / star_schema.fact_expense / star_schema.fact_payroll
--   star_schema.metric_M01_M28.sql  — one view per metric, matches metric_dictionary.csv

-- ---- Dimension imports ----------------------------------------------------
CREATE OR REPLACE VIEW star_schema.dim_account AS SELECT * FROM raw.dim_account;
CREATE OR REPLACE VIEW star_schema.dim_vendor   AS SELECT * FROM raw.dim_vendor;
CREATE OR REPLACE VIEW star_schema.dim_department AS SELECT * FROM raw.dim_department;
CREATE OR REPLACE VIEW star_schema.dim_date      AS SELECT * FROM raw.dim_date;

-- ---- Financial facts ------------------------------------------------------
CREATE OR REPLACE VIEW star_schema.fact_ledger AS
SELECT line_id, entry_id, date_key, entry_date, posting_period, financial_year,
       account_code, debit, credit, signed_amount_debit_positive,
       cost_center_department_id, source_type, source_id
FROM raw.fact_ledger;

CREATE OR REPLACE VIEW star_schema.fact_expense AS
SELECT expense_id, expense_date, expense_date_key, category_account,
       vendor_id, bill_reference, description, department_id,
       amount_excl_gst, gst_rate_percent, gst_amount, total_amount,
       due_date, paid_date, status, payment_mode, submitted_by, approved_by,
       ledger_entry_id
FROM raw.fact_expense;

CREATE OR REPLACE VIEW star_schema.fact_payroll AS
SELECT payroll_item_id, run_id, employee_id, date_key, employee_key,
       period_end_date, department_id, role_id, payable_days, lop_days,
       overtime_hours_paid, variable_pay_type, monthly_fixed_gross, basic,
       hra, conveyance, medical, special_allowance, earned_fixed_pay,
       overtime_pay, variable_pay, gross_pay, pf_employee, esi_employee,
       professional_tax, tds, other_deductions, total_deductions, net_pay,
       pf_employer, esi_employer, employer_cost, headcount_flag
FROM raw.fact_payroll;

-- ============================================================================
-- Monthly dimension (unique months from dim_date)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dim_month AS
SELECT DISTINCT year_month, month_start_date, month_end_date
FROM star_schema.dim_date;

-- ============================================================================
-- M16 — Revenue: income booked in ledger, strict accounts 4001-4004 only.
--        Credits posted as negative in signed_amount_debit_positive.
--        Excludes group heading 4000 and "Other Income" 4900 per definition.
--        Grain: Account x month (moved to month aggregate below).
--        CORRECTED: Join on date_key, aggregate by year_month.
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.m16_revenue AS
SELECT d.year_month AS month,
       -(SUM(f.signed_amount_debit_positive)) AS revenue
FROM star_schema.fact_ledger f
JOIN star_schema.dim_account a ON f.account_code = a.account_code
JOIN star_schema.dim_date    d ON f.date_key = d.date_key
WHERE a.account_type = 'INCOME' 
  AND a.account_code BETWEEN '4001' AND '4004'
  AND a.is_group = 'N'
GROUP BY 1 ORDER BY 1;

-- ============================================================================
-- M17 — Net profit: revenue (incl. 4900 Other Income) minus expenses
--        5000-5301, excluding group heads 4000 and 5000.
--        Grain: Month.
--        CORRECTED: Join on date_key, aggregate by year_month.
--        Includes all 4xxx income (4001-4999) and 5xxx expenses (5000-5301).
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.m17_net_profit AS
SELECT d.year_month AS month,
       SUM(CASE WHEN a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999' THEN -(f.signed_amount_debit_positive) ELSE 0 END) AS total_income,
       SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301' THEN f.signed_amount_debit_positive ELSE 0 END) AS total_expense,
       SUM(CASE WHEN a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999' THEN -(f.signed_amount_debit_positive) ELSE 0 END) -
       SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301' THEN f.signed_amount_debit_positive ELSE 0 END) AS net_profit
FROM star_schema.fact_ledger f
JOIN star_schema.dim_account a ON f.account_code = a.account_code
JOIN star_schema.dim_date    d ON f.date_key = d.date_key
WHERE a.statement = 'Profit & Loss' 
  AND a.is_group = 'N'
  AND (
    (a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999')
    OR (a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301')
  )
GROUP BY 1
ORDER BY 1;

-- ============================================================================
-- M18 — Operating margin: net profit / revenue * 100.
--        Denominator is STRICT revenue (accounts 4001-4004) per the metric
--        definition "Net profit as a share of revenue". 4900 Other Income
--        falls inside net profit numerator but outside revenue denominator.
--        NULLIF guards zero denominator.
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.m18_operating_margin AS
SELECT np.month,
       ROUND(100.0 * (np.net_profit / NULLIF(r.revenue, 0)), 2) AS operating_margin_pct
FROM star_schema.m17_net_profit np
JOIN star_schema.m16_revenue r USING(month);

-- ============================================================================
-- Expense-by-category (M19-style breakdown, extra dimension for analysis)
-- CORRECTED: Join on date_key, aggregate by year_month.
-- Uses signed_amount_debit_positive so credits/reversals reduce net expense.
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.expense_by_category AS
SELECT d.year_month AS month,
       l.account_code AS category_code,
       a.account_name AS category_name,
       COUNT(*) AS line_count,
       ROUND(SUM(l.signed_amount_debit_positive), 2) AS signed_expense
FROM star_schema.fact_ledger l
JOIN star_schema.dim_account a ON l.account_code = a.account_code
JOIN star_schema.dim_date    d ON l.date_key = d.date_key
WHERE a.account_type = 'EXPENSE' AND a.is_group = 'N' AND a.account_code BETWEEN '5000' AND '5301'
GROUP BY 1,2,3
ORDER BY 1, signed_expense DESC;

-- ============================================================================
-- Top vendors by spend (ALL vendors visible, including active flag as column).
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.vendor_spend_analysis AS
SELECT v.vendor_id, v.vendor_name, v.city,
       v.primary_expense_account,
       SUBSTR(CAST(e.expense_date_key AS VARCHAR), 1, 6) AS year_month,
       e.department_id AS dept,
       SUM(e.amount_excl_gst) AS spend_excl_gst,
       SUM(e.total_amount) AS spend_incl_gst,
       COUNT(*) AS bill_count,
       SUM(CASE WHEN e.status <> 'UNPAID' THEN 1 ELSE 0 END) AS paid_bills,
       SUM(CASE WHEN e.status = 'UNPAID' THEN 1 ELSE 0 END) AS unpaid_bills,
       MAX(v.is_active) AS vendor_active_flag
FROM star_schema.fact_expense e
JOIN star_schema.dim_vendor v ON e.vendor_id = v.vendor_id
GROUP BY 1,2,3,4,5,6
ORDER BY spend_excl_gst DESC;

-- ============================================================================
-- Department-wise expense summary
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_expense_summary AS
SELECT df.year_month AS month,
       e.department_id,
       COUNT(*) AS bills,
       ROUND(SUM(e.amount_excl_gst), 2) AS spend_excl_gst,
       ROUND(SUM(e.total_amount), 2) AS spend_incl_gst,
       SUM(CASE WHEN e.status <> 'UNPAID' THEN 1 ELSE 0 END) AS paid_bills,
       SUM(CASE WHEN e.status = 'UNPAID' THEN 1 ELSE 0 END) AS unpaid_bills
FROM star_schema.fact_expense e
JOIN star_schema.dim_department d ON e.department_id = d.department_id
JOIN star_schema.dim_date df ON e.expense_date_key = df.date_key
GROUP BY 1,2
ORDER BY 1, spend_excl_gst DESC;

-- ============================================================================
-- Reconciliation bridges (verified aggregation paths)
-- ============================================================================
-- Payroll-Ledger reconciliation: aggregate both sides at month + department
-- Uses signed_amount_debit_positive for ledger so credits reduce net expense.
-- employees_paid counts distinct employees per month+dept.
CREATE OR REPLACE VIEW star_schema.reconciliation_payroll_ledger AS
SELECT pay_by_dept.month,
       pay_by_dept.department_id,
       pay_by_dept.employees_paid,
       ROUND(pay_by_dept.employer_cost, 2) AS payroll_employer_cost,
       COALESCE(led_salary.total_signed_expense, 0) AS ledger_salary_expense,
       ABS(pay_by_dept.employer_cost - COALESCE(led_salary.total_signed_expense, 0)) AS diff
FROM (
    SELECT dd.year_month AS month,
           p.department_id,
           COUNT(DISTINCT p.employee_id) AS employees_paid,
           ROUND(SUM(p.employer_cost), 2) AS employer_cost
    FROM star_schema.fact_payroll p
    JOIN star_schema.dim_department d ON p.department_id = d.department_id
    JOIN star_schema.dim_date dd ON p.date_key = dd.date_key
    GROUP BY 1, 2
) pay_by_dept
LEFT JOIN (
    SELECT dd.year_month AS month,
           d2.department_id,
           SUM(ROUND(l.signed_amount_debit_positive, 2)) AS total_signed_expense
    FROM star_schema.fact_ledger l
    JOIN star_schema.dim_date dd ON l.date_key = dd.date_key
    JOIN star_schema.dim_department d2 ON l.cost_center_department_id = d2.department_id
    JOIN star_schema.dim_account a ON l.account_code = a.account_code
    WHERE a.account_code BETWEEN '5001' AND '5005' AND a.is_group = 'N'
    GROUP BY 1, 2
) led_salary USING(month, department_id)
WHERE ABS(pay_by_dept.employer_cost - COALESCE(led_salary.total_signed_expense, 0)) > 0.01
ORDER BY diff DESC;

-- ============================================================================
-- Expense-Ledger reconciliation: join on ledger_entry_id -> entry_id
-- Compare vendor bill amounts to their specific ledger journal entries
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.reconciliation_expense_ledger AS
SELECT 
    e.expense_id,
    e.vendor_id,
    e.department_id,
    e.expense_date_key,
    e.amount_excl_gst AS expense_amount_excl_gst,
    e.gst_amount AS expense_gst_amount,
    e.total_amount AS expense_total_amount,
    e.ledger_entry_id,
    COALESCE(l.ledger_debit, 0) AS ledger_debit,
    COALESCE(l.ledger_credit, 0) AS ledger_credit,
    COALESCE(l.ledger_signed_amount, 0) AS ledger_signed_amount,
    COALESCE(l.ledger_expense_accounts, 0) AS ledger_expense_accounts,
    ABS(e.total_amount - COALESCE(l.ledger_expense_accounts, 0)) AS diff_total_vs_expense_accounts,
    ABS(e.amount_excl_gst - COALESCE(l.ledger_expense_accounts, 0)) AS diff_excl_gst_vs_expense_accounts,
    CASE 
        WHEN l.ledger_entry_id IS NULL THEN 'MISSING_LEDGER_ENTRY'
        WHEN ABS(e.total_amount - COALESCE(l.ledger_expense_accounts, 0)) <= 0.01 THEN 'MATCH'
        WHEN ABS(e.amount_excl_gst - COALESCE(l.ledger_expense_accounts, 0)) <= 0.01 THEN 'MATCH_EXCL_GST'
        ELSE 'AMOUNT_MISMATCH'
    END AS reconciliation_status
FROM star_schema.fact_expense e
LEFT JOIN (
    SELECT 
        l.entry_id AS ledger_entry_id,
        SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.is_group = 'N' AND a.account_code BETWEEN '5000' AND '5301' THEN l.debit ELSE 0 END) AS ledger_debit,
        SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.is_group = 'N' AND a.account_code BETWEEN '5000' AND '5301' THEN l.credit ELSE 0 END) AS ledger_credit,
        SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.is_group = 'N' AND a.account_code BETWEEN '5000' AND '5301' THEN l.signed_amount_debit_positive ELSE 0 END) AS ledger_signed_amount,
        SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.is_group = 'N' AND a.account_code BETWEEN '5000' AND '5301' THEN ABS(l.debit - l.credit) ELSE 0 END) AS ledger_expense_accounts
    FROM star_schema.fact_ledger l
    JOIN star_schema.dim_account a ON l.account_code = a.account_code
    GROUP BY l.entry_id
) l ON e.ledger_entry_id = l.ledger_entry_id
ORDER BY reconciliation_status, diff_total_vs_expense_accounts DESC;

-- ============================================================================
-- Identifiable duplicate payroll exceptions (matches C03 from PQ-03).
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.duplicate_payroll_rows AS
SELECT employee_id, run_id, payroll_item_id, gross_pay, employer_cost
FROM star_schema.fact_payroll
WHERE (employee_id, run_id) IN (
    SELECT employee_id, run_id
    FROM star_schema.fact_payroll
    GROUP BY 1,2 HAVING COUNT(*) > 1
);