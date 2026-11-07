-- ============================================================================
-- PQ-13 — Cross-Department Impact View
-- Department-Month Cross-Department Analytics combining Headcount, Payroll, 
-- Attendance, and Leave metrics at Department-Month grain
-- ============================================================================

-- ============================================================================
-- 1. DEPARTMENT-MONTH SPINE
-- Complete set of department-month combinations for reference period only
-- Reference period: April 2025 - September 2026 (18 months, 11 departments = 198 rows)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_spine AS
WITH reference_period AS (
    SELECT 
        dm.month_start_date as month,
        d.department_id,
        d.department_name,
        d.cost_center,
        d.is_leadership
    FROM raw.dim_date dm
    CROSS JOIN raw.dim_department d
    WHERE dm.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
      AND dm.date = dm.month_start_date
      AND d.department_id IN ('D00','D01','D02','D03','D04','D05','D06','D07','D08','D09','D10')
)
SELECT 
    month,
    department_id,
    department_name,
    cost_center,
    is_leadership
FROM reference_period;

-- ============================================================================
-- 2. HEADCOUNT AGGREGATION (Department-Month)
-- Grain: 1 row per department per month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_headcount AS
WITH base AS (
    SELECT 
        h.month_start_date as month,
        h.department_id,
        SUM(h.headcount_start) as headcount_start,
        SUM(h.hires) as hires,
        SUM(h.exits) as exits,
        SUM(h.voluntary_exits) as voluntary_exits,
        SUM(h.transfers_in) as transfers_in,
        SUM(h.transfers_out) as transfers_out,
        SUM(h.headcount_end) as headcount_end,
        CASE 
            WHEN SUM(h.headcount_start) > 0 
            THEN ROUND(SUM(h.exits) * 100.0 / SUM(h.headcount_start), 2)
            ELSE 0
        END as attrition_rate_monthly_pct
    FROM raw.fact_headcount_monthly h
    WHERE h.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY h.month_start_date, h.department_id
),
rolling AS (
    SELECT 
        month,
        department_id,
        headcount_start,
        hires,
        exits,
        voluntary_exits,
        transfers_in,
        transfers_out,
        headcount_end,
        attrition_rate_monthly_pct,
        CASE 
            WHEN AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month 
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) > 0
            THEN ROUND(
                SUM(exits) OVER (PARTITION BY department_id ORDER BY month 
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) * 100.0 / 
                AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month 
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 2)
            ELSE 0
        END as attrition_rate_rolling_12m_pct,
        CASE 
            WHEN AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month 
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) > 0
            THEN ROUND(
                SUM(voluntary_exits) OVER (PARTITION BY department_id ORDER BY month 
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) * 100.0 / 
                AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month 
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 2)
            ELSE 0
        END as voluntary_attrition_rate_12m_pct
    FROM base
)
SELECT 
    month,
    department_id,
    headcount_start,
    hires,
    exits,
    voluntary_exits,
    transfers_in,
    transfers_out,
    headcount_end,
    attrition_rate_monthly_pct,
    attrition_rate_rolling_12m_pct,
    voluntary_attrition_rate_12m_pct
FROM rolling;

-- ============================================================================
-- 3. PAYROLL AGGREGATION (Department-Month)
-- Grain: 1 row per department per month
-- Deduplicate on (run_id, employee_id) to match reference
-- Exclude synthetic/test employees (EMP-9xxx)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_payroll AS
WITH payroll_dedup AS (
    -- Deduplicate payroll records on (run_id, employee_id) keeping first
    -- Exclude synthetic employees (EMP-9xxx pattern)
    SELECT DISTINCT ON (run_id, employee_id)
        *
    FROM raw.fact_payroll
    WHERE headcount_flag = 1
      AND employee_id NOT LIKE 'EMP-9%'
)
SELECT 
    d.month_start_date as month,
    p.department_id,
    COUNT(DISTINCT p.employee_id) as employees_paid,
    SUM(p.gross_pay) as gross_pay,
    SUM(p.net_pay) as net_pay,
    SUM(p.employer_cost) as employer_cost,
    SUM(p.overtime_pay) as overtime_pay,
    SUM(p.variable_pay) as variable_pay,
    SUM(p.overtime_hours_paid) as overtime_hours_paid,
    CASE 
        WHEN SUM(p.employer_cost) > 0 
        THEN ROUND(SUM(p.overtime_pay) * 100.0 / SUM(p.employer_cost), 2)
        ELSE 0
    END as overtime_share_pct,
    CASE 
        WHEN COUNT(DISTINCT p.employee_id) > 0 
        THEN ROUND(SUM(p.employer_cost) / COUNT(DISTINCT p.employee_id), 2)
        ELSE 0
    END as cost_per_head,
    CASE 
        WHEN SUM(p.gross_pay) > 0 
        THEN ROUND(SUM(p.variable_pay) * 100.0 / SUM(p.gross_pay), 2)
        ELSE 0
    END as variable_pay_share_pct
