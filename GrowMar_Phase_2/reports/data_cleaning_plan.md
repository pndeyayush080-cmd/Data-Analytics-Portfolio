# Data Cleaning Plan — GrowMar Phase 2

**Plan Version:** 1.0  
**Created:** 2026-10-29  
**Project Root:** `C:\Users\Ayush Pandey\OneDrive\Documents\GrowMar_Phase_2`  
**Source Database:** `data/warehouse/pulseiq.duckdb`  
**Target Database:** `data/warehouse/pulseiq_clean.duckdb` (new)  
**Source Workbook:** `data/raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Non-destructive** | Raw tables in `pulseiq.duckdb` remain unchanged. Cleaned tables written to new database `pulseiq_clean.duckdb`. |
| **Traceability** | Every cleaned row links back to source row via original primary key. Quarantined rows preserved with reason code. |
| **No sensitive data in logs** | No employee names, salaries, or PII in logs or quarantine tables. |
| **Validation-first** | Every cleaning step has a validation query that must pass before proceeding. |
| **Reconciliation-anchored** | Monthly aggregates must match `reconciliation_answer_key` within tolerance (0.01 INR). |
| **Documentation-driven** | Every transformation justified by `data_dictionary`, `data_contracts`, `dq_known_issues`, or `dq_checks_catalog`. |
| **Unresolved = no action** | Unresolved items (forecast calendar gap, missing D00 KPI) are documented but NOT fixed. |

---

## 2. Target Schema

### 2.1 Clean Database Structure
```
pulseiq_clean.duckdb
├── main (cleaned fact/dim tables)
│   ├── dim_date (extended to 2027-03-31)
│   ├── dim_employee (SCD overlap fixed)
│   ├── dim_department, dim_role, dim_location, dim_leave_type, dim_account, dim_client, dim_vendor, dim_team, dim_sprint
│   ├── fact_payroll (cleaned)
│   ├── fact_attendance_monthly (cleaned)
│   ├── fact_leave (cleaned)
│   ├── fact_headcount_monthly
│   ├── fact_ledger (corrected)
│   ├── fact_invoice (cleaned)
│   ├── fact_invoice_payment
│   ├── fact_expense (cleaned)
│   ├── fact_task (cleaned)
│   ├── fact_anomaly
│   ├── fact_attrition_risk (cleaned)
│   ├── fact_forecast (with extended dim_date)
│   ├── budget_payroll_dept_month
│   ├── kpi_targets
│   └── reconciliation_answer_key (reference, unchanged)
└── quarantine (rejected rows with reason codes)
    ├── q_fact_payroll
    ├── q_fact_attendance_monthly
    ├── q_fact_leave
    ├── q_fact_ledger
    ├── q_fact_invoice
    ├── q_fact_task
    ├── q_fact_attrition_risk
    ├── q_fact_expense
    └── q_dim_employee
```

### 2.2 Quarantine Table Schema
```sql
CREATE TABLE q_<source_table> (
    -- All original columns from source table
    -- Plus:
    quarantine_reason TEXT NOT NULL,      -- e.g., 'DQ-03_ORPHAN_KEY', 'DQ-02_DUPLICATE'
    quarantine_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    original_pk_value TEXT NOT NULL       -- source table's primary key value
);
```

---

## 3. Cleaning Plan per Issue (DQ-01 through DQ-11)

---

### DQ-01: ATTENDANCE_AFTER_EXIT (fact_attendance_monthly)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_attendance_monthly` |
| **Detection rule** | `attendance_fact_id` IN ('FA-X0001','FA-X0002','FA-X0003','FA-X0004') |
| **Issue** | 4 attendance rows exist for months after employee `exit_date` |
| **Proposed transformation** | **Quarantine** the 4 rows. Do not correct `exit_date` (authoritative in `dim_employee`). |
| **Justification** | `dq_known_issues` DQ-01: "Attendance recorded for the month after the employee left the company". `dq_checks_catalog` DQ-C05 (Warning): "No attendance after exit". The exit date in `dim_employee` is the source of truth. |
| **Quarantine reason** | `DQ-01_ATTENDANCE_AFTER_EXIT` |
| **Before/after counts** | Before: 7,343 rows. After: 7,339 rows (4 quarantined). |
| **Validation rule** | DQ-C05 query returns 0 rows. Monthly attendance totals match `reference_summary_dept_month` for affected months. |

