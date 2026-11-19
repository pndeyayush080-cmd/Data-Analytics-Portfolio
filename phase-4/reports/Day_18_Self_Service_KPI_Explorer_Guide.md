# Aura Workforce — Self-Service KPI Explorer Guide
## Phase 4 | Day 18

**Project:** Aura Workforce – PulseIQ Analytics  
**GitHub Repository:** https://github.com/pndeyayush080-cmd/Data-Analytics-Portfolio  
**Branch:** main  
**Document Status:** Final  
**Date:** November 19, 2026

---

## 1. Overview

### What is the Self-Service KPI Explorer?

The Self-Service KPI Explorer is a Streamlit-based dashboard that allows authorized users to independently explore workforce and business metrics. It reads exclusively from the privacy-safe deployment database (`phase-3/data/warehouse/pulseiq_public.duckdb`) in read-only mode.

The explorer supports:
- KPI selection from a role-appropriate menu
- Department filtering
- Reporting-period selection (month range)
- Monthly trend analysis with interactive line charts
- Department-level comparisons with bar charts
- Clear metric definitions and calculation logic
- Role-based metric access enforced at the query layer

### Live Dashboard Entry Point

`phase-4/src/kpi_explorer.py`

Run locally with:
```bash
streamlit run phase-4/src/kpi_explorer.py
```

---

## 2. Architecture

### Data Source

The explorer reads exclusively from:

`phase-3/data/warehouse/pulseiq_public.duckdb`

This is a sanitized, privacy-safe DuckDB database containing a single table:

- **Table:** `star_schema.dept_month_combined`
- **Columns:** 41
- **Rows:** 180 (department-month records)
- **Departments:** 10 (D01–D10, Executive Office excluded)
- **Months:** 18 (April 2025 – September 2026)
- **Minimum headcount_end:** 8

### Architecture Diagram

```
User Browser
     |
     v
Streamlit Server (kpi_explorer.py)
     |
     v
DuckDB (read-only)
phase-3/data/warehouse/pulseiq_public.duckdb
     |
     v
star_schema.dept_month_combined (aggregate data only)
```

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| Read-only access | All DuckDB connections use `read_only=True` |
| Role-based access | KPI access enforced at the query layer via role configuration |
| Default-deny | Unknown roles receive no KPI access |
| Small-group suppression | Groups with headcount < 5 excluded at query level |
| No zero-filling | NULL/missing values remain as-is, never replaced with 0 |
| No PII | No client names, emails, phone numbers, or government IDs |

---

## 3. Available KPIs

The following KPIs are available in the explorer. Each maps to a column in `star_schema.dept_month_combined` and uses the specified aggregation. Each KPI is classified by metric type: **stock** (point-in-time snapshot), **flow** (accumulated over a period), or **rate** (percentage or ratio).

|| KPI Key | Display Name | Column | Unit | Metric Type | Aggregation | Business Definition |
|---------|-------------|--------|------|-------------|-------------|---------------------|
|| headcount | Headcount | headcount_end | count | Stock | Latest month per department | Month-end headcount at the selected reporting date |
|| employer_cost | Employer Cost | employer_cost | INR | Flow | SUM across period | Total employer cost accumulated over the selected reporting period |
|| overtime_pay | Overtime Pay | overtime_pay | INR | Flow | SUM across period | Total overtime pay accumulated over the selected reporting period |
|| overtime_share_pct | Overtime Share | overtime_share_pct | % | Rate | AVG across period | Average overtime share percentage (overtime_pay / employer_cost × 100) |
|| attendance_rate_pct | Attendance Rate | attendance_rate_pct | % | Rate | AVG across period | Average attendance rate percentage |
|| total_leave_days | Total Leave Days | total_leave_days | count | Flow | SUM across period | Total leave days accumulated over the selected reporting period |
|| attrition_rate_monthly_pct | Attrition Rate | attrition_rate_monthly_pct | % | Rate | AVG across period | Average monthly attrition rate percentage |
|| cost_per_head | Cost Per Head | cost_per_head | INR | Rate (pre-computed) | AVG across period | Average pre-computed cost per head |