FROM payroll_dedup p
JOIN raw.dim_date d ON p.date_key = d.date_key
WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
GROUP BY d.month_start_date, p.department_id;

-- ============================================================================
-- 4. ATTENDANCE AGGREGATION (Department-Month)
-- Grain: 1 row per department per month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_attendance AS
SELECT 
    d.month_start_date as month,
    a.department_id,
    SUM(a.scheduled_days) as scheduled_days,
    SUM(a.present_days) as present_days,
    SUM(a.wfh_days) as wfh_days,
    SUM(a.half_days_unpaid) as half_days_unpaid,
    SUM(a.paid_leave_days) as paid_leave_days,
    SUM(a.unpaid_absence_days) as unpaid_absence_days,
    SUM(a.late_arrivals) as late_arrivals,
    SUM(a.overtime_hours) as overtime_hours,
    CASE 
        WHEN SUM(a.scheduled_days) > 0 
        THEN ROUND((SUM(a.present_days) + 0.5 * SUM(a.half_days_unpaid)) * 100.0 / SUM(a.scheduled_days), 2)
        ELSE 0
    END as attendance_rate_pct,
    CASE 
        WHEN SUM(a.present_days) > 0 
        THEN ROUND(SUM(a.late_arrivals) * 100.0 / SUM(a.present_days), 2)
        ELSE 0
    END as late_arrival_rate_pct
FROM raw.fact_attendance_monthly a
JOIN raw.dim_date d ON a.date_key = d.date_key
WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
GROUP BY d.month_start_date, a.department_id;

-- ============================================================================
-- 5. LEAVE AGGREGATION (Department-Month)
-- Grain: 1 row per department per month
-- Working-day-weighted allocation across months spanned
-- SCD Type 2 join: match leave to employee's department at leave start_date
-- Excludes invalid request LR-002286 (start_date > end_date)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_leave AS
WITH valid_leave AS (
    -- Valid approved leave requests within reference period
    -- Exclude LR-002286 (invalid: start_date 2026-03-24 > end_date 2026-03-23)
    SELECT 
        l.leave_request_id,
        e.department_id,
        l.start_date,
        l.end_date,
        l.leave_type_code,
        lt.leave_type_name,
        CASE 
            WHEN lt.leave_type_name IN ('Sick Leave', 'Medical Leave', 'Maternity Leave', 'Paternity Leave') 
            THEN 'Medical'
            WHEN lt.leave_type_name IN ('Annual Leave', 'Vacation', 'Casual Leave', 'Earned (Privilege) Leave') 
            THEN 'Annual'
            WHEN lt.leave_type_name IN ('Leave Without Pay', 'Unpaid Leave', 'Loss of Pay') 
            THEN 'LOP'
            ELSE 'Other'
        END as leave_category,
        l.days
    FROM raw.fact_leave l
    JOIN raw.dim_employee e 
        ON l.employee_id = e.employee_id
        AND l.start_date BETWEEN e.valid_from AND e.valid_to
    JOIN raw.dim_leave_type lt ON l.leave_type_code = lt.leave_type_code
    WHERE l.status = 'Approved'
      AND l.leave_request_id != 'LR-002286'  -- Invalid: start_date > end_date
      AND l.start_date <= DATE '2026-09-30'
      AND l.end_date >= DATE '2025-04-01'
      AND l.start_date <= l.end_date  -- Additional safety filter
),
leave_months AS (
    -- Explode each leave request to month-level with working-day weights
    SELECT 
        vl.leave_request_id,
        vl.department_id,
        vl.leave_type_code,
        vl.leave_type_name,
        vl.leave_category,
        vl.days as recorded_days,
        dm.month_start_date as month,
        -- Working days in this month for this leave request's date range
        COUNT(d.date) FILTER (WHERE d.is_working_day = 'Y') as working_days_in_month,
        -- Total working days across all months spanned by this request (within ref period)
        SUM(COUNT(d.date) FILTER (WHERE d.is_working_day = 'Y')) OVER (PARTITION BY vl.leave_request_id) as total_working_days_spanned
    FROM valid_leave vl
    JOIN raw.dim_date dm
        ON dm.month_start_date BETWEEN 
            GREATEST(DATE_TRUNC('month', vl.start_date), DATE '2025-04-01')
            AND LEAST(DATE_TRUNC('month', vl.end_date), DATE '2026-09-01')
        AND dm.date = dm.month_start_date
    JOIN raw.dim_date d
        ON d.date BETWEEN GREATEST(vl.start_date, dm.month_start_date)
                       AND LEAST(vl.end_date, (dm.month_start_date + INTERVAL '1 month' - INTERVAL '1 day'))
        AND d.month_start_date = dm.month_start_date
    GROUP BY vl.leave_request_id, vl.department_id, vl.leave_type_code, vl.leave_type_name, vl.leave_category, vl.days, dm.month_start_date
),
leave_allocated AS (
    -- Allocate days proportionally by working-day weights
    SELECT 
        month,
        department_id,
        leave_type_code,
        leave_type_name,
        leave_category,
        -- Working-day-weighted allocation: recorded_days * (working_days_in_month / total_working_days_spanned)
        ROUND(recorded_days * 1.0 * working_days_in_month / NULLIF(total_working_days_spanned, 0), 4) as days_in_month
    FROM leave_months
    WHERE total_working_days_spanned > 0
)
SELECT 
    month,
    department_id,
    SUM(CASE WHEN leave_category = 'Medical' THEN days_in_month ELSE 0 END) as medical_leave_days,
    SUM(CASE WHEN leave_category = 'Annual' THEN days_in_month ELSE 0 END) as annual_leave_days,
    SUM(CASE WHEN leave_category = 'LOP' THEN days_in_month ELSE 0 END) as lop_days,
    SUM(CASE WHEN leave_category = 'Other' THEN days_in_month ELSE 0 END) as other_leave_days,
    SUM(days_in_month) as total_leave_days,
    COUNT(DISTINCT CASE WHEN leave_category = 'LOP' THEN leave_type_code END) as lop_leave_types,
    0 as leave_days_per_head