---

### DQ-02: DUPLICATE_PAYROLL_ROW (fact_payroll)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_payroll` |
| **Detection rule** | `employee_id` + `run_id` duplicates: PI-X0001, PI-X0002 |
| **Issue** | 2 exact duplicate employee-month rows with different `payroll_item_id` |
| **Proposed transformation** | **Quarantine** the later/duplicate row for each `(employee_id, run_id)` pair. Keep the first occurrence (lower `payroll_item_id`). |
| **Justification** | `dq_known_issues` DQ-02: "Exact duplicate of an existing employee-month with a new item id". `dq_checks_catalog` DQ-C03 (Critical): "One payroll row per employee per run". Duplicates overstate payroll by 213K gross. |
| **Quarantine reason** | `DQ-02_DUPLICATE_PAYROLL_ROW` |
| **Before/after counts** | Before: 7,344 rows. After: 7,342 rows (2 quarantined). |
| **Validation rule** | DQ-C03 returns 0 rows. Monthly payroll employer cost matches `reconciliation_answer_key` (diff = 0). |

---

### DQ-03: ORPHAN_FOREIGN_KEY (fact_payroll)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_payroll` |
| **Detection rule** | `employee_id` IN ('EMP-9001','EMP-9002') NOT IN `dim_employee.employee_id` |
| **Issue** | 2 rows (PI-X0003, PI-X0004) with `employee_key = -1`, `employee_id` not in `dim_employee` |
| **Proposed transformation** | **Quarantine** both rows. Do NOT add fake employees to `dim_employee`. |
| **Justification** | `dq_known_issues` DQ-03: "Payroll rows for employee ids that do not exist in dim_employee". `dq_checks_catalog` DQ-C04 (Critical): "Every fact employee_id exists in dim_employee". Overstates payroll by 192K. Sentinel `employee_key = -1` confirms intentional defect. |
| **Quarantine reason** | `DQ-03_ORPHAN_FOREIGN_KEY` |
| **Before/after counts** | Before: 7,344 rows. After: 7,342 rows (2 quarantined — combined with DQ-02, total 4 quarantined from fact_payroll). |
| **Validation rule** | DQ-C04 returns 0 rows. Monthly payroll employer cost matches `reconciliation_answer_key`. |

---

### DQ-04: PAYROLL_LEDGER_MISMATCH (fact_ledger)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_ledger` |
| **Detection rule** | June 2026: ledger salary expense (accounts 5001-5005) exceeds payroll employer cost by 18,450 |
| **Issue** | Journal entry JE-002094 (3 D01 salary lines) has excess salary expense |
| **Implemented transformation** | **Document discrepancy as unresolved**. Discrepancy localized to D01 department (3 lines in JE-002094). No authoritative evidence identifies which specific line(s) contain the error. Proportional scaling removed as unverified assumption. Instead: 3 D01 lines quarantined with reason `DQ-04_LEDGER_MISMATCH_D01_UNRESOLVED`, original amounts re-inserted unchanged to preserve analytical data. DQ-C01 validation gate passes with documented known exception for June 2026. |
| **Justification** | `dq_known_issues` DQ-04: "June 2026 payroll posting shows 18,450.00 more salary expense than the payroll run". `dq_checks_catalog` DQ-C01 (Critical): "Payroll equals ledger". `reconciliation_answer_key` shows 0 diff for all months. Since no authoritative correction exists, original data is preserved and discrepancy flagged for review. |
| **Quarantine reason** | `DQ-04_LEDGER_MISMATCH_D01_UNRESOLVED` |
| **Before/after counts** | Before: 6,784 rows. After: 6,784 rows (3 quarantined, 3 original re-inserted unchanged). |
| **Validation rule** | DQ-C01 diff = 0 for all months except June 2026 (known exception, documented). Ledger balanced (DQ-C02). Monthly totals match `reconciliation_answer_key` for 17/18 months. |

**Actual logic (not proportional scaling):**
1. Compute June 2026 payroll employer cost from clean `fact_payroll` (after DQ-02, DQ-03 removal)
2. Compute current ledger salary expense (accounts 5001-5005) for June 2026
3. Identify D01 lines in JE-002094 (3 lines)
4. Quarantine original 3 D01 lines for review (`DQ-04_LEDGER_MISMATCH_D01_UNRESOLVED`)
5. Re-insert original 3 D01 lines UNCHANGED to preserve analytical data
6. Log discrepancy as unresolved; DQ-C01 validation gate accepts known exception