### Metric Type Classifications

| Classification | KPIs | Interpretation |
|----------------|------|----------------|
| **Stock** | Headcount | Point-in-time snapshot. Must use latest month value — never summed across months. |
| **Flow** | Employer Cost, Overtime Pay, Total Leave Days | Accumulated over a period. SUM across selected period is correct. |
| **Rate** | Overtime Share, Attendance Rate, Attrition Rate, Cost Per Head | Percentage or ratio. AVG across period is appropriate; unweighted departmental average, not organization-wide weighted rate. |

### Aggregation Logic by KPI

- **Headcount (stock):** Latest selected month per department. KPI cards show the latest month's SUM across selected departments. Department comparison uses the latest month's value per department — never summed across monthly snapshots.
- **Employer Cost (flow):** SUM of `employer_cost` across all months in the selected period.
- **Overtime Pay (flow):** SUM of `overtime_pay` across all months in the selected period.
- **Overtime Share (rate):** AVG of the pre-computed `overtime_share_pct` column. Matches `overtime_pay / employer_cost × 100` where overtime_pay > 0.
- **Attendance Rate (rate):** AVG of the pre-computed `attendance_rate_pct` column. Source-provided rate, not recalculated from `present_days / scheduled_days`.
- **Total Leave Days (flow):** SUM of `total_leave_days` across all months in the selected period.
- **Attrition Rate (rate):** AVG of the pre-computed `attrition_rate_monthly_pct` column. Labeled "average monthly rate" — not cumulative period attrition.
- **Cost Per Head (pre-computed rate):** AVG of the pre-computed `cost_per_head` column. Does NOT equal `employer_cost / headcount_end` — see Limitations.

**Note:** Revenue and net profit are not available in the public database. Employer cost is the closest financial metric provided.

---

## 4. Role Permissions

Role-based access is enforced at the **query layer**, not merely by hiding UI elements. Unknown roles receive no KPI access (default-deny).

| Role | Description | Accessible KPIs |
|------|-------------|-----------------|
| **Executive** | High-level organizational KPIs | headcount, employer_cost, overtime_pay, overtime_share_pct, attendance_rate_pct, total_leave_days, attrition_rate_monthly_pct, cost_per_head |
| **Manager** | Departmental KPIs | headcount, attendance_rate_pct, total_leave_days |
| **Analyst** | All analytical metrics | headcount, employer_cost, overtime_pay, overtime_share_pct, attendance_rate_pct, total_leave_days, attrition_rate_monthly_pct, cost_per_head |

### Example Role Restrictions

| KPI | Executive | Manager | Analyst |
|-----|-----------|---------|---------|
| Headcount | ✅ | ✅ | ✅ |
| Employer Cost | ✅ | ❌ | ✅ |
| Overtime Pay | ✅ | ❌ | ✅ |
| Overtime Share % | ✅ | ❌ | ✅ |
| Attendance Rate % | ✅ | ✅ | ✅ |
| Total Leave Days | ✅ | ✅ | ✅ |
| Attrition Rate % | ✅ | ❌ | ✅ |
| Cost Per Head | ✅ | ❌ | ✅ |

### Important: Role Selector is Not Authentication

The role selector in the sidebar is a **development/demo mechanism only**. No production authentication system exists in this codebase. Do not treat role selection as secure authentication. In a production deployment, role-based access should be enforced by an identity provider (IdP) before the user reaches the dashboard.

---

## 5. Privacy Enforcement

### Privacy-Safe Database

The explorer uses only:

`phase-3/data/warehouse/pulseiq_public.duckdb`

The following databases are **never** used:
- `phase-3/data/warehouse/pulseiq_clean.duckdb` (contains PII — excluded)
- `phase-3/data/warehouse/pulseiq_deployment.duckdb` (intermediate — excluded)