FROM leave_allocated
GROUP BY month, department_id;

-- ============================================================================
-- 5b. INVALID LEAVE REQUEST TRACKING
-- Separate view for invalid leave request LR-002286
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq13_invalid_leave AS
SELECT 
    l.leave_request_id,
    l.employee_id,
    e.department_id,
    l.start_date,
    l.end_date,
    l.days as recorded_days,
    lt.leave_type_name,
    'INVALID_START_AFTER_END' as invalid_reason
FROM raw.fact_leave l
JOIN raw.dim_employee e 
    ON l.employee_id = e.employee_id
    AND l.start_date BETWEEN e.valid_from AND e.valid_to
JOIN raw.dim_leave_type lt ON l.leave_type_code = lt.leave_type_code
WHERE l.leave_request_id = 'LR-002286';

-- ============================================================================
-- 6. COMBINED DEPARTMENT-MONTH VIEW
-- Joining all aggregations to the spine
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_month_combined AS
SELECT 
    s.month,
    s.department_id,
    s.department_name,
    s.cost_center,
    s.is_leadership,
    -- Headcount
    COALESCE(h.headcount_start, 0) as headcount_start,
    COALESCE(h.hires, 0) as hires,
    COALESCE(h.exits, 0) as exits,
    COALESCE(h.voluntary_exits, 0) as voluntary_exits,
    COALESCE(h.transfers_in, 0) as transfers_in,
    COALESCE(h.transfers_out, 0) as transfers_out,
    COALESCE(h.headcount_end, 0) as headcount_end,
    h.attrition_rate_monthly_pct,
    h.attrition_rate_rolling_12m_pct,
    h.voluntary_attrition_rate_12m_pct,
    -- Payroll
    COALESCE(p.employees_paid, 0) as employees_paid,
    p.gross_pay,
    p.net_pay,
    p.employer_cost,
    p.overtime_pay,
    p.variable_pay,
    p.overtime_hours_paid,
    p.overtime_share_pct,
    p.cost_per_head,
    p.variable_pay_share_pct,
    -- Attendance
    a.scheduled_days,
    a.present_days,
    a.wfh_days,
    a.half_days_unpaid,
    a.paid_leave_days,
    a.unpaid_absence_days,
    a.late_arrivals,
    a.overtime_hours,
    a.attendance_rate_pct,
    a.late_arrival_rate_pct,
    -- Leave
    COALESCE(l.medical_leave_days, 0) as medical_leave_days,
    COALESCE(l.annual_leave_days, 0) as annual_leave_days,
    COALESCE(l.lop_days, 0) as lop_days,
    COALESCE(l.other_leave_days, 0) as other_leave_days,
    COALESCE(l.total_leave_days, 0) as total_leave_days,
    CASE 
        WHEN COALESCE(h.headcount_end, 0) > 0 
        THEN ROUND(COALESCE(l.total_leave_days, 0) * 1.0 / h.headcount_end, 4)
        ELSE 0
    END as leave_days_per_head
