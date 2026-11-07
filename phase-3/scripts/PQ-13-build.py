"""Load PQ-13 cross-department views into the existing DuckDB warehouse.

Run: python PQ-13-build.py
"""
import duckdb, os, sys

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")
SQL_FILE = os.path.join(os.path.dirname(__file__), "PQ-13-cross_department_views.sql")

def main():
    con = duckdb.connect(r'C:\Users\Ayush Pandey\OneDrive\Documents\Data-Analytics-Portfolio\GrowMar_Phase_3\data\warehouse\pulseiq_clean.duckdb')
    
    print("=== PQ-13 Loading ===")
    print(f"Warehouse: C:\\Users\\Ayush Pandey\\OneDrive\\Documents\\Data-Analytics-Portfolio\\GrowMar_Phase_3\\data\\warehouse\\pulseiq_clean.duckdb")
    
    # Load PQ-13 metric SQL views
    print("\n--- Loading PQ-13 Metric Views ---")
    with open(SQL_FILE, encoding="utf-8") as fh:
        sql_text = fh.read()
    
    # Split by semicolon, filter comments and empty
    raw_statements = sql_text.split(";")
    statements = []
    for s in raw_statements:
        s = s.strip()
        if not s:
            continue
        code_lines = [line for line in s.split('\n') if not line.strip().startswith('--')]
        if not code_lines:
            continue
        joined = '\n'.join(code_lines).strip()
        if joined.upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE", "SELECT", "WITH")):
            statements.append(joined)
    
    bad = []
    for i, stmt in enumerate(statements):
        try:
            con.execute(stmt)
            if stmt.upper().startswith("CREATE OR REPLACE VIEW"):
                view_name = stmt.split()[4]  # CREATE OR REPLACE VIEW star_schema.view_name ...
                print(f"  Created: {view_name}")
        except Exception as e:
            bad.append((i, str(e)))
            print(f"  VIEW LOAD FAILED #{i}: {e}")
            print(f"    Statement: {stmt[:200]}")
    
    if bad:
        print(f"\nFAILED VIEWS: {len(bad)}")
        for idx, err in bad:
            print(f"  #{idx}: {err}")
        sys.exit(1)
    
    print(f"\nAll {len(statements) - len(bad)} PQ-13 metric views loaded successfully.")
    
    # Verify key views
    print("\n--- Verification ---")
    checks = [
        ("star_schema.dept_month_spine", 180),  # ~15 departments * 12 months = ~180
        ("star_schema.dept_month_combined", 180),
        ("star_schema.dept_month_headcount", 180),
        ("star_schema.dept_month_payroll", 180),
        ("star_schema.dept_month_attendance", 180),
        ("star_schema.dept_month_leave", 180),
        ("star_schema.dept_month_combined", 180),
        ("star_schema.dept_comparison", 180),
        ("star_schema.overtime_attrition_correlation", 2),
        ("star_schema.pq13_validation", 10),
        ("star_schema.pq13_reference_reconciliation", 198),  # 198 rows in reference
        ("star_schema.dept_comparison", 180),
        ("star_schema.overtime_attrition_correlation", 2),
        ("star_schema.pq13_validation", 10),
    ]
    
    for view, expected in checks:
        try:
            actual = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            status = "OK" if actual >= expected * 0.8 else "LOW"
            print(f"  {view}: {actual} (expected ~{expected}) - {status}")
        except Exception as e:
            print(f"  {view}: ERROR - {e}")
    
    con.close()
    print("\nPQ-13 Load Complete.")

if __name__ == "__main__":
    main()