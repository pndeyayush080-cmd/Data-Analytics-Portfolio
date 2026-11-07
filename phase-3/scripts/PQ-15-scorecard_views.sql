-- ============================================================================
-- PQ-15: Executive Company-Health Scorecard
-- Company-level metric view aggregating 8 founder-level KPIs
-- ============================================================================

-- ============================================================================
-- 1. COMPANY-LEVEL SCORECARD VIEW
-- Single-row-per-month view with all 8 KPIs aggregated at company level
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq15_company_scorecard AS
WITH
-- Revenue from m16_revenue (already company-level)
-- month column is VARCHAR in format 'YYYY-MM', append '-01' for DATE cast
revenue_cte AS (
    SELECT 
        (month || '-01')::DATE as month,
        revenue
    FROM star_schema.m16_revenue
    WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
),

-- Net Profit from m17_net_profit (already company-level)
net_profit_cte AS (
    SELECT 
        (month || '-01')::DATE as month,
        net_profit
    FROM star_schema.m17_net_profit
    WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
),

-- Operating Margin from m18_operating_margin (already company-level)
operating_margin_cte AS (
    SELECT 
        (month || '-01')::DATE as month,
        operating_margin_pct
    FROM star_schema.m18_operating_margin
    WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
),

-- DSO from m20_dso (point-in-time, latest only)
dso_cte AS (
    SELECT 
        DATE_TRUNC('month', report_date)::DATE as month,
        dso_days
    FROM star_schema.m20_dso
    WHERE report_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-30'
),

-- Company-level Headcount (sum of dept headcount_end)
headcount_cte AS (
    SELECT 
        month,
        SUM(headcount_end) as total_headcount
    FROM star_schema.dept_month_headcount
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
),

-- Company-level Rolling 12M Attrition
-- Correct formula: SUM(exits over 12M) / AVG(total_headcount over 12M) * 100
attrition_cte AS (
    SELECT 
        h.month,
        -- Rolling 12M: sum exits over 12 months / avg total_headcount over 12 months
        (
            SELECT SUM(m.total_exits) * 100.0 / NULLIF(AVG(m.total_headcount), 0)
            FROM (
                SELECT 
                    h2.month,
                    SUM(h2.exits) as total_exits,
                    SUM(h2.headcount_end) as total_headcount
                FROM star_schema.dept_month_headcount h2
                WHERE h2.month BETWEEN h.month - INTERVAL '11 months' AND h.month
                GROUP BY h2.month
            ) m
        ) as attrition_rolling_12m_pct
    FROM star_schema.dept_month_headcount h
    WHERE h.month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY h.month
),

-- Company-level Attendance Rate
-- Aggregate numerator and denominator per the metric definition
attendance_cte AS (
    SELECT 
        month,
        SUM(present_days + 0.5 * half_days_unpaid) * 100.0 / NULLIF(SUM(scheduled_days), 0) as attendance_rate_pct
    FROM star_schema.dept_month_attendance
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
),

-- Company-level Overtime Share
-- SUM(overtime_pay) / SUM(employer_cost) * 100
overtime_cte AS (
    SELECT 
        month,
        SUM(overtime_pay) * 100.0 / NULLIF(SUM(employer_cost), 0) as overtime_share_pct
    FROM star_schema.dept_month_payroll
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
),

-- Total Headcount (sum of headcount_end)
headcount_total_cte AS (
    SELECT 
        month,
        SUM(headcount_end) as total_headcount
    FROM star_schema.dept_month_headcount
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
),

-- DSO (only one row, but join on month)
dso_monthly_cte AS (
    SELECT 
        DATE_TRUNC('month', report_date)::DATE as month,
        dso_days
    FROM star_schema.m20_dso
    WHERE report_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-30'
)

-- Final combined scorecard
SELECT 
    COALESCE(r.month, np.month, om.month, d.month, att.month, o.month, ht.month) as month,
    -- 1. Revenue
    r.revenue,
    -- 2. Net Profit
    np.net_profit,
    -- 3. Operating Margin
    om.operating_margin_pct,
    -- 4. DSO (days)
    d.dso_days,
    -- 5. Total Headcount
    ht.total_headcount,
    -- 6. Rolling 12M Attrition
    a.attrition_rolling_12m_pct,
    -- 7. Attendance Rate
    att.attendance_rate_pct,
    -- 8. Overtime Share
    o.overtime_share_pct