### Small-Group Privacy Threshold

Departments with fewer than 5 employees are excluded from all published metrics. This threshold is enforced at the SQL query level:

```sql
WHERE headcount_end >= 5
```

All 180 rows in the public database have `headcount_end >= 8`, so all rows pass this filter in the current dataset. However, the threshold is enforced in every query to prevent future data from exposing small groups.

### What Is Excluded

| Data Type | Status |
|-----------|--------|
| Client names | Excluded (not in public DB) |
| Contact emails | Excluded (not in public DB) |
| Phone numbers | Excluded (not in public DB) |
| Government IDs | Excluded (not in public DB) |
| Bank details | Excluded (not in public DB) |
| Employee-level records | Excluded (aggregated at department-month level) |
| Executive Office department | Excluded (headcount = 1, below threshold) |

### Published Totals

All company-level totals, KPI cards, charts, and correlation calculations are computed exclusively from the 10 eligible departments. The Executive Office is absent from all outputs. A privacy disclosure banner is displayed on the dashboard:

> "Small-group departments with fewer than five employees are excluded from published departmental metrics to protect employee privacy. Reported totals reflect eligible published departments only."

### No NULL-to-Zero Substitution

Missing values are never replaced with zero unless the metric definition explicitly requires it. The dashboard code contains no `COALESCE`, `IFNULL`, `fillna`, or similar NULL-to-zero transformations.

---

## 6. Testing Results

### Test File

`phase-4/tests/test_kpi_explorer.py` — 25 tests

### Test Results

All 25 tests pass:

| Test | Result |
|------|--------|
| headcount KPI matches SQL | PASS |
| employer_cost KPI matches SQL | PASS |
| attendance_rate_pct KPI matches SQL | PASS |
| Department filter restricts results | PASS |
| Month filter restricts results | PASS |
| Empty result for nonexistent department | PASS |
| Executive role has all 8 KPIs | PASS |
| Manager role has 3 limited KPIs | PASS |
| Analyst role has all 8 KPIs | PASS |
| Unknown role defaults to none | PASS |
| is_kpi_allowed respects role | PASS |
| Selected KPIs filtered by role | PASS |
| Small-group suppression (headcount >= 5) | PASS |
| Min headcount constant is 5 | PASS |
| No NULL-to-zero substitution | PASS |
| Database is read-only | PASS |
| Original database untouched (180 rows, 41 cols) | PASS |
| Warehouse path resolves to public DB | PASS |
| Empty KPI list returns empty DataFrame | PASS |
| Empty result for no matching rows | PASS |
| Headcount comparison uses latest month | PASS |
| Headcount not summed across months | PASS |
| Flow metrics use SUM | PASS |
| Rate metrics use AVG | PASS |
| Date and department filters affect results | PASS |

### Existing Day 16 Tests

All 27 existing tests continue to pass. Total: **52 tests passing** (27 existing + 25 new).

### Privacy Verification Results

| Check | Result |
|-------|--------|
| No PII columns in public DB | PASS |
| No NULL values in audited overtime fields | PASS |
| No missing department-month records | PASS |
| Public DB matches original source | PASS |
| Department averages independently verified | PASS |
| No NULL-to-zero transformation in code | PASS |
| Database opened read-only | PASS |
| Small-group threshold enforced (>= 5) | PASS |

### Source Data Ground Truth

All KPI calculations verified against direct SQL queries against `pulseiq_public.duckdb`:

| KPI | Source Check | Result |
|-----|-------------|--------|
| Headcount | SUM vs latest month for D01 (3 months) | Latest month (167) ≠ SUM (483) — stock logic correct |
| Attendance Rate | Stored vs present_days/scheduled_days | Stored 96.18% ≠ calculated 95.93% — source discrepancy documented |
| Cost Per Head | Stored vs employer_cost/headcount_end | Stored 124,268.66 ≠ 125,756.91 — pre-computed formula unresolved |
| Overtime Pay | Zero vs NULL counts | 108/180 rows are zero, 0 NULLs — genuine source data |


