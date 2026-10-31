# Task 3 — Data Quality Gatekeeper Report

## Decision for managers

The latest gatekeeper run is **blocked**: five critical controls fail (C01, C03,
C04, C12 and C14; C02 and C13 pass).  Warning findings are retained for their
owners but do not stop a technically complete load.  No raw source file or
warehouse table was changed to obtain this result.

The evidence is stored in `main.dq_results`.  Each row contains the check,
source table(s), number of bad rows, status, execution time, and up to ten
example bad rows in `details_json`.

## What every check protects against

| Check | Plain-English risk if it fails | Decision |
| --- | --- | --- |
| C01 Payroll equals ledger | Pay costs and finance expenses disagree, so financial and people reports tell different stories. | Stop load |
| C02 Ledger balanced | A journal entry has more debit than credit (or the reverse), making the books unreliable. | Stop load |
| C03 Unique payroll rows | The same employee/run is counted twice, overstating pay and headcount-linked costs. | Stop load |
| C04 No orphan employees | Payroll references a person who is absent from the employee dimension, so joins and employee reporting lose or misstate pay. | Stop load |
| C05 No attendance after exit | Attendance is recorded after a person left, inflating workforce attendance. | Warn and send to HR |
| C06 Unpaid leave deducted | Unpaid absence and payroll leave-without-pay do not agree, creating a possible pay error. | Warn and send to Payroll |
| C07 Invoice arithmetic | An invoice is overpaid or has a negative balance, misstating receivables. | Warn and send to Finance |
| C08 Expense arithmetic | The bill total does not equal amount plus GST, overstating or understating expense. | Warn and send to Finance |
| C09 Task dates sensible | A task finishes before it starts, or is marked Done without a finish date, corrupting cycle-time and delivery KPIs. | Warn and send to Engineering Ops |
| C10 Leave dates sensible | A leave end is before its start, producing negative leave duration. | Warn and send to HR |
| C11 AI feeds fresh | Risk/anomaly scores are stale and may be presented as current. | Warn and send to AI/ML |
| C12 Dimension history does not overlap | One employee can match two history versions for the same date, duplicating fact joins. | Stop load |
| C13 Pipeline freshness | The latest completed pipeline run is more than 24 hours old or incomplete, so the dashboard may be stale. | Stop load |
| C14 Minimum group size | A manager-facing aggregate may expose a group smaller than its privacy threshold. | Stop manager publication |

The stop decisions match the catalog's Critical severity.  Warnings remain
visible in the summary because they can still affect individual records and
KPIs, but they are business-review exceptions rather than structural failures
that make the whole load unusable.  C14 is intentionally fail-closed: there is
currently no `manager_aggregate_groups` register, so the system cannot prove
that manager output is privacy-safe.  Register an output with its metric,
group key, distinct employee count, and required minimum before publication.

## Latest evidence summary

Run `9d0c3c99-d063-4ff9-8b65-da11c9d45cdd` recorded 14 checks:

| Result | Checks | Bad rows/groups |
| --- | ---: | ---: |
| Pass | 2 (C02, C13) | 0 |
| Critical fail | 5 (C01, C03, C04, C12, C14) | 11 |
| Warning fail | 7 (C05–C11) | 449 |

Notable examples: June 2026 payroll-to-ledger difference is -18,450.00; two
orphan payroll rows are `PI-X0003` and `PI-X0004`; the five stale attrition
records are in the sample; and no manager aggregate register exists.

## Planted-issue comparison — unlock_PQ-03

All **11 of 11** planted issue types were detected; none were missed.

| Vault issue | Gatekeeper evidence | Comparison note |
| --- | --- | --- |
| DQ-01 Attendance after exit | C05: 4 | Exact four `FA-X0001` to `FA-X0004`. |
| DQ-02 Duplicate payroll row | C03: 2 groups | Exact two duplicate employee/run groups. |
| DQ-03 Orphan foreign key | C04: 2 | Exact `PI-X0003` and `PI-X0004`. |
| DQ-04 Payroll/ledger mismatch | C01: 5 months | Includes the planted June 2026 -18,450.00 difference plus four additional monthly mismatches. |
| DQ-05 Overpaid invoice | C07: 1 | Exact `INV-00385`. |
| DQ-06 Completed before started | C09: 20 total | Contains all 12 planted negative-cycle tasks. |
| DQ-07 Done without date | C09: 20 total | Contains all 8 planted Done-without-date tasks. |
| DQ-08 Leave end before start | C10: 2 | Exact two leave requests. |
| DQ-09 Stale prediction | C11: 410 total | Contains the five planted attrition predictions. The other 405 are anomaly scores more than 24 hours before the ETL audit time, a separate C11 freshness condition. |
| DQ-10 Expense total mismatch | C08: 1 | Exact `EXP-00371`, difference 500.00. |
| DQ-11 SCD interval overlap | C12: 1 | Exact employee history overlap for employee key 100000/100001. |

The vault does not enumerate C06 unpaid-leave discrepancies, the four extra
C01 monthly reconciliation differences, or C14's missing publication register;
these are additional findings, not missed planted issues.

## Repeatable evidence commands

```powershell
.\.venv\Scripts\python.exe -B .\src\test_dq_gatekeeper.py
.\.venv\Scripts\python.exe -B .\src\load_to_duckdb.py
.\.venv\Scripts\python.exe -B .\src\inspect_dq_results.py
```

The first command uses only in-memory copies of `raw` tables and removes its
temporary audit-log fixture.  The second runs the gatekeeper after loading; the
loader preserves existing raw tables and never rewrites the source CSV files.
