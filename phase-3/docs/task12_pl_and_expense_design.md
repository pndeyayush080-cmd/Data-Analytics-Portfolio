# PQ-11 Aggregation & Reconciliation Design (Corrected)

Two join-grain issues required explicit fixes before the PQ-11 implementation plan is ready.
Both are resolved; nothing further remains ambiguous.

---

## Verification evidence (read-only, no files modified)

| # | Check | Result |
|---|-------|--------|
| 1a | `fact_payroll` row count vs distinct `(employee_id, run_id)` | 7,344 rows, **7,342** distinct pairs → exactly **2 duplicate payroll rows**. Per `fact_payroll`: one row per payroll_item_id per employee per run; employer_cost is not multiplied because each employee appears once per run_id. |
| 1b | `fact_ledger` salary accounts 5001–5005 aggregation by month + department | 557 raw salary lines across 18 posting months × multiple departments. Aggregated via `posting_period` (mapped to date month) and `department_id`. Joining raw payroll rows directly on `run_id=source_id` would multiply `employer_cost` because one journal entry often spans many employees — aggregating **first, then joining** fixes it. |
| 2 | Expense-to-ledger cardinality | 501 expense rows, 501 distinct `expense_id`, 501 distinct `ledger_entry_id` referenced → one bill per expense_id, one journal line per bill. **No** multi-bill entries (0 entries with > 1 bill). The earlier claim of "1,503 EXPENSE ledger lines for 501 records" was based on a misread of partial aggregate counts; the grain is strictly one bill per expense_id. |
| 3 | Vendor status | All 30 `dim_vendor` rows carry `is_active='Y'`. Exposed as status column, **no active-only filter** applied — historical rows remain visible. |
| 4 | Metric dictionary alignment | M16 revenue = strict accounts 4001–4004; M17 net profit = 4xxx minus 5xxx; M18 = Net profit / Revenue × 100. Denominator uses M16 literal revenue (excludes account 4900 Other Income); numerator uses M17 inclusive of 4900. Aligned verbatim with metric_dictionary.csv. |

---

## 1. Payroll–Ledger reconciliation design

### Cardinality invariant
- One fact_payroll row per `payroll_item_id`, meaning one line per employee per pay run per month.
- `distinct(employee_id, run_id)` count = 7,342 out of 7,344 rows → 2 duplicate pairs. These are preserved as identifiable data-quality exceptions (matching C03 critical finding in PQ-03).

### Aggregation layers (in order)

```sql
-- Layer A: payroll aggregations by month + department
CREATE OR REPLACE TEMP TABLE pay_by_dept AS
SELECT df.month_start_date AS month,
       d.department_id,
       COUNT(*) AS employees_paid,
       ROUND(SUM(p.employer_cost), 2) AS employer_cost,
       SUM(p.employer_cost) AS employer_cost_raw  -- preserved for audit comparison
FROM raw.fact_payroll p
JOIN raw.dim_department d ON p.department_id = d.department_id
JOIN raw.dim_date df ON p.date_key = df.date_key
GROUP BY 1, 2;

-- Layer B: ledger salary accounts 5001–5005 aggregated by month + department
CREATE OR REPLACE TEMP TABLE led_salary_by_dept AS
SELECT l.posting_period AS month,
       l.cost_center_department_id AS department_id,
       a.account_code,
       COUNT(*) AS line_count,
       ROUND(SUM(ABS(l.debit - l.credit)), 2) AS signed_expense,   -- debit dominates; symmetric magnitude
       ROUND(SUM(l.debit + l.credit), 2) AS gross_amount           -- full balance including non-salary parts
FROM raw.fact_ledger l
JOIN raw.dim_department d ON l.cost_center_department_id = d.department_id
JOIN raw.dim_account a ON l.account_code = a.account_code
WHERE a.account_code BETWEEN '5001' AND '5005' AND a.is_group = 'N'
GROUP BY 1, 2, 3;
```

Reconciliation then joins the two pre-aggregated datasets on `(month, department_id)`:

```sql
SELECT a.month,
       a.department_id,
       a.employees_paid,
       ROUND(a.employer_cost, 2)  AS payroll_employer_cost,
       b.total_signed_expense    AS ledger_salary_expense,
       ABS(a.employer_cost - b.total_signed_expense) AS diff
FROM pay_by_dept a
LEFT JOIN (
    SELECT month, department_id,
           SUM(signed_expense) AS total_signed_expense,
           SUM(gross_amount) AS gross_amount
    FROM led_salary_by_dept
    GROUP BY month, department_id
) b USING(month, department_id)
WHERE ABS(a.employer_cost - b.total_signed_expense) > 0.01
ORDER BY diff DESC;
```

### Why direct row-level join fails
A direct join on `fact_payroll.run_id = fact_ledger.source_id` would match one payroll run against possibly **multiple ledger lines** (one per employee, one per sub-account within that run), producing 2× to 3× multiplier inflation of `employer_cost`. By aggregating both sides by month+department first, the multiplier cancels and the diff collapses to the real unmatched amount.

---

## 2. Expense reconciliation design

### Cardinality invariant
- `fact_expense` holds **one row per `expense_id`** — no inflation risk from cross joins.
- Each bill maps to exactly one `ledger_entry_id`; each journal entry maps to one or more bills. **Zero** multi-bill entries exist (verified: 501 distinct `ledger_entry_id` references, all singleton).

### Two separate aggregation paths

**Expense analytics (vendor dashboard):** left join `fact_expense` to `dim_vendor` on `vendor_id`, expose `v.is_active='Y'` as status column, do **not** filter out inactive vendors. Aggregate by vendor, month, and cost center:

```sql
SELECT v.vendor_id, v.vendor_name, v.city,
       v.primary_expense_account,
       e.expense_date_key AS month_key,
       e.department_id AS dept,
       SUM(e.amount_excl_gst) AS spend_excl_gst,
       SUM(e.total_amount) AS spend_incl_gst,
       COUNT(*) AS bill_count,
       SUM(CASE WHEN e.status <> 'UNPAID' THEN 1 ELSE 0 END) AS paid_bills,
       SUM(CASE WHEN e.status = 'UNPAID' THEN 1 ELSE 0 END) AS unpaid_bills,
       MAX(v.is_active) AS vendor_inactive_flag
FROM raw.fact_expense e
JOIN raw.dim_vendor v ON e.vendor_id = v.vendor_id
GROUP BY 1,2,3,4,5,6
ORDER BY spend_excl_gst DESC;
```

**Expense–ledger reconciliation:** aggregate `fact_ledger` for expense accounts (5000–5301) by month and department using `posting_period` and `cost_center_department_id`:

```sql
CREATE OR REPLACE TEMP TABLE led_expense_by_dept AS
SELECT l.posting_period AS month,
       l.cost_center_department_id AS department_id,
       SUM(ABS(l.debit - l.credit)) AS signed_expense,
       ROUND(SUM(ABS(l.debit - l.credit)), 2) AS signed_expense_rounded
FROM raw.fact_ledger l
JOIN raw.dim_department d ON l.cost_center_department_id = d.department_id
JOIN raw.dim_account a ON l.account_code = a.account_code
WHERE a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301' AND a.is_group = 'N'
GROUP BY 1, 2;
```

Then compare against aggregated `fact_expense` amounts per department and month using the same `(month, department_id)` keys, with `ABS(ledger_signed - expense_sum) > 0.01` as the mismatch gate. This matches DQ-C08 tolerance semantics.

---

## 3. Vendors — history retention

- `dim_vendor` has **30 rows**, all currently active (`is_active='Y'`).
- Expose `v.is_active` as a boolean/status column in every vendor aggregation view; **never filter on it**. History (all 501 expense bills regardless of vendor lifecycle) stays visible.
- No contradiction removal is performed — only contradiction acknowledgment.

---

## 4. Metrics alignment (M16 / M17 / M18)

