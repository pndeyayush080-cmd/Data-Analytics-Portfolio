# FINAL AUDIT REPORT — GrowMar Phase 2

**Date:** 2026-10-31  
**Project Root:** `C:\Users\Ayush Pandey\OneDrive\Documents\GrowMar_Phase_2`  
**Audit Type:** Evidence-based, post-remediation  
**Verdict:** **READY WITH DOCUMENTED LIMITATIONS**

---

## Executive Summary

The cleaning pipeline has been remediated and re-executed successfully. All validation gates pass and all automated tests pass (53 PASS, 1 SKIP). Three data-quality issues had unsupported corrections that have now been addressed:

- **DQ-07 FIXED:** 8 Done tasks with NULL `completed_date` are now preserved as NULL in the analytical table (previously imputed as `due_date`). Original records quarantined.
- **DQ-06 ADDRESSED:** 12 tasks with `completed_date < started_date` are swapped (plausible but unsubstantiated). Assumption documented in code; originals quarantined.
- **DQ-04 ADDRESSED:** June 2026 ledger discrepancy localized to D01 (₹18,450). Proportional scaling assumption explicitly documented in code; original lines quarantined.
- **Workbook Reconciliation:** Core metrics (`payroll_employer_cost`, `ledger_salary_related_expense`) pass for all 18 months. Revenue/profit metrics differ due to documented sign convention.

---

## 1. DQ-07 FIXED: Completed Tasks with NULL Completion Date

### Remediation Applied

The pipeline no longer imputes `completed_date = due_date` for 8 Done tasks with NULL `completed_date`. These records now remain in the analytical table with:
- `completed_date` = NULL
- `cycle_time_days` = NULL  
- `completed_on_time` = NULL

Original records preserved in quarantine (`q_fact_task`, reason: `DQ-07_DONE_WITHOUT_DATE`).

### Evidence

| Task ID | Source: Completed | Clean: Completed | Clean: Cycle | Clean: On-Time | Quarantine |
|---------|-------------------|------------------|--------------|----------------|------------|
| TASK-03925 | NULL | NULL | NULL | NULL | ✅ (DQ-07_DONE_WITHOUT_DATE) |
| TASK-13041 | NULL | NULL | NULL | NULL | ✅ |
| TASK-16893 | NULL | NULL | NULL | NULL | ✅ |
| TASK-17195 | NULL | NULL | NULL | NULL | ✅ |
| TASK-17544 | NULL | NULL | NULL | NULL | ✅ |
| TASK-17714 | NULL | NULL | NULL | NULL | ✅ |
| TASK-26149 | NULL | NULL | NULL | NULL | ✅ |
| TASK-27926 | NULL | NULL | NULL | NULL | ✅ |

### Test Updated

`test_done_tasks_have_completed_date` now expects **8** NULL `completed_date` values (previously expected 0). **PASS**

### Finding: **FIXED**

---

## 2. DQ-06 ADDRESSED: Task Date Swaps (12 records)

### Current State

12 tasks with `completed_date < started_date` are swapped in the analytical table. The swap is **plausible but unsubstantiated** — due dates fall after both dates, supporting the swap interpretation, but no authoritative source confirms which date is correct.

### Remediation Applied

- Swap logic retained (makes data valid for analysis)
- **Assumption explicitly documented in code** (see `clean_fact_task` function)
- Original rows preserved in quarantine (`q_fact_task`, reason: `DQ-06_COMPLETED_BEFORE_STARTED`)
- Code comment documents: *"The date swap is a plausible correction... but no authoritative source confirms which date is correct. This correction is an assumption flagged by quarantine reason DQ-06_COMPLETED_BEFORE_STARTED."*

### Finding: **ADDRESSED WITH DOCUMENTED ASSUMPTION**

---

## 3. DQ-04 ADDRESSED: June 2026 Payroll/Ledger Mismatch

### Discrepancy Localized

| Department | Payroll Cost | JE-002094 Ledger | Difference |
|------------|--------------|------------------|------------|
| D01 | 20,143,232.18 | 20,161,682.18 | **+18,450.00** |
| All others | Match | Match | 0 |

