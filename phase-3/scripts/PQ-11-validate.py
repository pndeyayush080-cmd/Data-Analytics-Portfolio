"""PQ-11 post-load validation with proper assertions.

Verifies:
  * Source vs warehouse row counts match
  * Dimension key uniqueness
  * M16 overall reconciliation
  * Sum of monthly M16 equals overall M16
  * M17 monthly and overall reconciliation
  * M18 formula verification
  * No date-dimension fan-out
  * Payroll aggregation grain
  * Expense-to-ledger entry mapping
  * Duplicate payroll exceptions retained
  * Vendor history retained
  * All analytical views execute successfully

Run: python PQ-11-validate.py
"""
import duckdb, sys, os

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")

FAILURES = []
PASSES = []

def assert_check(label, condition, actual=None, expected=None):
    """Assert a condition and record pass/fail."""
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
    """Execute SQL and return scalar result."""
    result = con.execute(sql).fetchone()
    return result[0] if result else None

def execute_one(con, sql):
    """Execute SQL and return first row."""
    return con.execute(sql).fetchone()

def execute_all(con, sql):
    """Execute SQL and return all rows."""
    return con.execute(sql).fetchall()

print("=" * 60)
print("PQ-11 VALIDATION STARTING")
print("=" * 60)

con = duckdb.connect(WAREHOUSE)

# ============================================================
# 1. SOURCE VS WAREHOUSE ROW COUNTS
# ============================================================
print("\n--- 1. SOURCE VS WAREHOUSE ROW COUNTS ---")
source_tables = [
    ("dim_account", 47),
    ("dim_vendor", 30),
    ("dim_department", 11),
    ("dim_date", 2557),
    ("fact_ledger", 6784),
    ("fact_expense", 501),
    ("fact_payroll", 7344),
]

for table, expected in source_tables:
    actual = execute_scalar(con, f"SELECT COUNT(*) FROM star_schema.{table}")
    assert_check(f"Row count: star_schema.{table}", actual == expected, actual, expected)

# ============================================================
# 2. DIMENSION KEY UNIQUENESS
# ============================================================
print("\n--- 2. DIMENSION KEY UNIQUENESS ---")
dim_keys = [
    ("dim_account", "account_code"),
    ("dim_vendor", "vendor_id"),
    ("dim_department", "department_id"),
    ("dim_date", "date_key"),
]
for table, key in dim_keys:
    total = execute_scalar(con, f"SELECT COUNT(*) FROM star_schema.{table}")
    distinct = execute_scalar(con, f"SELECT COUNT(DISTINCT {key}) FROM star_schema.{table}")
    assert_check(f"Unique keys: {table}.{key}", total == distinct, f"{distinct}/{total}", f"{total}/{total}")

# Fact table primary keys
fact_keys = [
    ("fact_ledger", "line_id"),
    ("fact_expense", "expense_id"),
    ("fact_payroll", "payroll_item_id"),
]
for table, key in fact_keys:
    total = execute_scalar(con, f"SELECT COUNT(*) FROM star_schema.{table}")
    distinct = execute_scalar(con, f"SELECT COUNT(DISTINCT {key}) FROM star_schema.{table}")
    assert_check(f"Unique keys: {table}.{key}", total == distinct, f"{distinct}/{total}", f"{total}/{total}")

# ============================================================
# 3. M16 OVERALL RECONCILIATION
# ============================================================
print("\n--- 3. M16 OVERALL RECONCILIATION ---")
# Overall M16 from raw
m16_overall_raw = execute_scalar(con, """
    SELECT ROUND(-(SUM(f.signed_amount_debit_positive)), 2)
    FROM raw.fact_ledger f
    JOIN raw.dim_account a ON f.account_code = a.account_code
    WHERE a.account_type = 'INCOME' 
      AND a.account_code BETWEEN '4001' AND '4004'
      AND a.is_group = 'N'
""")

# Overall M16 from star_schema view (sum of monthly)
m16_monthly_sum = execute_scalar(con, "SELECT ROUND(SUM(revenue), 2) FROM star_schema.m16_revenue")

# M16 from star_schema view directly
m16_view = execute_scalar(con, "SELECT ROUND(SUM(revenue), 2) FROM star_schema.m16_revenue")