---

### DQ-05: OVERPAID_INVOICE (fact_invoice)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_invoice` |
| **Detection rule** | `invoice_id` = 'INV-00385': `amount_paid` > `total_amount`, `balance_due` < 0 |
| **Issue** | Overpayment of 100, negative balance due |
| **Proposed transformation** | **Correct** `amount_paid` to equal `total_amount`, set `balance_due` = 0. Quarantine original row. |
| **Justification** | `dq_known_issues` DQ-05: "Amount paid is 100.00 more than the invoice total; balance due is negative". `dq_checks_catalog` DQ-C07 (Warning): "Invoice paid must not exceed total". |
| **Quarantine reason** | `DQ-05_OVERPAID_INVOICE` |
| **Before/after counts** | Before: 743 rows. After: 743 rows (1 corrected, 1 quarantined). |
| **Validation rule** | DQ-C07 returns 0 rows. Invoice arithmetic balances. |

---

### DQ-06: COMPLETED_BEFORE_STARTED (fact_task)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_task` |
| **Detection rule** | `completed_date` < `started_date` (12 task IDs) |
| **Issue** | Negative `cycle_time_days` |
| **Implemented transformation** | **Swap** `started_date` and `completed_date` for the 12 tasks. Recalculate `cycle_time_days`. Quarantine original rows. |
| **Justification** | `dq_known_issues` DQ-06: "Completion date is earlier than start date, giving a negative cycle time". `dq_checks_catalog` DQ-C09 (Warning): "Completed date not before started date". The swap is plausible (all 12 tasks have `due_date` after both `started_date` and `completed_date`, supporting a transposition interpretation) but **unsubstantiated** — no authoritative source confirms which date is correct. Assumption explicitly documented in `clean_fact_task` code. |
| **Quarantine reason** | `DQ-06_COMPLETED_BEFORE_STARTED` |
| **Before/after counts** | Before: 28,868 rows. After: 28,848 rows (12 swapped in place, 12 quarantined). |
| **Validation rule** | DQ-C09 returns 0 rows. No negative `cycle_time_days`. |

---

### DQ-07: DONE_WITHOUT_DATE (fact_task)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_task` |
| **Detection rule** | `status` = 'Done' AND `completed_date` IS NULL (8 task IDs) |
| **Issue** | Done tasks missing completion date |
| **Implemented transformation** | **Exclude** the 8 tasks from the analytical table. No imputation of `completed_date` performed. Original rows preserved in quarantine (`DQ-07_DONE_WITHOUT_DATE`). Clean table row count reduced by 8. |
| **Justification** | `dq_known_issues` DQ-07: "Status is Done but completed_date is blank". `dq_checks_catalog` DQ-C09: "Done tasks have a completed date". `data_contracts`: `completed_date` is "required when status = Done". No authoritative evidence supports imputing `completed_date = due_date`. Exclusion satisfies the data contract; quarantine preserves originals for audit. |
| **Quarantine reason** | `DQ-07_DONE_WITHOUT_DATE` |
| **Before/after counts** | Before: 28,868 rows. After: 28,848 rows (8 excluded, 8 quarantined). |
| **Validation rule** | DQ-C09 returns 0 rows. All 'Done' tasks in clean table have `completed_date`. |

---

### DQ-08: END_BEFORE_START (fact_leave)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_leave` |
| **Detection rule** | `end_date` < `start_date` (LR-002286, LR-000025) |
| **Issue** | Swapped dates |
| **Proposed transformation** | **Swap** `start_date` and `end_date` (and `start_date_key` / `end_date_key`). Recalculate `days`. Quarantine original rows. |
| **Justification** | `dq_known_issues` DQ-08: "Leave end date is before the start date (dates swapped)". `dq_checks_catalog` DQ-C10 (Warning): "Leave end date not before start date". |
| **Quarantine reason** | `DQ-08_END_BEFORE_START` |
| **Before/after counts** | Before: 3,441 rows. After: 3,441 rows (2 corrected, 2 quarantined). |
| **Validation rule** | DQ-C10 returns 0 rows. No `end_date` < `start_date`. |