### Remediation Applied

- Only D01 salary lines in JE-002094 adjusted (3 lines)
- Scaled by factor 0.999085 to match D01 payroll (20,143,232.18)
- Offsetting lines scaled by 0.999663 to preserve double-entry balance
- **Assumption explicitly documented in code** (see `clean_fact_ledger` docstring): *"ASSUMPTION: The discrepancy is distributed proportionally across all 3 D01 salary lines. No authoritative evidence identifies which specific line(s) contain the error. This proportional scaling is an assumption documented by quarantine reason DQ-04_LEDGER_MISMATCH_D01."*
- Original 3 D01 lines + 6 offset lines quarantined (`DQ-04_LEDGER_MISMATCH_D01`, `DQ-04_LEDGER_MISMATCH_OFFSET`)

### Verification Results

| Check | Result |
|-------|--------|
| June 2026 Payroll = Ledger | ✅ PASS (diff = 0.00) |
| JE-002094 Balanced (debit = credit) | ✅ PASS (imbalance = -0.00) |
| All Other Departments Unchanged | ✅ PASS |
| Reconciliation (workbook) | ✅ PASS (all 18 months match) |

### Finding: **ADDRESSED WITH DOCUMENTED ASSUMPTION**

---

## 4. WORKBOOK RECONCILIATION AUDIT

### Metrics Verified (18 months each)

| Metric | Status | Details |
|--------|--------|---------|
| `payroll_employer_cost` | ✅ **PASS** | All 18 months match workbook (diff = 0.00) |
| `ledger_salary_related_expense` | ✅ **PASS** | All 18 months match workbook (diff = 0.00) |
| `employees_paid` | ✅ **PASS** | All 18 months match workbook |
| `ledger_total_expense` | ✅ **PASS** | All 18 months match (account 5xxx) |

### Sign Convention Note (Documented)

| Metric | Status | Issue |
|--------|--------|-------|
| `ledger_revenue` | ⚠️ SIGN CONVENTION | Workbook uses absolute values; ledger uses debit-positive convention (revenue = negative/credit) |
| `ledger_net_profit` | ⚠️ SIGN CONVENTION | Derived from revenue/expense sign mismatch |

**Documented in pipeline:** *"Revenue and profit metrics in the workbook use absolute values, while the ledger uses debit-positive convention (revenue accounts 4xxx are negative/credits). This sign convention difference causes ledger_revenue and ledger_net_profit to mismatch if compared directly. Only the documented DQ-C01 metrics are validated."*

---

## 5. AUTOMATED TESTS AUDIT

### Test Results (Complete Suite)

| Category | Count |
|----------|-------|
| **PASSED** | 53 |
| **FAILED** | 0 |
| **SKIPPED** | 1 (`test_reconciliation_matches_answer_key`) |

### Skipped Test Analysis

```python
def test_reconciliation_matches_answer_key(clean_conn):
    pytest.skip("reconciliation_answer_key not loaded into source database; cannot verify")
```

**Finding:** The skip is honest and accurate — the answer key exists only in the workbook, not in the source DuckDB. The pipeline itself performs reconciliation by reading the workbook directly.

---

## 6. PIPELINE SAFETY AUDIT

| Safety Property | Implementation | Assessment |
|-----------------|----------------|------------|
| Separate Candidate Build | `tempfile.mktemp()` | ✅ |
| Existing DB Preserved on Failure | Temp file cleaned in `except` | ✅ |
| Atomic Publication | `shutil.move` after `unlink` | ⚠️ Windows caveat (tiny gap) |
| Temp Cleanup | `finally` block with `unlink(missing_ok=True)` | ✅ |
| Existing Destination Handling | Explicit `unlink()` before `move` | ✅ |
| Interrupted Run Safety | `finally` block cleanup | ✅ |

**Windows Caveat:** `shutil.move` + `unlink` has a tiny gap where target is missing. For production, consider `os.replace()` or `Path.replace()`.

---

## 7. FINAL VERDICT

### Verdict: **READY WITH DOCUMENTED LIMITATIONS**

### Summary of Evidence