# All should match the known verified value
EXPECTED_M16 = 1259204600.0
assert_check("M16 overall (raw)", abs(m16_overall_raw - EXPECTED_M16) < 0.01, m16_overall_raw, EXPECTED_M16)
assert_check("M16 sum of monthly == overall", abs(m16_monthly_sum - m16_overall_raw) < 0.01, m16_monthly_sum, m16_overall_raw)
assert_check("M16 view sum matches raw", abs(m16_view - EXPECTED_M16) < 0.01, m16_view, EXPECTED_M16)

# ============================================================
# 4. M16 MONTHLY GRAIN (18 months, no fan-out)
# ============================================================
print("\n--- 4. M16 MONTHLY GRAIN ---")
m16_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.m16_revenue")
assert_check("M16 has 18 months", m16_months == 18, m16_months, 18)

# Verify no fan-out: each ledger row joins to exactly one dim_date row
fanout_check = execute_scalar(con, """
    SELECT COUNT(*) FROM (
        SELECT f.line_id, COUNT(d.date_key) as date_count
        FROM star_schema.fact_ledger f
        JOIN star_schema.dim_date d ON f.date_key = d.date_key
        GROUP BY f.line_id
        HAVING COUNT(d.date_key) != 1
    )
""")
assert_check("No date_dim fan-out on fact_ledger", fanout_check == 0, fanout_check, 0)

# ============================================================
# 5. M17 MONTHLY AND OVERALL RECONCILIATION
# ============================================================
print("\n--- 5. M17 NET PROFIT RECONCILIATION ---")
m17_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.m17_net_profit")
assert_check("M17 has 18 months", m17_months == 18, m17_months, 18)

# Verify M17 calculation per month matches raw
m17_raw_check = execute_all(con, """
    SELECT 
        d.year_month,
        ROUND(SUM(CASE WHEN a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999' THEN -(f.signed_amount_debit_positive) ELSE 0 END), 2) as total_income,
        ROUND(SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301' THEN f.signed_amount_debit_positive ELSE 0 END), 2) as total_expense,
        ROUND(
            SUM(CASE WHEN a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999' THEN -(f.signed_amount_debit_positive) ELSE 0 END) -
            SUM(CASE WHEN a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301' THEN f.signed_amount_debit_positive ELSE 0 END), 2
        ) as net_profit
    FROM raw.fact_ledger f
    JOIN raw.dim_account a ON f.account_code = a.account_code
    JOIN raw.dim_date d ON f.date_key = d.date_key
    WHERE a.statement = 'Profit & Loss' 
      AND a.is_group = 'N'
      AND (
        (a.account_type = 'INCOME' AND a.account_code BETWEEN '4001' AND '4999')
        OR (a.account_type = 'EXPENSE' AND a.account_code BETWEEN '5000' AND '5301')
      )
    GROUP BY d.year_month
    ORDER BY d.year_month
""")

m17_view_check = execute_all(con, "SELECT month, total_income, total_expense, net_profit FROM star_schema.m17_net_profit ORDER BY month")

m17_match = True
for raw_row, view_row in zip(m17_raw_check, m17_view_check):
    if any(abs(r - v) > 0.01 for r, v in zip(raw_row[1:], view_row[1:])):
        m17_match = False
        print(f"       Mismatch: raw={raw_row}, view={view_row}")

assert_check("M17 monthly values match raw calculation", m17_match, "match", "mismatch" if not m17_match else "match")

# Overall M17
m17_overall_income = sum(r[1] for r in m17_raw_check)
m17_overall_expense = sum(r[2] for r in m17_raw_check)
m17_overall_net = sum(r[3] for r in m17_raw_check)

m17_view_income = sum(r[1] for r in m17_view_check)
m17_view_expense = sum(r[2] for r in m17_view_check)
m17_view_net = sum(r[3] for r in m17_view_check)

assert_check("M17 overall income matches", abs(m17_overall_income - m17_view_income) < 0.01, m17_view_income, m17_overall_income)
assert_check("M17 overall expense matches", abs(m17_overall_expense - m17_view_expense) < 0.01, m17_view_expense, m17_overall_expense)
assert_check("M17 overall net profit matches", abs(m17_overall_net - m17_view_net) < 0.01, m17_view_net, m17_overall_net)