FROM revenue_cte r
FULL JOIN net_profit_cte np ON r.month = np.month
FULL JOIN operating_margin_cte om ON r.month = om.month
FULL JOIN dso_monthly_cte d ON r.month = d.month
FULL JOIN attrition_cte a ON r.month = a.month
FULL JOIN attendance_cte att ON r.month = att.month
FULL JOIN overtime_cte o ON r.month = o.month
FULL JOIN headcount_total_cte ht ON r.month = ht.month
ORDER BY r.month;

-- ============================================================================
-- 2. KPI TARGETS VIEW (Company-level targets - separate from dept-level)
-- ============================================================================
-- This view will be populated when company-level targets are approved.
-- Currently returns 8 rows with "Not Set" status.
CREATE OR REPLACE VIEW star_schema.pq15_kpi_targets_company AS
SELECT 
    'Revenue' as kpi_name,
    NULL as target_value,
    NULL as threshold_warning,
    NULL as threshold_critical,
    'Not Set' as target_status
UNION ALL
SELECT 'Net Profit', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'Operating Margin', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'DSO', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'Total Headcount', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'Rolling 12M Attrition', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'Attendance Rate', NULL, NULL, NULL, 'Not Set'
UNION ALL
SELECT 'Overtime Share', NULL, NULL, NULL, 'Not Set';

-- ============================================================================
-- 3. VALIDATION VIEW
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq15_validation AS
SELECT 'Scorecard Row Count' as check_name, 
    COUNT(*) as actual, 18 as expected,
    CASE WHEN COUNT(*) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard

UNION ALL
SELECT 'Revenue Matches m16_revenue' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.revenue - m16.revenue) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.revenue - m16.revenue) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m16_revenue m16 ON r.month = (m16.month || '-01')::DATE

UNION ALL
SELECT 'Net Profit Matches m17_net_profit' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.net_profit - m17.net_profit) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.net_profit - m17.net_profit) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m17_net_profit m17 ON r.month = (m17.month || '-01')::DATE

UNION ALL
SELECT 'Operating Margin Matches m18_operating_margin' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.operating_margin_pct - m18.operating_margin_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.operating_margin_pct - m18.operating_margin_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m18_operating_margin m18 ON r.month = (m18.month || '-01')::DATE

UNION ALL
SELECT 'Total Headcount Matches dept_month_headcount' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.total_headcount - h.total_headcount) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.total_headcount - h.total_headcount) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN (
    SELECT month, SUM(headcount_end) as total_headcount
    FROM star_schema.dept_month_headcount
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) h ON r.month = h.month

UNION ALL
SELECT 'Attendance Rate Matches dept_month_attendance' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.attendance_rate_pct - a.attendance_rate_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.attendance_rate_pct - a.attendance_rate_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN (
    SELECT month, SUM(present_days + 0.5 * half_days_unpaid) * 100.0 / NULLIF(SUM(scheduled_days), 0) as attendance_rate_pct
    FROM star_schema.dept_month_attendance
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) a ON r.month = a.month

UNION ALL
SELECT 'Overtime Share Matches dept_month_payroll' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.overtime_share_pct - o.overtime_share_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.overtime_share_pct - o.overtime_share_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN (
    SELECT month, SUM(overtime_pay) * 100.0 / NULLIF(SUM(employer_cost), 0) as overtime_share_pct
    FROM star_schema.dept_month_payroll
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) o ON r.month = o.month

UNION ALL
SELECT 'Rolling 12M Attrition Calculation Correct' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.attrition_rolling_12m_pct - a.attrition_rolling_12m_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.attrition_rolling_12m_pct - a.attrition_rolling_12m_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN (
    SELECT 
        h.month,
        (
            SELECT SUM(h2.exits) * 100.0 / NULLIF(AVG(h2.headcount_end), 0)
            FROM star_schema.dept_month_headcount h2
            WHERE h2.month BETWEEN h.month - INTERVAL '11 months' AND h.month
        ) as attrition_rolling_12m_pct
    FROM star_schema.dept_month_headcount h
    WHERE h.month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY h.month
) a ON r.month = a.month

UNION ALL
SELECT 'DSO Matches m20_dso' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.dso_days - d.dso_days) < 0.01 THEN 1 ELSE 0 END) = 1 THEN 1 ELSE 0 END as actual,
    1 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.dso_days - d.dso_days) < 0.01 THEN 1 ELSE 0 END) = 1 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m20_dso d ON r.month = DATE_TRUNC('month', d.report_date)::DATE

UNION ALL
SELECT 'Overtime Share Matches dept_month_payroll' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.overtime_share_pct - o.overtime_share_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.overtime_share_pct - o.overtime_share_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN (
    SELECT month, SUM(overtime_pay) * 100.0 / NULLIF(SUM(employer_cost), 0) as overtime_share_pct
    FROM star_schema.dept_month_payroll
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) o ON r.month = o.month