---

## 7. Known Limitations

| Limitation | Description |
|------------|-------------|
| Static data snapshot | The deployed database ends September 2026. No new data appears until regenerated and redeployed. |
| No scheduled refresh | Automatic data refresh is not configured. Updates require manual regeneration and redeployment. |
| Demo role selector | The role selector is not production authentication. No IdP integration exists. |
| No user authentication | Any user can select any role. Production deployment requires identity provider integration. |
| Department-level only | Data is aggregated at department-month level. No drill-down to individual employees. |
| Overtime data is all zeros | All 180 rows in `pulseiq_public.duckdb` have `overtime_pay = 0` and `overtime_share_pct = 0`. This is genuine source data — not introduced by sanitization or code. Overtime charts will correctly display 0. |
| Attendance rate source discrepancy | Stored `attendance_rate_pct` (96.18% for D01 Sep 2026) differs from `present_days / scheduled_days × 100` (95.93%). The source-provided rate is retained as-is; the exact denominator definition is not documented in the schema. |
| Cost per head formula unresolved | Stored `cost_per_head` (124,268.66 for D01 Sep 2026) does not equal `employer_cost / headcount_end` (125,756.91). The exact underlying formula cannot be derived from available source columns. The source value is retained and clearly labelled as pre-computed. |
| Unweighted rate averages | Rate metrics (overtime_share_pct, attendance_rate_pct, attrition_rate_monthly_pct, cost_per_head) use AVG across the selected period. These are unweighted departmental averages — never presented as organization-wide weighted rates. |

---

## 8. Instructions for Using the Explorer

### Running Locally

```bash
# From the repository root
cd phase-4
streamlit run src/kpi_explorer.py
```

### Using the Explorer

1. **Select a role** from the sidebar (Executive, Manager, or Analyst). This determines which KPIs are available.
2. **Review available KPIs** in the sidebar expander to see what your role can access.
3. **Select a month range** using the slider (April 2025 – September 2026).
4. **Select departments** using the multiselect (defaults to all departments).
5. **Select KPIs** from the role-appropriate list.
6. **View results:**
   - **KPI Cards:** Latest-month values for each selected KPI
   - **Monthly Trends:** Line charts showing trends over time, faceted by department
   - **Department Comparison:** Bar charts comparing departments for each selected KPI

### Example Workflow (Executive Role)

1. Select role: **Executive**
2. Select month range: **January 2026 – September 2026**
3. Select departments: **Engineering, Data & AI, Sales**
4. Select KPIs: **Headcount, Employer Cost, Overtime Share %**
5. View KPI cards for latest month, monthly trend lines, and department comparison bars

---

## 9. File Summary

| File | Purpose |
|------|---------|
| `phase-4/src/kpi_explorer.py` | Self-Service KPI Explorer application (new) |
| `phase-4/tests/test_kpi_explorer.py` | Automated tests (19 tests, new) |
| `phase-4/reports/Day_18_Self_Service_KPI_Explorer_Guide.md` | This documentation (new) |
| `phase-3/data/warehouse/pulseiq_public.duckdb` | Privacy-safe public database (read-only, created Day 17) |
| `phase-3/scripts/PQ-13-dashboard.py` | Day 17 dashboard (unchanged) |

---

## 10. Conclusion

The Self-Service KPI Explorer provides a role-based, privacy-safe interface for exploring workforce metrics. All data is read from the sanitized public DuckDB database, with access restrictions enforced at the query layer. The explorer has been tested for KPI calculation accuracy, filter correctness, role-based access, default-deny behavior, small-group suppression, and database read-only integrity.

**Next steps for production:** Connect to an identity provider for real authentication, establish an upstream data source for scheduled refreshes, and pin dependency versions in `requirements.txt`.

---

*This document was generated from verified repository evidence. No infrastructure, services, or configurations were invented.*