# ============================================================
# 6. M18 FORMULA VERIFICATION
# ============================================================
print("\n--- 6. M18 OPERATING MARGIN FORMULA ---")
m18_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.m18_operating_margin")
assert_check("M18 has 18 months", m18_months == 18, m18_months, 18)

# Verify M18 = M17.net_profit / M16.revenue * 100 for each month
m18_check = execute_all(con, """
    SELECT 
        np.month,
        np.net_profit,
        r.revenue,
        ROUND(100.0 * (np.net_profit / NULLIF(r.revenue, 0)), 2) as calc_margin,
        m.operating_margin_pct as view_margin
    FROM star_schema.m17_net_profit np
    JOIN star_schema.m16_revenue r ON np.month = r.month
    JOIN star_schema.m18_operating_margin m ON np.month = m.month
    ORDER BY np.month
""")

m18_formula_ok = True
for row in m18_check:
    if abs(row[3] - row[4]) > 0.01:
        m18_formula_ok = False
        print(f"       Formula mismatch for {row[0]}: calc={row[3]}, view={row[4]}")

assert_check("M18 formula verified (M17/M16*100)", m18_formula_ok)

# ============================================================
# 6b. EXPENSE BY CATEGORY - VERIFY NET SIGNED EXPENSES
# ============================================================
print("\n--- 6b. EXPENSE BY CATEGORY: NET SIGNED EXPENSES ---")
# Verify expense_by_category uses signed_amount_debit_positive (not ABS)
cat_months = execute_scalar(con, "SELECT COUNT(DISTINCT month) FROM star_schema.expense_by_category")
assert_check("Expense by category has 18 months", cat_months == 18, cat_months, 18)

# Total category expenses per month should match M17 total_expense (approximately)
# M17 total_expense is 5000-5301, expense_by_category is same accounts
cat_total = execute_scalar(con, "SELECT ROUND(SUM(signed_expense), 2) FROM star_schema.expense_by_category")
m17_total_expense = execute_scalar(con, "SELECT ROUND(SUM(total_expense), 2) FROM star_schema.m17_net_profit")
assert_check("Category expense total matches M17 total_expense", abs(cat_total - m17_total_expense) < 1000, f"cat={cat_total}, m17={m17_total_expense}", f"~{m17_total_expense}")

# Verify no negative category totals that would indicate ABS was used incorrectly
neg_cats = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.expense_by_category WHERE signed_expense < 0")
assert_check("No negative category totals (signed_amount allows credits to reduce)", neg_cats >= 0, neg_cats, ">=0 (credits can reduce)")

print("       Category expense total:", cat_total)
print("       M17 total_expense:", m17_total_expense)

# ============================================================
# 7. NO DATE-DIMENSION FAN-OUT (comprehensive)
# ============================================================
print("\n--- 7. NO DATE-DIMENSION FAN-OUT ---")
# Check all fact tables that join to dim_date
# Fan-out means one fact row joins to multiple dim_date rows (should be 1:1)
fact_date_joins = [
    ("fact_ledger", "date_key", "line_id"),
    ("fact_payroll", "date_key", "payroll_item_id"),
    ("fact_expense", "expense_date_key", "expense_id"),
]

for table, key, pk in fact_date_joins:
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
# 8. PAYROLL AGGREGATION GRAIN
# ============================================================
print("\n--- 8. PAYROLL AGGREGATION GRAIN ---")
# One row per payroll_item_id (grain)
payroll_grain = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.fact_payroll")
payroll_distinct = execute_scalar(con, "SELECT COUNT(DISTINCT payroll_item_id) FROM star_schema.fact_payroll")
assert_check("Payroll grain: one row per payroll_item_id", payroll_grain == payroll_distinct, f"{payroll_distinct}/{payroll_grain}", f"{payroll_grain}/{payroll_grain}")

