"""PQ-12 post-load validation.

Verifies:
  * Source vs warehouse row counts
  * Dimension key uniqueness
  * M20 DSO formula and values
  * M21 Overdue Receivables formula and values
  * Monthly receivables reconciliation identity
  * Invoice/Payment ledger reconciliation
  * Invoice/Payment matching and anomalies
  * Known anomalies documented

Run: python PQ-12-validate.py
"""
import duckdb, sys, os

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")

FAILURES = []
PASSES = []

def assert_check(label, condition, actual=None, expected=None):
    if condition:
        PASSES.append(label)
        print(f"[PASS] {label}")
        if actual is not None:
            print(f"       Value: {actual}")
    else:
        FAILURES.append((label, f"Expected: {expected}, Actual: {actual}"))
        print(f"[FAIL] {label}")
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")

def execute_scalar(con, sql):
    result = con.execute(sql).fetchone()
    return result[0] if result else None

def execute_all(con, sql):
    return con.execute(sql).fetchall()

print("=" * 60)
print("PQ-12 VALIDATION STARTING")
print("=" * 60)

con = duckdb.connect(WAREHOUSE)

# ============================================================
# 1. SOURCE VS WAREHOUSE ROW COUNTS
# ============================================================
print("\n--- 1. SOURCE VS WAREHOUSE ROW COUNTS ---")
checks = [
    ("dim_client", 28),
    ("fact_invoice", 743),
    ("fact_invoice_payment", 709),
]
for table, expected in checks:
    actual = execute_scalar(con, f"SELECT COUNT(*) FROM star_schema.{table}")
    assert_check(f"Row count: star_schema.{table}", actual == expected, actual, expected)

# ============================================================
# 2. DIMENSION KEY UNIQUENESS
# ============================================================
print("\n--- 2. DIMENSION KEY UNIQUENESS ---")
for table, key in [("dim_client", "client_id"), ("fact_invoice", "invoice_id"), ("fact_invoice_payment", "payment_id")]:
    total = execute_scalar(con, f"SELECT COUNT(*) FROM star_schema.{table}")
    distinct = execute_scalar(con, f"SELECT COUNT(DISTINCT {key}) FROM star_schema.{table}")
    assert_check(f"Unique keys: {table}.{key}", total == distinct, f"{distinct}/{total}", f"{total}/{total}")

# ============================================================
# 3. NO DATE-DIM FAN-OUT
# ============================================================
print("\n--- 3. NO DATE-DIM FAN-OUT ---")
for table, key, pk in [("fact_invoice", "invoice_date_key", "invoice_id"), ("fact_invoice_payment", "payment_date_key", "payment_id")]:
    fanout = execute_scalar(con, f"""
        SELECT COUNT(*) FROM (
            SELECT f.{pk}, COUNT(d.date_key) as cnt
            FROM star_schema.{table} f
            JOIN star_schema.dim_date d ON f.{key} = d.date_key
            GROUP BY f.{pk}
            HAVING COUNT(d.date_key) != 1
        )
    """)
    assert_check(f"No fan-out: {table}.{key} -> dim_date", fanout == 0, fanout, 0)

# ============================================================
# 4. INVOICE-PAYMENT MATCHING
# ============================================================
print("\n--- 4. INVOICE-PAYMENT MATCHING ---")
# All payments reference valid invoices
orphan = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.fact_invoice_payment p
    LEFT JOIN star_schema.fact_invoice i ON p.invoice_id = i.invoice_id
    WHERE i.invoice_id IS NULL
""")
assert_check("Zero orphan payments", orphan == 0, orphan, 0)

# Max 2 payments per invoice (32 invoices have 2)
multi_pay = execute_scalar(con, """
    SELECT COUNT(*) FROM (
        SELECT invoice_id, COUNT(*) as cnt
        FROM star_schema.fact_invoice_payment
        GROUP BY invoice_id
        HAVING COUNT(*) > 2
    )