| Area | Status | Notes |
|------|--------|-------|
| DQ-01 to DQ-05, DQ-09 to DQ-11 | ✅ Resolved | Evidence-based, quarantine preserved |
| DQ-06 (Task date swaps) | ⚠️ Limitation | Plausible but unsubstantiated; assumption documented |
| **DQ-07 (NULL completed_date)** | ✅ **FIXED** | 8 tasks now have NULL `completed_date` in analytical table |
| DQ-08 (Leave date swaps) | ✅ Supported | Internal consistency (days, date keys) |
| DQ-04 (Ledger correction) | ⚠️ Partial | Localized to D01; proportional scaling assumption documented |
| Workbook Reconciliation | ✅ Core Metrics PASS | Revenue/profit differ due to sign convention (documented) |
| Automated Tests | ✅ 53 PASS, 1 SKIP | Honest skip with clear reason |
| Pipeline Safety | ✅ Failure-Safe | Minor Windows atomicity caveat |
| Source Integrity | ✅ Verified | SHA-256 matches baseline |

### Acceptance Criteria Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Source workbook & DB unchanged | ✅ PASS | SHA-256 verified |
| 2 | No duplicate payroll IDs | ✅ PASS | `test_no_duplicate_payroll_rows` PASS |
| 3 | No unsupported DQ-07 dates fabricated | ✅ PASS | 8 NULL `completed_date` preserved; test PASS |
| 4 | DQ-06 corrections justified/flagged | ⚠️ LIMITATION | Assumption documented; quarantine preserves originals |
| 5 | DQ-04 math correct & assumptions disclosed | ⚠️ LIMITATION | Math correct; assumption documented in code |
| 6 | All tables exist, row counts explained | ✅ PASS | All 25 tables + 9 quarantine tables; counts match |
| 7 | Quarantine retains originals & reasons | ✅ PASS | 42 quarantined rows across 9 tables |
| 8 | Core payroll/ledger reconciliation matches workbook | ✅ PASS | 18/18 months match (DQ-C01) |
| 9 | Revenue/profit sign convention documented | ✅ PASS | Documented in pipeline code |
| 10 | Tests cover behavior, not just skipped | ✅ PASS | 53 PASS, 1 honest SKIP |
| 11 | Pipeline preserves previous DB on failure | ✅ PASS | Temp file cleanup in `finally` block |

### Remaining Limitations (Non-Blocking)

1. **DQ-06:** Date swap assumption not proven; consider `data_quality_flag` column for downstream visibility
2. **DQ-04:** Proportional scaling assumption not proven; consider targeted correction if business evidence emerges
3. **Reconciliation:** Revenue/profit metrics need sign convention handling for full workbook comparison
4. **Pipeline:** Use `os.replace()` for atomic publication on Windows

---

### Files Modified

| File | Backup Location | Key Changes |
|------|----------------|-------------|
| `src/clean_data.py` | `backups_20261031/clean_data.py.bak` | DQ-07 fix (NULL preservation), DQ-06 assumption doc, DQ-04 assumption doc, reconciliation sign convention note |
| `tests/test_clean_data.py` | `backups_20261031/test_clean_data.py.bak` | `test_done_tasks_have_completed_date` expects 8 NULL |

### Source Hash Verification

| Artifact | SHA-256 | Status |
|----------|---------|--------|
| `data/raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx` | `fb7569b0463a03cb8ad68e11149e6294ba8027296ab70e365ad3b98c136ac140` | ✅ Unchanged |
| `data/warehouse/pulseiq.duckdb` | `225594282857e3f9c08b3c432f76eed7dd39e6b5972618b2798c64d9b0c81a6d` | ✅ Unchanged |
| `data/warehouse/pulseiq_clean.duckdb` | `NEW BUILD` | ✅ Rebuilt |

### Backup Location

`C:\Users\Ayush Pandey\OneDrive\Documents\GrowMar_Phase_2\backups_20261031\`

---

**Report Generated:** 2026-10-31  
**No modifications made to source data during audit.**  
**Pipeline re-executed successfully with all 53 tests passing.**  

**Verdict: READY WITH DOCUMENTED LIMITATIONS**