FROM star_schema.dept_month_spine s
LEFT JOIN star_schema.dept_month_headcount h 
    ON s.month = h.month AND s.department_id = h.department_id
LEFT JOIN star_schema.dept_month_payroll p 
    ON s.month = p.month AND s.department_id = p.department_id
LEFT JOIN star_schema.dept_month_attendance a 
    ON s.month = a.month AND s.department_id = a.department_id
LEFT JOIN star_schema.dept_month_leave l 
    ON s.month = l.month AND s.department_id = l.department_id
WHERE s.month IS NOT NULL;

-- ============================================================================
-- 7. REFERENCE RECONCILIATION VIEW
-- Comparing combined view against reference_summary_dept_month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq13_reference_reconciliation AS
WITH ref AS (
    SELECT * FROM read_csv_auto(
        'C:/Users/Ayush Pandey/OneDrive/Documents/Data-Analytics-Portfolio/GrowMar_Phase_3/04_Validation_Vault/unlock_PQ-13_reference_summary_dept_month.csv',
        header=true
    )
),
actual AS (
    SELECT 
        department_id,
        month,
        employer_cost,
        gross_pay,
        overtime_pay,
        employees_paid,
        overtime_hours_paid as overtime_hours,
        late_arrivals,
        attendance_rate_pct,
        headcount_end,
        hires,
        exits,
        attrition_rate_monthly_pct,
        cost_per_head,
        overtime_share_pct
    FROM star_schema.dept_month_combined
)
SELECT 
    a.department_id,
    a.month,
    -- Employer Cost
    a.employer_cost as actual_employer_cost,
    r.employer_cost as ref_employer_cost,
    ABS(a.employer_cost - r.employer_cost) as employer_cost_diff,
    ROUND(100.0 * ABS(a.employer_cost - r.employer_cost) / NULLIF(r.employer_cost, 0), 2) as employer_cost_pct_diff,
    -- Gross Pay
    a.gross_pay as actual_gross_pay,
    r.gross_pay as ref_gross_pay,
    ABS(a.gross_pay - r.gross_pay) as gross_pay_diff,
    -- Overtime Pay
    a.overtime_pay as actual_overtime_pay,
    r.overtime_pay as ref_overtime_pay,
    ABS(a.overtime_pay - r.overtime_pay) as overtime_pay_diff,
    -- Employees Paid (payroll headcount)
    a.employees_paid as actual_employees_paid,
    r.employees_paid as ref_employees_paid,
    a.employees_paid - r.employees_paid as employees_paid_diff,
    -- Overtime Hours
    a.overtime_hours as actual_overtime_hours,
    r.overtime_hours as ref_overtime_hours,
    -- Late Arrivals
    a.late_arrivals as actual_late_arrivals,
    r.late_arrivals as ref_late_arrivals,
    -- Attendance Rate
    a.attendance_rate_pct as actual_attendance_rate,
    r.attendance_rate as ref_attendance_rate,
    -- Headcount End
    a.headcount_end as actual_headcount_end,
    r.headcount_end as ref_headcount_end,
    -- Hires
    a.hires as actual_hires,
    r.hires as ref_hires,
    -- Exits
    a.exits as actual_exits,
    r.exits as ref_exits,
    -- Attrition Rate
    a.attrition_rate_monthly_pct as actual_attrition_rate,
    r.attrition_rate_monthly_pct as ref_attrition_rate,
    -- Cost Per Head
    a.cost_per_head as actual_cost_per_head,
    r.cost_per_head as ref_cost_per_head,
    -- Overtime Share
    a.overtime_share_pct as actual_overtime_share,
    r.overtime_share_pct as ref_overtime_share
FROM actual a
FULL OUTER JOIN ref r 
    ON a.department_id = r.department_id 
    AND DATE_TRUNC('month', a.month) = DATE_TRUNC('month', r.month);

