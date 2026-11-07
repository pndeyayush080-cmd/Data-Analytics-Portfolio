# GrowMar Phase 2: Workforce Analytics Project

## Project Overview

This project implements a complete data engineering pipeline for the **GrowMar Phase 2 Workforce Analytics** dataset. It extracts data from a provided Excel workbook, loads it into a DuckDB star-schema warehouse, applies 11 documented data-quality (DQ) corrections with full traceability, and produces a clean analytical database with quarantine tables for auditability.

**Key objectives:**
- Non-destructive cleaning: source data remains unchanged
- Full traceability: every corrected row preserved in quarantine with reason codes
- Validation-first: all transformations pass automated quality gates
- Reconciliation-anchored: monthly aggregates match the workbook's `reconciliation_answer_key`

---

## Dataset

**Source:** `data/raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`  
**Workbook sheets (29):** README, data_dictionary, metric_dictionary, data_contracts, dq_checks_catalog, dq_known_issues, reconciliation_answer_key, reference_summary_dept_month, plus 21 dimension/fact tables.

**Star schema:**
- **Dimensions (11):** dim_date, dim_employee, dim_department, dim_role, dim_location, dim_leave_type, dim_account, dim_client, dim_vendor, dim_team, dim_sprint
- **Facts (12):** fact_payroll, fact_attendance_monthly, fact_leave, fact_headcount_monthly, fact_ledger, fact_invoice, fact_invoice_payment, fact_expense, fact_task, fact_anomaly, fact_attrition_risk, fact_forecast
- **Targets (2):** budget_payroll_dept_month, kpi_targets

---

## Technology Stack

| Component | Version |
|-----------|---------|
| Python | 3.11+ |
| DuckDB | 1.1+ |
| openpyxl | 3.1+ |
| pytest | 9.2+ |

---

## Folder Structure

```
GrowMar_Phase_2/
├── data/
│   ├── raw/                           # Source workbook (immutable)
│   └── warehouse/
│       ├── pulseiq.duckdb             # Source database (immutable)
│       └── pulseiq_clean.duckdb       # Clean database (pipeline output)
├── src/
│   ├── clean_data.py                  # Main cleaning pipeline
│   ├── extract_data.py                # Workbook → DuckDB extraction
│   ├── validate_warehouse.py          # Validation runner
│   └── inspect_workbook.py            # Workbook inspection utility
├── tests/
│   └── test_clean_data.py             # 56 automated tests
├── sql/
│   └── data_quality_checks.sql        # Read-only DQ detection queries
├── reports/
│   ├── data_cleaning_plan.md          # Cleaning plan (this doc)
│   ├── data_quality_investigation.md  # DQ investigation notes
│   └── warehouse_validation_report.md # Source DB validation
├── logs/
│   └── clean_data.log                 # Pipeline execution log
├── backups_20261031/                  # Pre-modification backups
├── REMEDIATION_REPORT.md              # Final remediation summary
├── FINAL_AUDIT_REPORT.md              # Post-remediation audit
└── requirements.txt                   # Python dependencies
```

---

## Setup & Execution

### Prerequisites
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 1. Extract workbook to source database (run once)
```bash
python src/extract_data.py
```
Creates `data/warehouse/pulseiq.duckdb` from the Excel workbook.

### 2. Run cleaning pipeline
```bash
python src/clean_data.py
```
- Reads from `pulseiq.duckdb`
- Builds candidate in temp file
- Runs all validation gates
- Atomically publishes to `pulseiq_clean.duckdb`
- Logs to `logs/clean_data.log`

### 3. Run tests
```bash
python -m pytest tests/test_clean_data.py -v
```
**Expected:** 56 passed

### 4. Validate clean database
```bash
python src/validate_warehouse.py
```

---

## Pipeline Outputs

| Artifact | Description |
|----------|-------------|
| `data/warehouse/pulseiq_clean.duckdb` | Clean star-schema database (25 main tables + 9 quarantine tables) |
| `logs/clean_data.log` | Full execution log with quarantine counts |
| `reports/warehouse_validation_report.md` | Source DB validation (pre-clean) |

### Clean Database Row Counts (Key Tables)

| Table | Clean Rows | Quarantined |
|-------|-----------|-------------|
| fact_payroll | 7,340 | 4 (DQ-02: 2, DQ-03: 2) |
| fact_attendance_monthly | 7,339 | 7 (DQ-01) |
| fact_leave | 3,441 | 2 (DQ-08) |
| fact_task | 28,848 | 20 (DQ-06: 12, DQ-07: 8) |
| fact_ledger | 6,784 | 3 (DQ-04) |
| fact_invoice | 743 | 1 (DQ-05) |
| fact_expense | 501 | 1 (DQ-10) |
| fact_attrition_risk | 425 | 5 (DQ-09) |
| dim_employee | 1,606 | 2 (DQ-11) |
| dim_date | 2,647 | 0 |

---

## Data Quality Issues (DQ-01 through DQ-11)