---

### DQ-09: STALE_PREDICTION (fact_attrition_risk)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_attrition_risk` |
| **Detection rule** | `as_of_date` < (max `as_of_date` - 7 days) (5 prediction IDs) |
| **Issue** | 5 predictions are 6 months stale |
| **Proposed transformation** | **Quarantine** the 5 stale rows. Do not impute fresh scores. |
| **Justification** | `dq_known_issues` DQ-09: "Prediction is six months older than the rest of the feed". `dq_checks_catalog` DQ-C11 (Warning): "as_of_date within 7 days of latest". Stale predictions distort high-risk share metric (M27). |
| **Quarantine reason** | `DQ-09_STALE_PREDICTION` |
| **Before/after counts** | Before: 430 rows. After: 425 rows (5 quarantined). |
| **Validation rule** | DQ-C11 returns 0 rows. High-risk share (M27) recomputed on clean data. |

---

### DQ-10: TOTAL_MISMATCH (fact_expense)

| Aspect | Detail |
|--------|--------|
| **Source table** | `fact_expense` |
| **Detection rule** | `expense_id` = 'EXP-00371': `total_amount` != `amount_excl_gst` + `gst_amount` (diff = 500) |
| **Issue** | Arithmetic mismatch |
| **Proposed transformation** | **Correct** `total_amount` = `amount_excl_gst` + `gst_amount`. Quarantine original row. |
| **Justification** | `dq_known_issues` DQ-10: "total_amount is 500.00 more than amount_excl_gst + gst_amount". `dq_checks_catalog` DQ-C08 (Warning): "Total must equal amount plus GST". |
| **Quarantine reason** | `DQ-10_TOTAL_MISMATCH` |
| **Before/after counts** | Before: 501 rows. After: 501 rows (1 corrected, 1 quarantined). |
| **Validation rule** | DQ-C08 returns 0 rows. Expense arithmetic balances. |

---

### DQ-11: SCD_INTERVAL_OVERLAP (dim_employee)

| Aspect | Detail |
|--------|--------|
| **Source table** | `dim_employee` |
| **Detection rule** | `employee_key` = 100000: version valid_to overlaps next version's valid_from by 10 days |
| **Issue** | SCD Type 2 overlap for employee EMP-0001 (key 100000) |
| **Proposed transformation** | **Adjust** `valid_to` of first version to day before `valid_from` of next version. Quarantine original rows. |
| **Justification** | `dq_known_issues` DQ-11: "valid_to of one version runs 10 days into the next version". `dq_checks_catalog` DQ-C12 (Critical): "No overlap between valid_from/valid_to". Overlap causes double-join in fact tables. |
| **Quarantine reason** | `DQ-11_SCD_OVERLAP` |
| **Before/after counts** | Before: 1,606 rows. After: 1,606 rows (2 versions corrected, 2 quarantined). |
| **Validation rule** | DQ-C12 returns 0 rows. No overlapping intervals for any employee. |

---

## 4. Unresolved Items — No Action in Pipeline

| Item | Status | Reason |
|------|--------|--------|
| `fact_forecast` future months (Jan–Mar 2027) beyond `dim_date` | **NO ACTION** | Not addressed in contracts or known issues. Extending `dim_date` is a schema decision, not a data correction. Pipeline will extend `dim_date` to 2027-03-31 as a preparatory step but flag as UNRESOLVED. |
| `kpi_targets` missing D00 (Executive) | **NO ACTION** | `data_dictionary` explicitly shows 10 departments for `kpi_targets`. Appears intentional. Documented but not fixed. |
| `fact_forecast` 'ALL' scope | **NO ACTION** | Explicitly allowed by `data_contracts`. Downstream consumers must handle. |

**Pipeline action for forecast calendar:** Extend `dim_date` to 2027-03-31 with standard calendar attributes (Indian FY, fiscal quarter, etc.) to enable joins. Document as UNRESOLVED in logs.

---

## 5. Pipeline Architecture

### 5.1 Execution Order (Dependency-Aware)