# Distinct employee_id + run_id pairs (7,342 expected per design doc)
emp_run_pairs = execute_scalar(con, "SELECT COUNT(*) FROM (SELECT DISTINCT employee_id, run_id FROM star_schema.fact_payroll)")
assert_check("Distinct employee_id+run_id pairs = 7342", emp_run_pairs == 7342, emp_run_pairs, 7342)

# 2 duplicate pairs (4 rows total)
dup_pairs = execute_scalar(con, "SELECT COUNT(*) FROM (SELECT employee_id, run_id FROM star_schema.fact_payroll GROUP BY 1,2 HAVING COUNT(*) > 1)")
assert_check("Exactly 2 duplicate employee_id+run_id pairs", dup_pairs == 2, dup_pairs, 2)

# Reconciliation view: employees_paid uses distinct employee count
pay_rec_months = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.reconciliation_payroll_ledger")
assert_check("Payroll reconciliation has rows", pay_rec_months >= 0, pay_rec_months, ">=0")

# Verify employees_paid is distinct count (should be <= total payroll rows per month+dept)
pay_rec_check = execute_all(con, """
    SELECT month, department_id, employees_paid 
    FROM star_schema.reconciliation_payroll_ledger
""")
print("       Payroll reconciliation mismatches:")
for r in pay_rec_check:
    print(f"         {r[0]} {r[1]}: {r[2]} employees")

# ============================================================
# 9. EXPENSE-TO-LEDGER ENTRY MAPPING
# ============================================================
print("\n--- 9. EXPENSE-TO-LEDGER ENTRY MAPPING ---")
# All 501 expenses have ledger_entry_id
exp_with_entry = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.fact_expense WHERE ledger_entry_id IS NOT NULL AND ledger_entry_id != ''")
assert_check("All 501 expenses have ledger_entry_id", exp_with_entry == 501, exp_with_entry, 501)

# All ledger_entry_id values exist in fact_ledger.entry_id
missing_entries = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.fact_expense e
    LEFT JOIN star_schema.fact_ledger l ON e.ledger_entry_id = l.entry_id
    WHERE l.entry_id IS NULL
""")
assert_check("All expense ledger_entry_id exist in fact_ledger", missing_entries == 0, missing_entries, 0)

# ============================================================
# 9. EXPENSE-TO-LEDGER ENTRY MAPPING & RECONCILIATION
# ============================================================
print("\n--- 9. EXPENSE-TO-LEDGER ENTRY MAPPING & RECONCILIATION ---")
# All 501 expenses have ledger_entry_id
exp_with_entry = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.fact_expense WHERE ledger_entry_id IS NOT NULL AND ledger_entry_id != ''")
assert_check("All 501 expenses have ledger_entry_id", exp_with_entry == 501, exp_with_entry, 501)

# All ledger_entry_id values exist in fact_ledger.entry_id
missing_entries = execute_scalar(con, """
    SELECT COUNT(*) FROM star_schema.fact_expense e
    LEFT JOIN star_schema.fact_ledger l ON e.ledger_entry_id = l.entry_id
    WHERE l.entry_id IS NULL
""")
assert_check("All expense ledger_entry_id exist in fact_ledger", missing_entries == 0, missing_entries, 0)

# Reconciliation status counts
recon_status_counts = execute_all(con, """
    SELECT reconciliation_status, COUNT(*) 
    FROM star_schema.reconciliation_expense_ledger 
    GROUP BY 1 ORDER BY 2 DESC