UNION ALL
SELECT 'Target Status Not Set For All KPIs' as check_name,
    CASE WHEN SUM(CASE WHEN t.target_status = 'Not Set' THEN 1 ELSE 0 END) = 8 THEN 1 ELSE 0 END as actual,
    8 as expected,
    CASE WHEN SUM(CASE WHEN t.target_status = 'Not Set' THEN 1 ELSE 0 END) = 8 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_kpi_targets_company t

UNION ALL
SELECT 'No Invented Targets' as check_name,
    CASE WHEN SUM(CASE WHEN t.target_value IS NULL AND t.target_status = 'Not Set' THEN 1 ELSE 0 END) = 8 THEN 1 ELSE 0 END as actual,
    8 as expected,
    CASE WHEN SUM(CASE WHEN t.target_value IS NULL AND t.target_status = 'Not Set' THEN 1 ELSE 0 END) = 8 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_kpi_targets_company t;

-- ============================================================================
-- 4. COMPANY TARGETS TABLE (Empty - for future use when targets are approved)
-- ============================================================================
-- This table will be populated when company-level targets are approved.
-- Currently empty - all KPIs have "Not Set" status.
CREATE TABLE IF NOT EXISTS star_schema.pq15_company_kpi_targets (
    kpi_name VARCHAR NOT NULL,
    target_value DOUBLE,
    threshold_warning DOUBLE,
    threshold_critical DOUBLE,
    target_status VARCHAR DEFAULT 'Not Set',
    approved_date DATE,
    approved_by VARCHAR,
    PRIMARY KEY (kpi_name)
);

-- ============================================================================
-- 5. TREND VIEW (12-month history for sparklines)
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.pq15_kpi_trends AS
SELECT 
    'Revenue' as kpi_name,
    (month || '-01')::DATE as month,
    revenue as value,
    'INR' as unit,
    'Higher is better' as direction
FROM star_schema.m16_revenue
WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'

UNION ALL
SELECT 
    'Net Profit' as kpi_name,
    (month || '-01')::DATE as month,
    net_profit as value,
    'INR' as unit,
    'Higher is better' as direction
FROM star_schema.m17_net_profit
WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'

UNION ALL
SELECT 
    'Operating Margin' as kpi_name,
    (month || '-01')::DATE as month,
    operating_margin_pct as value,
    '%' as unit,
    'Higher is better' as direction
FROM star_schema.m18_operating_margin
WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'

UNION ALL
SELECT 
    'DSO' as kpi_name,
    DATE_TRUNC('month', report_date)::DATE as month,
    dso_days as value,
    'days' as unit,
    'Lower is better' as direction
FROM star_schema.m20_dso
WHERE report_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-30'

UNION ALL
SELECT 
    'Total Headcount' as kpi_name,
    month,
    total_headcount as value,
    'count' as unit,
    'Context dependent' as direction
FROM (
    SELECT month, SUM(headcount_end) as total_headcount
    FROM star_schema.dept_month_headcount
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) h

UNION ALL
SELECT 
    'Rolling 12M Attrition' as kpi_name,
    month,
    attrition_rolling_12m_pct as value,
    '%' as unit,
    'Lower is better' as direction
FROM (
    SELECT 
        h.month,
        (
            SELECT SUM(h2.exits) * 100.0 / NULLIF(AVG(h2.headcount_end), 0)
            FROM star_schema.dept_month_headcount h2
            WHERE h2.month BETWEEN h.month - INTERVAL '11 months' AND h.month
        ) as attrition_rolling_12m_pct
    FROM star_schema.dept_month_headcount h
    WHERE h.month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY h.month
) a

UNION ALL
SELECT 
    'Attendance Rate' as kpi_name,
    month,
    attendance_rate_pct as value,
    '%' as unit,
    'Higher is better' as direction
FROM (
    SELECT 
        month,
        SUM(present_days + 0.5 * half_days_unpaid) * 100.0 / NULLIF(SUM(scheduled_days), 0) as attendance_rate_pct
    FROM star_schema.dept_month_attendance
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) att

UNION ALL
SELECT 
    'Overtime Share' as kpi_name,
    month,
    overtime_share_pct as value,
    '%' as unit,
    'Lower is better' as direction
FROM (
    SELECT 
        month,
        SUM(overtime_pay) * 100.0 / NULLIF(SUM(employer_cost), 0) as overtime_share_pct
    FROM star_schema.dept_month_payroll
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
) o

ORDER BY kpi_name, month;