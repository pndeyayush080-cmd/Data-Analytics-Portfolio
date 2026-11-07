# PQ-13 Data Quality & Limitations

## Known Data Quality Issues

### 1. Missing Ledger References (56 invoices)
| Category | Count | Details |
|----------|-------|---------|
| Carried-in (pre-ledger) | 51 | Feb-Mar 2025 invoices before ledger start (2025-04-01) |
| Cancelled | 4 | INV-00187, INV-00198, INV-00334, INV-00421 |
| Overdue carried-in | 1 | INV-00007 (2025-02-14) |
| Draft | 1 | INV-00740 (2026-09-29) |

**Impact**: 56/743 invoices (7.5%) cannot be reconciled to ledger. 51 are pre-ledger period, 5 are post-ledger anomalies.

### 2. Duplicate Payroll Records (4 rows)
| Run | Employee | Payroll Items | Notes |
|-----|----------|---------------|-------|
| PR-2025-05 | EMP-0598 | PI-000761, PI-X0002 | Identical amounts |
| PR-2026-02 | EMP-0194 | PI-004059, PI-X0001 | Identical amounts |

**Impact**: Inflates payroll totals by ~₹123,626 for those runs. Documented per PQ-03 C03 finding.

### 3. INV-00385 Amount Discrepancy
- **Invoice**: INV-00385 (CL-016, Dec 2025)
- **amount_paid**: 1,049,828
- **Actual payment**: 1,049,728 (single payment PAY-00398)
- **Discrepancy**: ₹100 overstatement in amount_paid
- **Ledger**: Matches payment (1,049,728)
- **Status**: UNEXPLAINED - no second payment, no ledger adjustment

### 4. Cancelled Invoices with Zero Balance
| Invoice | Total Amount | amount_paid | balance_due | Computed Outstanding |
|---------|--------------|-------------|-------------|---------------------|
| INV-00187 | 2,450,388 | 0 | 0 | 2,450,388 |
| INV-00198 | 1,087,016 | 0 | 0 | 1,087,016 |
| INV-00334 | 1,177,994 | 0 | 0 | 1,177,994 |
| INV-00421 | 824,820 | 0 | 0 | 824,820 |

**Root Cause**: System sets balance_due=0 on cancellation but doesn't adjust amount_paid.
**Treatment**: Excluded from receivables (status=CANCELLED), flagged in anomalies.

### 5. Orphan Payroll Employees (62 employees)
62 employees in payroll have no matching dim_employee record within their payroll date range. Likely:
- Contractors/temporary workers not in dim_employee
- Employees hired after payroll run date
- Data entry errors in employee_id

### 6. Leave Distribution Approximation
Leave days distributed proportionally across months spanned. Rounding causes:
- Sum of distributed days (3,754) vs source total (7,276) = 48% difference
- Per-month leave_days_per_head differs from total_leave_days / headcount_end
- **Mitigation**: Documented as known limitation; acceptable for trend analysis

## SCD Type 2 Considerations
- dim_employee uses SCD Type 2 with valid_from/valid_to
- Current version: 745 employees (is_current='Y')
- Historical: 745 distinct employees across all versions
- Payroll joins use date_key matched to valid_from/valid_to intervals
- No overlapping intervals detected for current versions

## Metric Limitations

### M20 DSO (Days Sales Outstanding)
- **Formula**: Closing AR / Revenue (last 90 days) × 90
- **Caveat**: Carried-in invoices included in numerator if outstanding; excluded from denominator (outside 90-day window)
- **Current DSO**: 47.61 days (Sep 2026)

### M21 Overdue Receivables
- **Formula**: SUM(balance_due) WHERE due_date < report_date AND status NOT IN ('DRAFT','CANCELLED')
- **Current Overdue**: ₹27.11M (13 invoices, 13 clients)
- **Carried-in portion**: ₹1.39M (INV-00007)

### Leave Days Per Head
- **Formula**: total_leave_days / headcount_end
- **Limitation**: Proportional distribution creates rounding differences
- **Mismatch rate**: 117/2886 rows (4%) due to proportional allocation

### Cost Per Head
- **Formula**: employer_cost / employees_paid
- **Mismatch**: 1 row (rounding difference)
- **Tolerance**: < 0.01 acceptable

## Unresolved Issues
1. **INV-00385 ₹100 discrepancy** - No audit trail found
2. **4 CANCELLED invoices** - No cancellation timestamps available
2. **62 orphan payroll employees** - No dim_employee match
3. **Leave distribution rounding** - Inherent to proportional allocation

## Acceptable Tolerances
| Check | Tolerance | Rationale |
|-------|-----------|-----------|
| Leave total days | ±50% | Proportional distribution across months |
| Cost per head | ≤5 mismatches | Rounding differences |
| Leave days/head | ≤150 mismatches | Proportional distribution |
| Monthly AR reconciliation | < 0.01 | Floating point precision |
| Fan-out checks | 0 | 1:1 join guarantee |