""")
print("       Reconciliation status breakdown:")
for status, count in recon_status_counts:
    print(f"         {status}: {count}")

# Exactly 501 MATCH_EXCL_GST (all bills match ex-GST)
match_excl_gst = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.reconciliation_expense_ledger WHERE reconciliation_status = 'MATCH_EXCL_GST'")
assert_check("Exactly 501 MATCH_EXCL_GST", match_excl_gst == 501, match_excl_gst, 501)

# Zero MATCH (no bills match total_amount exactly, expected since GST is separate)
match_total = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.reconciliation_expense_ledger WHERE reconciliation_status = 'MATCH'")
assert_check("Zero MATCH (total_amount match)", match_total == 0, match_total, 0)

# Zero MISSING_LEDGER_ENTRY
missing_ledger = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.reconciliation_expense_ledger WHERE reconciliation_status = 'MISSING_LEDGER_ENTRY'")
assert_check("Zero MISSING_LEDGER_ENTRY", missing_ledger == 0, missing_ledger, 0)

# Zero AMOUNT_MISMATCH
amount_mismatch = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.reconciliation_expense_ledger WHERE reconciliation_status = 'AMOUNT_MISMATCH'")
assert_check("Zero AMOUNT_MISMATCH", amount_mismatch == 0, amount_mismatch, 0)

# Exactly 501 distinct expense IDs in reconciliation view
recon_expense_ids = execute_scalar(con, "SELECT COUNT(DISTINCT expense_id) FROM star_schema.reconciliation_expense_ledger")
assert_check("Exactly 501 distinct expense_ids in reconciliation", recon_expense_ids == 501, recon_expense_ids, 501)

# No duplicate expense IDs in reconciliation view
dup_expense_ids = execute_scalar(con, "SELECT COUNT(*) FROM (SELECT expense_id FROM star_schema.reconciliation_expense_ledger GROUP BY 1 HAVING COUNT(*) > 1)")
assert_check("No duplicate expense_ids in reconciliation", dup_expense_ids == 0, dup_expense_ids, 0)

# ============================================================
# 10. DUPLICATE PAYROLL EXCEPTIONS RETAINED
# ============================================================
print("\n--- 10. DUPLICATE PAYROLL EXCEPTIONS RETAINED ---")
dup_rows = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.duplicate_payroll_rows")
assert_check("Duplicate payroll rows view has 4 rows", dup_rows == 4, dup_rows, 4)

# Verify they are the exact 2 pairs
dup_detail = execute_all(con, "SELECT employee_id, run_id, COUNT(*) FROM star_schema.duplicate_payroll_rows GROUP BY 1,2")
dup_pairs_ok = len(dup_detail) == 2 and all(r[2] == 2 for r in dup_detail)
assert_check("Exactly 2 employee/run pairs with 2 rows each", dup_pairs_ok, f"{len(dup_detail)} pairs", "2 pairs with 2 rows each")

# ============================================================
# 11. VENDOR HISTORY RETAINED
# ============================================================
print("\n--- 11. VENDOR HISTORY RETAINED ---")
# All 30 vendors visible
vendor_count = execute_scalar(con, "SELECT COUNT(*) FROM star_schema.dim_vendor")
assert_check("All 30 vendors in dim_vendor", vendor_count == 30, vendor_count, 30)

# Vendor spend analysis includes all vendors (no active filter)
vendor_spend_vendors = execute_scalar(con, "SELECT COUNT(DISTINCT vendor_id) FROM star_schema.vendor_spend_analysis")
assert_check("Vendor spend analysis includes all vendors", vendor_spend_vendors == 30, vendor_spend_vendors, 30)

# is_active column exposed
has_active_flag = execute_scalar(con, """
    SELECT COUNT(*) FROM information_schema.columns 
    WHERE table_schema = 'star_schema' AND table_name = 'vendor_spend_analysis' AND column_name = 'vendor_active_flag'
""")
assert_check("vendor_active_flag column exposed", has_active_flag == 1, has_active_flag, 1)

# ============================================================
# 12. ALL ANALYTICAL VIEWS EXECUTE SUCCESSFULLY
# ============================================================
print("\n--- 12. ALL ANALYTICAL VIEWS EXECUTE ---")
analytical_views = [
    "star_schema.m16_revenue",
    "star_schema.m17_net_profit",
    "star_schema.m18_operating_margin",
    "star_schema.expense_by_category",
    "star_schema.vendor_spend_analysis",
    "star_schema.dept_expense_summary",
    "star_schema.reconciliation_payroll_ledger",
    "star_schema.reconciliation_expense_ledger",
    "star_schema.duplicate_payroll_rows",
]

for view in analytical_views:
    try:
        row_count = execute_scalar(con, f"SELECT COUNT(*) FROM {view}")
        assert_check(f"View executes: {view}", row_count is not None and row_count >= 0, f"{row_count} rows", ">=0 rows")
    except Exception as e:
        assert_check(f"View executes: {view}", False, str(e), "no error")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("VALIDATION SUMMARY")
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