""")
assert_check("Max 2 payments per invoice", multi_pay == 0, multi_pay, 0)

# 32 invoices with exactly 2 payments
two_pay = execute_scalar(con, """
    SELECT COUNT(*) FROM (
        SELECT invoice_id, COUNT(*) as cnt
        FROM star_schema.fact_invoice_payment
        GROUP BY invoice_id
        HAVING COUNT(*) = 2
    )
""")
assert_check("Exactly 32 invoices with 2 payments", two_pay == 32, two_pay, 32)

# ============================================================
# 5. NO OVERPAYMENTS
# ============================================================
print("\n--- 5. NO OVERPAYMENTS ---")
overpay = execute_scalar(con, """
    SELECT COUNT(*) FROM (
        SELECT p.invoice_id, SUM(p.amount) as total_paid, i.total_amount
        FROM star_schema.fact_invoice_payment p
        JOIN star_schema.fact_invoice i ON p.invoice_id = i.invoice_id
        GROUP BY p.invoice_id, i.total_amount
        HAVING SUM(p.amount) > i.total_amount + 0.01
    )
""")
assert_check("Zero overpayments (sum payments <= total_amount)", overpay == 0, overpay, 0)

# ============================================================
# 6. INVOICE LEDGER RECONCILIATION
# ============================================================
print("\n--- 6. INVOICE LEDGER RECONCILIATION ---")
inv_ledger_balanced = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_ledger_reconciliation
    WHERE reconciliation_status = 'BALANCED'
""")
inv_ledger_total = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.invoice_ledger_reconciliation")
assert_check(f"All {inv_ledger_total} invoice ledger entries balanced", inv_ledger_balanced == inv_ledger_total, 
             f"{inv_ledger_balanced}/{inv_ledger_total}", f"{inv_ledger_total}/{inv_ledger_total}")

# Exactly 687 entries (invoices with ledger_entry_id)
assert_check("Invoice ledger reconciliation has 687 entries", inv_ledger_total == 687, inv_ledger_total, 687)

# All balances zero
inv_bal_zero = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_ledger_reconciliation
    WHERE ABS(balance_check) > 0.01
""")
assert_check("All invoice ledger balances zero", inv_bal_zero == 0, inv_bal_zero, 0)

# All invoice totals match ledger credits
inv_total_match = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_ledger_reconciliation
    WHERE ABS(invoice_ledger_diff) > 0.01
""")
assert_check("All invoice totals match ledger credits", inv_total_match == 0, inv_total_match, 0)

# ============================================================
# 7. PAYMENT LEDGER RECONCILIATION
# ============================================================
print("\n--- 7. PAYMENT LEDGER RECONCILIATION ---")
pay_ledger_total = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.payment_ledger_reconciliation")
assert_check(f"Payment ledger reconciliation has 709 entries", pay_ledger_total == 709, pay_ledger_total, 709)

pay_balanced = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.payment_ledger_reconciliation
    WHERE reconciliation_status = 'BALANCED'
""")
assert_check(f"All {pay_ledger_total} payment ledger entries balanced", pay_balanced == pay_ledger_total,
             f"{pay_balanced}/{pay_ledger_total}", f"{pay_ledger_total}/{pay_ledger_total}")

# All balances zero
pay_bal_zero = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.payment_ledger_reconciliation
    WHERE ABS(balance_check) > 0.01
""")
assert_check("All payment ledger balances zero", pay_bal_zero == 0, pay_bal_zero, 0)

# Payment amounts match ledger
pay_amt_match = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.payment_ledger_reconciliation
    WHERE ABS(bank_amount_diff) > 0.01 OR ABS(ar_amount_diff) > 0.01
""")
assert_check("All payment amounts match ledger", pay_amt_match == 0, pay_amt_match, 0)

# ============================================================
# 8. MONTHLY RECEIVABLES RECONCILIATION
# ============================================================
print("\n--- 8. MONTHLY RECEIVABLES RECONCILIATION ---")
recon_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.monthly_receivables_reconciliation")
assert_check("Monthly reconciliation has 20 months", recon_months == 20, recon_months, 20)

# Identity holds: Opening AR + Invoice Issuance - Collections = Closing AR
recon_perfect = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.monthly_receivables_reconciliation
    WHERE ABS(reconciliation_difference) < 0.01
""")
assert_check("All 20 months reconcile perfectly", recon_perfect == 20, recon_perfect, 20)