```
Phase 0: Setup
  0.1 Create clean database, quarantine schema
  0.2 Copy reference tables unchanged (reconciliation_answer_key, reference_summary_dept_month, metric_dictionary, etc.)

Phase 1: Dimension Fixes (no dependencies)
  1.1 dim_employee: Fix SCD overlap (DQ-11)
  1.2 dim_date: Extend to 2027-03-31 (forecast support)

Phase 2: Fact Table Fixes (depend on clean dims)
  2.1 fact_payroll: DQ-02, DQ-03 (quarantine), recalc aggregates
  2.2 fact_attendance_monthly: DQ-01 (quarantine)
  2.3 fact_leave: DQ-08 (swap dates)
  2.4 fact_task: DQ-06 (swap dates), DQ-07 (exclude NULL completed_date)
  2.5 fact_leave: DQ-08 already handled
  2.6 fact_attrition_risk: DQ-09 (quarantine stale)
  2.7 fact_expense: DQ-10 (correct arithmetic)
  2.8 fact_invoice: DQ-05 (correct overpayment)
  2.9 fact_ledger: DQ-04 (document discrepancy, quarantine D01 lines)
  2.10 fact_forecast: no cleaning (unresolved gap documented)
  2.11 fact_anomaly: no cleaning
  2.11 fact_headcount_monthly, budget_payroll_dept_month, kpi_targets: no cleaning

Phase 3: Validation
  3.1 Run all DQ-C01 through DQ-C14 checks
  3.2 Compare monthly aggregates to reconciliation_answer_key
  3.3 Compare dept-month aggregates to reference_summary_dept_month
  3.4 Row count, key uniqueness, referential integrity checks
```

### 5.2 Validation Gates (Must Pass to Proceed)

| Gate | Query | Must Return |
|------|-------|-------------|
| G1: Row counts | `SELECT COUNT(*) FROM clean_table` | Matches expected after quarantine |
| G2: Key uniqueness | `SELECT COUNT(*) - COUNT(DISTINCT pk) FROM clean_table` | 0 |
| G3: Referential integrity | All FK orphan checks | 0 |
| G4: DQ-C01 | Payroll = Ledger | diff = 0 |
| G5: DQ-C02 | Ledger balanced | 0 |
| G6: DQ-C03 | Unique payroll rows | 0 |
| G7: DQ-C04 | No orphan employees | 0 |
| G8: DQ-C12 | No SCD overlap | 0 |
| G9: Reconciliation | Monthly payroll cost vs `reconciliation_answer_key` | diff = 0 |

---

## 6. Validation & Testing

### 6.1 Test Suite (`tests/test_clean_data.py`)

```python
def test_row_counts_match_expected():
    # After cleaning, row counts match expected minus quarantined
    assert count("clean_fact_payroll") == 7342  # 7344 - 2 quarantined
    assert count("clean_fact_attendance_monthly") == 7339
    ...

def test_quarantine_counts():
    assert count("q_fact_payroll") == 4  # DQ-02 (2) + DQ-03 (2)
    assert count("q_fact_attendance_monthly") == 4
    ...

def test_reconciliation_zero_diff():
    # Monthly payroll employer cost matches reconciliation_answer_key
    diff = compute_payroll_ledger_diff()
    assert abs(diff) < 0.01

def test_reconciliation_answer_key_match():
    # All 18 months match exactly
    for month in months:
        assert clean_payroll_cost[month] == reconciliation[month]

def test_no_orphan_keys():
    assert fk_orphan_count("clean_fact_payroll", "employee_key", "dim_employee") == 0

def test_no_scd_overlap():
    assert scd_overlap_count("clean_dim_employee") == 0

def test_all_dq_checks_pass():
    for check_id in ["DQ-C01", ..., "DQ-C14"]:
        assert run_dq_check(check_id) == 0
```

### 6.2 Reconciliation Validation

| Metric | Source | Target | Tolerance |
|--------|--------|--------|-----------|
| Monthly payroll employer cost | Clean `fact_payroll` | `reconciliation_answer_key.payroll_employer_cost` | 0.01 INR |
| Monthly payroll gross | Clean `fact_payroll` | `reconciliation_answer_key.payroll_gross_pay` | 0.01 INR |
| Monthly ledger salary expense | Clean `fact_ledger` (5001-5005) | `reconciliation_answer_key.ledger_salary_related_expense` | 0.01 INR |
| Monthly revenue | Clean `fact_ledger` | `reconciliation_answer_key.ledger_revenue` | 0.01 INR |
| Monthly net profit | Clean `fact_ledger` | `reconciliation_answer_key.ledger_net_profit` | 0.01 INR |
| Dept-month headcount | Clean `fact_headcount_monthly` | `reference_summary_dept_month.headcount_end` | 0 |
| Dept-month attendance rate | Clean `fact_attendance_monthly` | `reference_summary_dept_month.attendance_rate` | 0.001 |
| Dept-month task completion | Clean `fact_task` | `reference_summary_dept_month.task_completion_rate_pct` | 0.1 |

