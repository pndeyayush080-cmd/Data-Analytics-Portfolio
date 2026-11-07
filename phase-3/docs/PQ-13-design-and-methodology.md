# PQ-13: Cross-Department Impact View - Design & Methodology

## 1. Objective
Build a unified department-month analytical view combining headcount, payroll, attendance, and leave data, validated against the official reference summary.

## 2. Analytical Grain
**Primary grain:** `department_id × month` (one row per department per month)

## 3. Source Tables
| Source | Rows | Grain | Key Columns |
|--------|------|-------|-------------|
| `fact_headcount_monthly` | 891 | dept × month | `date_key`, `department_id`, `headcount_start`, `headcount_end`, `hires`, `exits`, `voluntary_exits` |
| `fact_payroll` | 7,344 | employee × payroll run | `employee_id`, `department_id`, `employer_cost`, `overtime_pay`, `gross_pay`, `overtime_hours_paid` |
| `fact_attendance_monthly` | 7,343 | employee × month | `employee_id`, `department_id`, `scheduled_days`, `present_days`, `half_days_unpaid`, `late_arrivals` |
| `fact_leave` | 3,441 | leave request | `employee_id`, `department_id` (via employee), `days`, `leave_type`, `status` |

## 4. Analytical Grain & Join Strategy

### 4.1 Department-Month Spine
**Corrected:** Restricted to reference period (April 2025 - September 2026) and 11 reference departments:
```sql
dept_month_spine = 
  CROSS JOIN of dim_date (month_start_date BETWEEN '2025-04-01' AND '2026-09-01')
  and dim_department (department_id IN ('D00','D01',...,'D10'))
```
Result: **198 department-month rows** (11 departments × 18 months) matching reference summary exactly.

### 4.2 Independent Aggregation Pattern
Each fact table is independently aggregated to `department_id × month_start_date` grain BEFORE joining:
1. **Headcount**: Direct from `fact_headcount_monthly` (already at correct grain), filtered to reference period
2. **Payroll**: Aggregate `fact_payroll` by `dim_date.month_start_date`, `department_id` (deduplicated, synthetic employees excluded)
3. **Attendance**: Aggregate `fact_attendance_monthly` by `dim_date.month_start_date`, `department_id`
4. **Leave**: Explode `fact_leave` across months spanned within reference period, distribute days by **working-day weights**

### 4.3 Join Strategy
All aggregations LEFT JOIN to the spine on `(month, department_id)`. This ensures:
- No fan-out (each source aggregates to exactly 1 row per dept-month)
- Missing months/sources show as NULL (handled with COALESCE)
- No row multiplication from direct fact-to-fact joins

## 5. Metrics Implemented

| Metric | Formula | Source View |
|--------|---------|-------------|
| **Headcount Start** | `SUM(headcount_start)` | `dept_month_headcount` |
| **Hires** | `SUM(hires)` | `dept_month_headcount` |
| **Exits** | `SUM(exits)` | `dept_month_headcount` |
| **Voluntary Exits** | `SUM(voluntary_exits)` | `dept_month_headcount` |
| **Attrition Rate (Monthly)** | `exits / headcount_start × 100` | `dept_month_headcount` |
| **Attrition Rate (Rolling 12M)** | `SUM(exits, 12m) / AVG(headcount_end, 12m) × 100` | Window function |
| **Voluntary Attrition (12M)** | `SUM(voluntary_exits, 12m) / AVG(headcount_end, 12m) × 100` | Window function |
| **Employer Cost** | `SUM(employer_cost)` | `dept_month_payroll` |
| **Gross Pay** | `SUM(gross_pay)` | `dept_month_payroll` |
| **Overtime Pay** | `SUM(overtime_pay)` | `dept_month_payroll` |
| **Overtime Share %** | `overtime_pay / employer_cost × 100` | `dept_month_payroll` |
| **Cost Per Head** | `employer_cost / employees_paid` | `dept_month_payroll` |
| **Attendance Rate** | `(present_days + 0.5 × half_days_unpaid) / scheduled_days × 100` | `dept_month_attendance` |
| **Late Arrival Rate** | `late_arrivals / present_days × 100` | `dept_month_attendance` |
| **Leave Days Per Head** | `total_leave_days / headcount_end` | Calculated in `dept_month_combined` |

## 6. Leave Distribution Logic (Corrected)

Leave records are exploded across the months they span **within the reference period** using **working-day-weighted allocation**:

1. **Filter valid requests**: Approved status, within reference period, `start_date <= end_date`, exclude LR-002286
2. **SCD Type 2 join**: Leave joined to employee's department at `leave.start_date` (between `valid_from`/`valid_to`)
3. **Monthly explosion**: Each request joined to `dim_date` for month-start dates between clamped start/end dates
4. **Working-day weights**: For each month, count `dim_date.is_working_day = 'Y'` days within the request's date range
5. **Proportional allocation**: `recorded_days × (working_days_in_month / total_working_days_spanned)`
6. **Leave categorization**: Medical, Annual, LOP (Leave Without Pay), Other

**Invalid Request**: LR-002286 (start_date > end_date, 2 days) excluded from allocation, tracked in `pq13_invalid_leave` view.

**Maternity Leave**: 7 requests, 910 days total - fully preserved with < 0.01 day rounding difference.

## 7. Key Design Decisions

### 7.1 SCD Type 2 Employee Dimension
- `dim_employee` is SCD Type 2 with `valid_from`/`valid_to`
- Current version identified by `is_current = 'Y'`
- **Payroll joins**: use `date_key` cast to date and matched against `valid_from`/`valid_to`
- **Leave joins**: use `leave.start_date` matched against `valid_from`/`valid_to`

### 7.2 Payroll Deduplication
- 2 duplicate `(run_id, employee_id)` pairs identified (4 rows total)
- Deduplicated in view using `DISTINCT ON (run_id, employee_id)` keeping first occurrence
- Synthetic/test employees excluded via `employee_id NOT LIKE 'EMP-9%'`

### 7.3 Reference Period Alignment
- All views restricted to April 2025 - September 2026 (18 months)
- 11 departments matching reference: D00-D10
- Produces exactly 198 department-month rows for 1:1 reference reconciliation

## 8. Files Created

| File | Purpose |
|------|---------|
| `scripts/PQ-13-cross_department_views.sql` | 11 analytical views (corrected) |
| `scripts/PQ-13-build.py` | Warehouse loader |
| `scripts/PQ-13-validate.py` | 49 validation checks (updated) |
| `docs/PQ-13-design-and-methodology.md` | This document |
| `reports/PQ-13-department-month-comparison.md` | Department comparison report |
| `reports/PQ-13-reference-reconciliation.md` | Reference reconciliation (updated) |
| `reports/PQ-13-data-quality-and-limitations.md` | Data quality notes |
| `reports/PQ-13-executive-insights.md` | Executive summary (updated) |

## 9. Validation Results (49/49 PASSED)
- Source row counts, key uniqueness, grain integrity
- Source aggregation reconciliation (headcount, payroll, attendance, leave) — reference period only
- **Independent leave allocation validation (10 checks)** — NEW
- Metric formula verification (attrition, cost/head, overtime share, attendance, leave/head) — 0 mismatches
- Join validation (no fan-out)
- M20 DSO (47.61 days), M21 Overdue (₹27.11M)
- Monthly receivables reconciliation (20 months, perfect)
- Known anomalies documented (11)
- M20 DSO validation (47.61 days)
- Missing ledger references (6 distinct invoices)
- Overtime-attrition correlation analysis (Monthly: 0.09, Rolling 12M: 0.34)

## 10. Remediation Summary (PQ-13 Corrections Applied)

| Task | Issue | Correction | Validation |
|------|-------|------------|------------|
| 1. Monthly department spine | 2,886 rows (2020-2026) | Restricted to reference period: Apr 2025-Sep 2026, 11 departments | 198 rows ✅ |
| 2. Monthly leave allocation | Equal distribution inflated totals | Working-day-weighted allocation across months spanned | Source sum matches (7,274) ✅ |
| 3. Leave-per-head calculation | Formula mismatch (117 mismatches) | Calculate in combined view: total_leave_days / headcount_end | 0 mismatches ✅ |
| 4. Combined department-month view | Built on incorrect spine/leave | Rebuilt with corrected spine and leave views | 198 rows, grain intact ✅ |
| 5. Dashboard KPIs & correlations | Based on inflated data | Revalidated with corrected data | All KPIs consistent ✅ |
| 6. Reconcile 198 records | 2,886 vs 198 reference | All 198 department-month records match reference | 198/198 match ✅ |
| 7. Final report & validation | Previous reports outdated | Updated reconciliation, checklist, validation | All 49 checks pass ✅ |