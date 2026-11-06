-- THREE WORKED EXAMPLES (PQ-04). Copy the pattern for the other 25 metrics in metric_dictionary.
-- Pattern: one view per metric, named after metric_id, grain = department x month, always carrying the date and the department.

-- M01 Headcount (company, by month)
CREATE OR REPLACE VIEW m01_headcount AS
SELECT month_start_date, department_id, headcount_end AS headcount
FROM raw.fact_headcount_monthly;

-- Monthly attrition % (company level; note we divide exits by average headcount, never by zero)
CREATE OR REPLACE VIEW m_attrition_company AS
SELECT month_start_date,
       SUM(exits) AS exits,
       ROUND(100.0 * SUM(exits) / NULLIF((SUM(headcount_start) + SUM(headcount_end)) / 2.0, 0), 2) AS attrition_pct
FROM raw.fact_headcount_monthly
GROUP BY 1 ORDER BY 1;

-- Payroll cost by department and month. Planted bad rows exist (PQ-03): decide how you will exclude them and say why.
CREATE OR REPLACE VIEW m_payroll_cost AS
SELECT date_key, department_id, COUNT(DISTINCT employee_id) AS employees_paid,
       ROUND(SUM(gross_pay), 2) AS gross_pay, ROUND(SUM(net_pay), 2) AS net_pay, ROUND(SUM(employer_cost), 2) AS employer_cost
FROM raw.fact_payroll
GROUP BY 1, 2;