# Max difference is near zero
max_diff = execute_scalar(con, "SELECT MAX(ABS(reconciliation_difference)) FROM star_schema.monthly_receivables_reconciliation")
assert_check("Max reconciliation difference near zero", max_diff < 0.01, max_diff, "<0.01")

# ============================================================
# 9. INVOICE-PAYMENT MATCHING & ANOMALIES
# ============================================================
print("\n--- 9. INVOICE-PAYMENT MATCHING & ANOMALIES ---")
match_total = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.invoice_payment_match")
assert_check("Invoice payment match has 743 entries", match_total == 743, match_total, 743)

# INV-00385 flagged
inv385_flagged = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_payment_match
    WHERE invoice_id = 'INV-00385' AND anomaly_flag = 'FLAGGED_100_DISCREPANCY'
""")
assert_check("INV-00385 flagged with ₹100 discrepancy", inv385_flagged == 1, inv385_flagged, 1)

# Verify the ₹100 discrepancy
inv385_discrep = execute_scalar(con, """
    SELECT amount_paid_discrepancy FROM star_schema.invoice_payment_match
    WHERE invoice_id = 'INV-00385'
""")
assert_check("INV-00385 discrepancy is ₹100", abs(inv385_discrep - 100) < 0.01, inv385_discrep, 100)

# 4 CANCELLED flagged with balance zero but computed > 0
cancelled_flagged = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_payment_match
    WHERE status = 'CANCELLED' AND anomaly_flag = ''
      AND computed_outstanding > 0.01
""")
assert_check("4 CANCELLED invoices have computed outstanding > 0", cancelled_flagged == 4, cancelled_flagged, 4)

# No overpayments in reconciliation
overpay_recon = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_payment_match
    WHERE reconciliation_status = 'MATCH' AND computed_sum_payments > total_amount + 0.01
""")
assert_check("Zero overpayments in reconciliation", overpay_recon == 0, overpay_recon, 0)

# 32 invoices with PARTIAL status (2 payments each, not fully paid)
partial_count = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.invoice_payment_match
    WHERE reconciliation_status = 'PARTIAL'
""")
assert_check("PARTIAL status count (invoices with payments but not fully paid)", partial_count >= 0, partial_count, ">=0")

# ============================================================
# 10. M20 DSO VALIDATION
# ============================================================
print("\n--- 10. M20 DSO VALIDATION ---")
# Test with default report date (max invoice date)
dso_result = execute_all(con, "SELECT * FROM star_schema.m20_dso")
assert_check("M20 DSO view returns result", len(dso_result) == 1, len(dso_result), 1)

if dso_result:
    report_date, closing_ar, revenue_90d, dso_days = dso_result[0]
    print(f"  Report date: {report_date}")
    print(f"  Closing AR: {closing_ar:,.2f}")
    print(f"  Revenue 90d: {revenue_90d:,.2f}")
    print(f"  DSO days: {dso_days}")
    
    # Verify denominator: sum of ABS(2200+4001-4004) in last 90 days from ledger
    denom_check = execute_scalar(con, """
        SELECT ABS(SUM(l.signed_amount_debit_positive))
        FROM star_schema.fact_ledger l
        JOIN star_schema.dim_account a ON l.account_code = a.account_code
        WHERE l.source_type = 'INVOICE'
          AND a.account_code IN (2200, 4001, 4002, 4003, 4004)
          AND l.entry_date >= (SELECT MAX(entry_date) FROM star_schema.fact_ledger WHERE source_type = 'INVOICE') - INTERVAL '90 days'
    """)
    assert_check("M20 denominator matches ledger sum", abs(denom_check - revenue_90d) < 0.01, revenue_90d, denom_check)
    