| ID | Issue | Resolution | Status |
|----|-------|------------|--------|
| **DQ-01** | Attendance after exit | 7 rows quarantined | ✅ Resolved |
| **DQ-02** | Duplicate payroll rows | 2 rows quarantined | ✅ Resolved |
| **DQ-03** | Orphan payroll (employee_key=-1) | 2 rows quarantined | ✅ Resolved |
| **DQ-04** | Jun 2026 payroll/ledger mismatch (₹18,450) | **Documented unresolved**: 3 D01 ledger lines in JE-002094 quarantined; original amounts re-inserted unchanged; DQ-C01 flags known exception | ⚠️ Documented |
| **DQ-05** | Overpaid invoice (INV-00385) | 1 row corrected (amount_paid = total_amount) | ✅ Resolved |
| **DQ-06** | Task completed before started (12 tasks) | **Swapped** dates (plausible transposition; `due_date` after both dates); **assumption documented in code**; originals quarantined | ⚠️ Assumption documented |
| **DQ-07** | Done tasks missing completed_date (8 tasks) | **Excluded** from analytical table per data contract ("completed_date required when status = Done"); originals quarantined; **no imputation** | ✅ Resolved |
| **DQ-08** | Leave end_date < start_date (2 tasks) | Swapped dates & keys; recalculated days | ✅ Resolved |
| **DQ-09** | Stale attrition predictions (5) | 5 rows quarantined | ✅ Resolved |
| **DQ-10** | Expense total ≠ excl_gst + gst (1) | 1 row corrected | ✅ Resolved |
| **DQ-11** | SCD overlap (EMP-0001) | 2 versions corrected (valid_to adjusted); originals quarantined | ✅ Resolved |

---

## Validation Gates (All Passing)

| Gate | Check | Result |
|------|-------|--------|
| DQ-C01 | Payroll = Ledger (monthly) | ✅ PASS (June 2026 known exception) |
| DQ-C02 | Ledger balanced (all JEs) | ✅ PASS |
| DQ-C03 | Unique payroll rows (employee_id, run_id) | ✅ PASS |
| DQ-C04 | No orphan employees in payroll | ✅ PASS |
| DQ-C05 | No attendance after exit | ✅ PASS |
| DQ-C07 | Invoice paid ≤ total, balance ≥ 0 | ✅ PASS |
| DQ-C08 | Expense total = excl_gst + gst | ✅ PASS |
| DQ-C09 | Task dates sensible (no completed < started; Done has completed_date) | ✅ PASS |
| DQ-C10 | Leave end_date ≥ start_date | ✅ PASS |
| DQ-C11 | Attrition predictions within 7 days of latest | ✅ PASS |
| DQ-C12 | No SCD interval overlaps | ✅ PASS |
| Reconciliation | 18 months vs workbook answer key | ✅ PASS (core metrics) |

---

## Known Limitations

1. **DQ-04 (Jun 2026 ledger discrepancy):** ₹18,450 mismatch localized to D01 department (3 salary lines in JE-002094). No authoritative evidence identifies the erroneous line(s). Proportional scaling removed as unverified assumption. Original data preserved; discrepancy flagged in quarantine and DQ-C01 known exception.

2. **DQ-06 (12 task date swaps):** Swap is plausible (all 12 have `due_date` after both `started_date` and `completed_date`) but **unsubstantiated** — no source confirms which date is correct. Assumption explicitly documented in `clean_fact_task`; originals quarantined.

3. **fact_forecast 'ALL' scope:** 12 rows with `department_id = 'ALL'` are orphaned from `dim_department`. This is **explicitly allowed by `data_contracts`**; downstream consumers must handle.

4. **dim_date extension:** Extended to 2027-03-31 to support forecast joins. Marked UNRESOLVED in logs.

5. **kpi_targets missing D00:** Only 10 departments in `data_dictionary`; appears intentional.

6. **Revenue/profit sign convention:** Workbook uses absolute values; ledger uses debit-positive convention (revenue = negative/credit). Only core DQ-C01 metrics (payroll_employer_cost, ledger_salary_related_expense) are validated against answer key.

---

## Reports

| Report | Purpose |
|--------|---------|
| `REMEDIATION_REPORT.md` | Final summary of all fixes, test results, quarantine counts |
| `FINAL_AUDIT_REPORT.md` | Evidence-based audit with documented limitations |
| `reports/data_cleaning_plan.md` | Detailed cleaning plan per DQ issue |
| `reports/warehouse_validation_report.md` | Source database validation (pre-clean) |
| `reports/data_quality_investigation.md` | DQ investigation notes |

---

## Source Integrity (Verified)

| Artifact | SHA-256 | Status |
|----------|---------|--------|
| `data/raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx` | `fb7569b0463a03cb8ad68e11149e6294ba8027296ab70e365ad3b98c136ac140` | ✅ Unchanged |
| `data/warehouse/pulseiq.duckdb` | `225594282857e3f9c08b3c432f76eed7dd39e6b5972618b2798c64d9b0c81a6d` | ✅ Unchanged |

---

## Quick Reference

```bash
# Full pipeline: extract → clean → test
python src/extract_data.py
python src/clean_data.py
python -m pytest tests/test_clean_data.py -v

# View clean database
python -c "import duckdb; c=duckdb.connect('data/warehouse/pulseiq_clean.duckdb'); [print(f'{t[0]}: {c.execute(f\"SELECT COUNT(*) FROM \\\"{t[0]}\\\"\").fetchone()[0]:,}') for t in c.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=\"main\"').fetchall()]"
```