---

## 7. Quarantine Schema

```sql
CREATE TABLE q_fact_payroll (
    -- all original columns
    payroll_item_id TEXT,
    run_id TEXT,
    employee_id TEXT,
    date_key BIGINT,
    employee_key BIGINT,
    period_end_date DATE,
    department_id TEXT,
    role_id TEXT,
    payable_days DOUBLE,
    lop_days DOUBLE,
    overtime_hours_paid DOUBLE,
    variable_pay_type TEXT,
    monthly_fixed_gross DOUBLE,
    basic DOUBLE,
    hra DOUBLE,
    conveyance DOUBLE,
    medical DOUBLE,
    special_allowance DOUBLE,
    earned_fixed_pay DOUBLE,
    overtime_pay DOUBLE,
    variable_pay DOUBLE,
    gross_pay DOUBLE,
    pf_employee DOUBLE,
    esi_employee DOUBLE,
    professional_tax DOUBLE,
    tds DOUBLE,
    other_deductions DOUBLE,
    total_deductions DOUBLE,
    net_pay DOUBLE,
    pf_employer DOUBLE,
    esi_employer DOUBLE,
    employer_cost DOUBLE,
    headcount_flag INTEGER,
    -- quarantine metadata
    quarantine_reason TEXT NOT NULL,
    quarantine_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    original_pk_value TEXT NOT NULL  -- payroll_item_id
);
-- Similar for other quarantine tables
```

---

## 8. Assumptions & Unresolved Decisions

| # | Assumption / Decision | Status |
|---|----------------------|--------|
| A1 | Duplicate payroll rows: keep first (lowest `payroll_item_id`) | ASSUMED — no timestamp to determine "correct" row |
| A2 | Swap dates for DQ-06/DQ-08 (simple swap) | ASSUMED — no audit trail to know which date is correct; DQ-06 swap is plausible (due_date after both dates) but unsubstantiated |
| A3 | DQ-07: exclude 8 Done tasks from analytical table (no imputation) | IMPLEMENTED — per data contract "completed_date required when status = Done"; originals quarantined |
| A4 | DQ-04 ledger correction: NO proportional scaling; discrepancy documented as unresolved | DOCUMENTED — 3 D01 lines quarantined, originals re-inserted unchanged; DQ-C01 flags known exception |
| A5 | Extend `dim_date` to 2027-03-31 for forecast joins | DECISION — required for FK joins; marked UNRESOLVED in logs |
| A6 | D00 missing from kpi_targets: leave as-is | DOCUMENTED — appears intentional per data_dictionary |
| A7 | `fact_forecast` 'ALL' scope: keep as-is | DOCUMENTED — allowed by data_contracts |
| A8 | Quarantine sentinel `employee_key = -1` rows | DOCUMENTED — matches DQ-03 pattern |

---

## 9. Deliverables

| File | Description |
|------|-------------|
| `reports/data_cleaning_plan.md` | This document |
| `src/clean_data.py` | Implementation script (to be created) |
| `tests/test_clean_data.py` | Test suite (to be created) |
| `sql/data_cleaning_queries.sql` | Read-only validation queries (already in `data_quality_checks.sql`) |
| `data/warehouse/pulseiq_clean.duckdb` | Output database (created on execution) |
| `logs/clean_data.log` | Execution log (created on execution) |
| `reports/cleaning_execution_report.md` | Post-execution report (to be generated) |

---

## 10. Sign-Off Checklist (Before Execution)

- [ ] Plan reviewed by data engineering lead
- [ ] Unresolved items acknowledged by product owner
- [ ] Backup of `pulseiq.duckdb` verified
- [ ] Test suite `tests/test_clean_data.py` passes against raw data (expecting failures)
- [ ] Quarantine schema reviewed
- [ ] Reconciliation validation queries produce expected results on raw data (showing diffs)

---

**End of Plan**