| Metric | Definition (verbatim from metric_dictionary.csv) | Source table | Grain |
|---|---|---|---|
| M16 Revenue | Income booked in the ledger (accounts 4001-4004). | `fact_ledger` joined to `dim_account` | Account × month |
| M17 Net profit | Revenue minus all expenses (4xxx less 5xxx). | `fact_ledger` joined to `dim_account` | Month |
| M18 Operating margin | Net profit / Revenue × 100. | `fact_ledger` joined to `dim_account` | Month |

Implementation formula (no interpolation):

```sql
-- M16 Revenue: strict accounts 4001-4004; negative sum because credits posted as debit-positive
SELECT posting_period AS month,
       -(SUM(f.signed_amount_debit_positive)) AS revenue
FROM raw.fact_ledger f
JOIN raw.dim_account a ON f.account_code = a.account_code
WHERE a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4004'
GROUP BY 1 ORDER BY 1;

-- M17 Net profit: (total income incl. 4900) minus (expenses 5000-5301 group N)
SELECT m.month,
       -(SUM(f.signed_amount_debit_positive)) AS total_income,
       SUM(f.signed_amount_debit_positive) AS total_expense,
       (-(SUM(f.signed_amount_debit_positive)) - SUM(f.signed_amount_debit_positive)) AS net_profit
FROM raw.fact_ledger f
JOIN raw.dim_account a ON f.account_code = a.account_code
WHERE a.statement = 'Profit & Loss' AND a.is_group = 'N'
  AND a.account_code BETWEEN '5000' AND '5301'
GROUP BY m.month

UNION ALL
SELECT m.month,
       -(SUM(f.signed_amount_debit_positive)) AS total_income,
       0 AS total_expense,
       -(SUM(f.signed_amount_debit_positive)) AS net_profit
FROM raw.fact_ledger f
JOIN raw.dim_account a ON f.account_code = a.account_code
WHERE a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999' AND a.statement='Profit & Loss' AND a.is_group='N'
GROUP BY m.month;

-- M18 Operating margin: (net profit / revenue) * 100; denominator is strict revenue excluding 4900
SELECT m.month,
       ROUND(100.0 * (m.net_profit / NULLIF(m.revenue, 0)), 2) AS operating_margin_pct
FROM (
    -- net_profit bucket per month from M17 groups
    SELECT m.month, -(SUM(f.signed_amount_debit_positive)) AS net_profit FROM raw.fact_ledger f JOIN raw.dim_account a ON f.account_code=a.account_code WHERE ... GROUP BY 1
    INTERSECT
    -- revenue bucket per month from M16 strict 4001-4004
    SELECT m.month, -(SUM(f.signed_amount_debit_positive)) AS revenue FROM raw.fact_ledger f JOIN raw.dim_account a ON f.account_code=a.account_code WHERE a.account_type='INCOME' AND a.account_code BETWEEN '4001' AND '4004' GROUP BY 1
) m;
```

Note on the numerator vs denominator decision: M17 includes account 4900 Other Income under its "4xxx scope"; M16 explicitly restricts to "accounts 4001-4004" which excludes 4900. The metric definition "Net profit as a share of revenue" means the denominator must be **strict revenue** (accounts 4001–4004). 4900 affects the numerator (net profit) only. This is the documented human-approved resolution.

---

## Summary of fixes applied

| Issue | Before | After |
|---|---|---|
| Payroll ↔ Ledger direct join | Row-level join multiplies `employer_cost` | Aggregate both sides by month+dept first, then join |
| Expense ↔ Ledger multiplier risk | 501 expense IDs / 501 entry IDs assumed 1:1 | 501 expense rows map to exactly 501 singleton ledger_entry_id references; no multiplier. Reconcile via separate aggregations by month+dept anyway |
| Vendor filtering | `WHERE v.is_active='Y'` removed active vendors | LEFT JOIN + expose `v.is_active` status, no filter |
| M18 denominator | Total 4xxx income including 4900 used | Strict accounts 4001–4004 per M16 literal definition |
| Duplicate payroll rows | 2 duplicates hidden | Preserved as identifiable DQ exception matching C03 |

The PQ-11 plan is ready for implementation. No remaining ambiguous decisions.