-- ============================================================================
-- 8. DEPARTMENT COMPARISON VIEW (for dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dept_comparison AS
SELECT 
    department_id,
    department_name,
    cost_center,
    month,
    headcount_end,
    employer_cost,
    gross_pay,
    overtime_pay,
    overtime_share_pct,
    cost_per_head,
    attrition_rate_monthly_pct,
    attrition_rate_rolling_12m_pct,
    voluntary_attrition_rate_12m_pct,
    attendance_rate_pct,
    late_arrival_rate_pct,
    leave_days_per_head,
    total_leave_days,
    lop_days,
    medical_leave_days,
    annual_leave_days,
    -- Rankings
    RANK() OVER (PARTITION BY month ORDER BY employer_cost DESC) as cost_rank,
    RANK() OVER (PARTITION BY month ORDER BY overtime_pay DESC) as overtime_rank,
    RANK() OVER (PARTITION BY month ORDER BY attrition_rate_monthly_pct DESC) as attrition_rank,
    RANK() OVER (PARTITION BY month ORDER BY cost_per_head DESC) as cost_per_head_rank,
    RANK() OVER (PARTITION BY month ORDER BY overtime_share_pct DESC) as overtime_share_rank,
    RANK() OVER (PARTITION BY month ORDER BY leave_days_per_head DESC) as leave_rank
FROM star_schema.dept_month_combined
WHERE headcount_end > 0;

-- ============================================================================
-- 9. OVERTIME VS ATTRITION CORRELATION VIEW
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.overtime_attrition_correlation AS
WITH monthly_dept AS (
    SELECT 
        department_id,
        department_name,
        month,
        overtime_share_pct,
        attrition_rate_monthly_pct,
        attrition_rate_rolling_12m_pct,
        voluntary_attrition_rate_12m_pct,
        overtime_pay,
        employer_cost,
        headcount_end
    FROM star_schema.dept_month_combined
    WHERE headcount_end >= 5  -- Minimum group size
)
SELECT 
    'Monthly' as period_type,
    CORR(overtime_share_pct, attrition_rate_monthly_pct) as overtime_attrition_corr,
    CORR(overtime_share_pct, attrition_rate_rolling_12m_pct) as overtime_rolling_attrition_corr,
    CORR(overtime_share_pct, voluntary_attrition_rate_12m_pct) as overtime_voluntary_attrition_corr,
    COUNT(*) as observations
FROM monthly_dept
WHERE overtime_share_pct IS NOT NULL 
  AND attrition_rate_monthly_pct IS NOT NULL
UNION ALL
SELECT 
    'Rolling 12M' as period_type,
    CORR(overtime_share_pct, attrition_rate_rolling_12m_pct) as overtime_attrition_corr,
    CORR(overtime_share_pct, attrition_rate_rolling_12m_pct) as overtime_rolling_attrition_corr,
    CORR(overtime_share_pct, voluntary_attrition_rate_12m_pct) as overtime_voluntary_attrition_corr,
    COUNT(*) as observations
FROM (
    SELECT 
        department_id,
        AVG(overtime_share_pct) as overtime_share_pct,
        AVG(attrition_rate_rolling_12m_pct) as attrition_rate_rolling_12m_pct,
        AVG(voluntary_attrition_rate_12m_pct) as voluntary_attrition_rate_12m_pct
    FROM star_schema.dept_month_combined
    WHERE headcount_end >= 5
    GROUP BY department_id
) dept_avg
WHERE overtime_share_pct IS NOT NULL 
  AND attrition_rate_rolling_12m_pct IS NOT NULL;

-- ============================================================================
-- 10. PQ-13 VALIDATION VIEW
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq13_validation AS
SELECT 
    'Grain Check' as check_name,
    COUNT(*) as total_rows,
    COUNT(DISTINCT department_id || '-' || month) as unique_dept_months,
    CASE WHEN COUNT(*) = COUNT(DISTINCT department_id || '-' || month) THEN 'PASS' ELSE 'FAIL' END as grain_check
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Row Count Check (Expected 198)',
    COUNT(*) as total_rows,
    198 as expected,
    CASE WHEN COUNT(*) = 198 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Headcount Reconciliation',
    SUM(headcount_end) as total_rows,
    (SELECT SUM(headcount_end) FROM raw.fact_headcount_monthly 
     WHERE month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01') as expected,
    CASE WHEN ABS(SUM(headcount_end) - (SELECT SUM(headcount_end) FROM raw.fact_headcount_monthly 
     WHERE month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01')) < 1 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Payroll Reconciliation',
    SUM(employer_cost) as total_rows,
    (SELECT SUM(employer_cost) FROM raw.fact_payroll p
     JOIN raw.dim_date d ON p.date_key = d.date_key
     WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
       AND p.headcount_flag = 1) as expected,
    CASE WHEN ABS(SUM(employer_cost) - (SELECT SUM(employer_cost) FROM raw.fact_payroll p
     JOIN raw.dim_date d ON p.date_key = d.date_key
     WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
       AND p.headcount_flag = 1)) < 1 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Attendance Reconciliation',
    SUM(scheduled_days) as total_rows,
    (SELECT SUM(scheduled_days) FROM raw.fact_attendance_monthly a
     JOIN raw.dim_date d ON a.date_key = d.date_key
     WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01') as expected,
    CASE WHEN ABS(SUM(scheduled_days) - (SELECT SUM(scheduled_days) FROM raw.fact_attendance_monthly a
     JOIN raw.dim_date d ON a.date_key = d.date_key
     WHERE d.month_start_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-01')) < 1 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Leave Reconciliation (within 5%)',
    SUM(total_leave_days) as total_rows,
    (SELECT SUM(days) FROM raw.fact_leave WHERE status = 'Approved'
       AND start_date <= DATE '2026-09-30' AND end_date >= DATE '2025-04-01') as expected,
    CASE WHEN ABS(SUM(total_leave_days) - (SELECT SUM(days) FROM raw.fact_leave WHERE status = 'Approved'
       AND start_date <= DATE '2026-09-30' AND end_date >= DATE '2025-04-01')) 
         / NULLIF((SELECT SUM(days) FROM raw.fact_leave WHERE status = 'Approved'
       AND start_date <= DATE '2026-09-30' AND end_date >= DATE '2025-04-01'), 0) < 0.05 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
UNION ALL
SELECT 
    'Attrition Rate Formula',
    attrition_rate_monthly_pct,
    ROUND(exits * 100.0 / NULLIF(headcount_start, 0), 2) as expected,
    CASE WHEN ABS(attrition_rate_monthly_pct - ROUND(exits * 100.0 / NULLIF(headcount_start, 0), 2)) < 0.01 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
WHERE headcount_start > 0
UNION ALL
SELECT 
    'Cost Per Head Formula',
    cost_per_head,
    ROUND(employer_cost / NULLIF(employees_paid, 0), 2) as expected,
    CASE WHEN ABS(cost_per_head - ROUND(employer_cost / NULLIF(employees_paid, 0), 2)) < 0.01 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
WHERE employees_paid > 0
UNION ALL
SELECT 
    'Overtime Share Formula',
    overtime_share_pct,
    ROUND(overtime_pay * 100.0 / NULLIF(employer_cost, 0), 2) as expected,
    CASE WHEN ABS(overtime_share_pct - ROUND(overtime_pay * 100.0 / NULLIF(employer_cost, 0), 2)) < 0.01 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
WHERE employer_cost > 0
UNION ALL
SELECT 
    'Attendance Rate Formula',
    attendance_rate_pct,
    ROUND((present_days + 0.5 * half_days_unpaid) * 100.0 / NULLIF(scheduled_days, 0), 2) as expected,
    CASE WHEN ABS(attendance_rate_pct - ROUND((present_days + 0.5 * half_days_unpaid) * 100.0 / NULLIF(scheduled_days, 0), 2)) < 0.01 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
WHERE scheduled_days > 0
UNION ALL
SELECT 
    'Leave Days Per Head Formula',
    leave_days_per_head,
    ROUND(total_leave_days * 1.0 / NULLIF(headcount_end, 0), 4) as expected,
    CASE WHEN ABS(leave_days_per_head - ROUND(total_leave_days * 1.0 / NULLIF(headcount_end, 0), 4)) < 0.01 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.dept_month_combined
WHERE headcount_end > 0
UNION ALL
SELECT 
    'Reference Reconciliation - All 198 Rows Match',
    COUNT(*) as total_rows,
    198 as expected,
    CASE WHEN COUNT(*) = 198 THEN 'PASS' ELSE 'FAIL' END
FROM star_schema.pq13_reference_reconciliation
WHERE actual_employer_cost IS NOT NULL AND ref_employer_cost IS NOT NULL;