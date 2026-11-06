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
JOIN star_schema.m16_revenue m16 ON r.month = CAST(m16.month AS DATE)

UNION ALL
SELECT 'Net Profit Matches m17_net_profit' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.net_profit - m17.net_profit) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.net_profit - m17.net_profit) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m17_net_profit m17 ON r.month = CAST(m17.month AS DATE)

UNION ALL
SELECT 'Operating Margin Matches m18_operating_margin' as check_name,
    CASE WHEN SUM(CASE WHEN ABS(r.operating_margin_pct - m18.operating_margin_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 1 ELSE 0 END as actual,
    18 as expected,
    CASE WHEN SUM(CASE WHEN ABS(r.operating_margin_pct - m18.operating_margin_pct) < 0.01 THEN 1 ELSE 0 END) = 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM star_schema.pq15_company_scorecard r
JOIN star_schema.m18_operating_margin m18 ON r.month = CAST(m18.month AS DATE)

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