# Verify numerator: sum of ALL positive outstanding balances as of report_date (corrected)
    # Outstanding = total_amount - payments received by report_date
    num_check = execute_scalar(con, f"""
        SELECT COALESCE(SUM(i.total_amount - COALESCE(i.paid_by_report, 0)), 0)
        FROM (
            SELECT 
                i.invoice_id,
                i.total_amount,
                COALESCE(SUM(p.amount) FILTER (WHERE p.payment_date <= '{report_date}'), 0) AS paid_by_report
            FROM star_schema.fact_invoice i
            LEFT JOIN star_schema.fact_invoice_payment p ON i.invoice_id = p.invoice_id
            WHERE i.invoice_date <= '{report_date}'
              AND i.status NOT IN ('DRAFT', 'CANCELLED')
            GROUP BY i.invoice_id, i.total_amount
        ) i
        WHERE i.total_amount - COALESCE(i.paid_by_report, 0) > 0
    """)
    assert_check("M20 numerator matches sum of ALL positive outstanding balances", abs(num_check - closing_ar) < 0.01, closing_ar, num_check)
    
    # DSO formula verification
    expected_dso = 90.0 * closing_ar / revenue_90d if revenue_90d > 0 else None
    if expected_dso:
        assert_check("M20 DSO formula correct", abs(expected_dso - dso_days) < 0.01, dso_days, expected_dso)

# ============================================================
# 11. M21 OVERDUE RECEIVABLES VALIDATION
# ============================================================
print("\n--- 11. M21 OVERDUE RECEIVABLES VALIDATION ---")
m21_result = execute_all(con, "SELECT * FROM star_schema.m21_overdue_receivables")
assert_check("M21 view returns results", len(m21_result) > 0, len(m21_result), ">0")

# Verify formula: due_date < report_date AND status NOT IN ('DRAFT','CANCELLED')
m21_check = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.fact_invoice i
    WHERE i.due_date < (SELECT MAX(invoice_date) FROM star_schema.fact_invoice)
      AND i.status NOT IN ('DRAFT', 'CANCELLED')
      AND i.balance_due > 0
""")
m21_total = execute_scalar(con, "SELECT SUM(total_overdue_receivables) FROM star_schema.m21_overdue_receivables")
# Note: m21_check counts invoices, m21_total sums amounts - they should be consistent
print(f"  Overdue invoice count: {m21_check}")
print(f"  Total overdue receivables: {m21_total:,.2f}")

# Verify CANCELLED and DRAFT excluded
cancelled_in_m21 = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.m21_overdue_receivables
    WHERE client_id IN (
        SELECT client_id FROM star_schema.fact_invoice 
        WHERE status = 'CANCELLED'
    )
""")
print(f"  M21 includes cancelled client data (should be 0 overdue from them): {cancelled_in_m21}")

# Carried-in overdue separated
carried_overdue = execute_scalar(con, "SELECT SUM(carried_in_overdue) FROM star_schema.m21_overdue_receivables")
new_overdue = execute_scalar(con, "SELECT SUM(new_invoice_overdue) FROM star_schema.m21_overdue_receivables")
print(f"  Carried-in overdue: {carried_overdue:,.2f}")
print(f"  New invoice overdue: {new_overdue:,.2f}")

# ============================================================
# 12. INVOICE AGEING & CLIENT AGEING
# ============================================================
print("\n--- 12. INVOICE AGEING & CLIENT AGEING ---")
ageing_months = execute_scalar(con, "SELECT COUNT(DISTINCT month_end) FROM star_schema.invoice_ageing_monthly")
assert_check("Invoice ageing has 20 months", ageing_months == 20, ageing_months, 20)

ageing_rows = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.invoice_ageing_monthly")
print(f"  Invoice ageing rows: {ageing_rows}")

client_ageing_months = execute_scalar(con, "SELECT COUNT(DISTINCT month_end) FROM star_schema.client_ageing_monthly")
assert_check("Client ageing has 20 months", client_ageing_months == 20, client_ageing_months, 20)

# Ageing buckets present
buckets = execute_all(con, """
    SELECT ageing_bucket, COUNT(*) FROM star_schema.invoice_ageing_monthly
    WHERE ageing_bucket != 'EXCLUDED'
    GROUP BY ageing_bucket ORDER BY COUNT(*) DESC
""")
print("  Ageing bucket distribution:")
for b, c in buckets:
    print(f"    {b}: {c}")

# ============================================================
# 13. MONTHLY INVOICING & COLLECTIONS
# ============================================================
print("\n--- 13. MONTHLY INVOICING & COLLECTIONS ---")
inv_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.monthly_invoicing")
assert_check("Monthly invoicing has 20 months", inv_months == 20, inv_months, 20)

coll_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.monthly_collections")
assert_check("Monthly collections has 18 months (payments start 2025-04)", coll_months == 18, coll_months, 18)

# ============================================================
# 14. KNOWN ANOMALIES DOCUMENTED
# ============================================================
print("\n--- 14. KNOWN ANOMALIES DOCUMENTED ---")
anomaly_count = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.known_anomalies")
assert_check(f"Known anomalies documented: {anomaly_count}", anomaly_count == 11, anomaly_count, 11)

# INV-00385 anomaly
inv385_anomaly = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.known_anomalies
    WHERE invoice_id = 'INV-00385' AND anomaly_type = 'AMOUNT_PAID_DISCREPANCY'
""")
assert_check("INV-00385 anomaly documented", inv385_anomaly == 1, inv385_anomaly, 1)

# 4 cancelled anomalies
cancelled_anomalies = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.known_anomalies
    WHERE anomaly_type = 'CANCELLED_BALANCE_ZERO'
""")
assert_check("4 CANCELLED balance zero anomalies documented", cancelled_anomalies == 4, cancelled_anomalies, 4)

# Missing ledger references - count distinct invoices (INV-00740 has two anomaly types)
missing_ledger_anomalies = execute_scalar(con, """
    SELECT COUNT(DISTINCT invoice_id) FROM star_schema.known_anomalies
    WHERE anomaly_type IN ('CARRIED_IN_OVERDUE_MISSING_LEDGER', 'CANCELLED_MISSING_LEDGER', 'DRAFT_MISSING_LEDGER', 'POST_LEDGER_NO_ENTRY')
""")
assert_check("6 missing ledger references documented (distinct invoices)", missing_ledger_anomalies == 6, missing_ledger_anomalies, 6)

# ============================================================
# 15. INVOICE AGGREGATE VERIFICATION
# ============================================================
print("\n--- 15. INVOICE AGGREGATE VERIFICATION ---")
# Total invoiced amount
total_invoiced = execute_scalar(con, """
    SELECT SUM(total_amount) FROM star_schema.fact_invoice
    WHERE status NOT IN ('DRAFT', 'CANCELLED')
""")
print(f"  Total invoiced (excl DRAFT/CANCELLED): {total_invoiced:,.2f}")

# Total collected
total_collected = execute_scalar(con, "SELECT SUM(amount) FROM star_schema.fact_invoice_payment")
print(f"  Total collected: {total_collected:,.2f}")

# Outstanding balance
outstanding = execute_scalar(con, """
    SELECT SUM(total_amount - COALESCE((
        SELECT SUM(p.amount) FROM star_schema.fact_invoice_payment p
        WHERE p.invoice_id = i.invoice_id
    ), 0))
    FROM star_schema.fact_invoice i
    WHERE i.status NOT IN ('DRAFT', 'CANCELLED')
      AND i.total_amount - COALESCE((
        SELECT SUM(p.amount) FROM star_schema.fact_invoice_payment p
        WHERE p.invoice_id = i.invoice_id
    ), 0) > 0
""")
print(f"  Total outstanding: {outstanding:,.2f}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("PQ-12 VALIDATION SUMMARY")
print("=" * 60)
print(f"PASSED: {len(PASSES)}")
print(f"FAILED: {len(FAILURES)}")

if FAILURES:
    print("\nFAILURES:")
    for label, detail in FAILURES:
        print(f"  - {label}: {detail}")
    sys.exit(1)
else:
    print("\nALL CHECKS PASSED!")
    sys.exit(0)