"""Load PQ-15 company scorecard views into the existing DuckDB warehouse.

Run: python PQ-15-build.py
"""
import duckdb, os, sys

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")
SQL_FILE = os.path.join(os.path.dirname(__file__), "PQ-15-scorecard_views.sql")

def main():
    con = duckdb.connect(WAREHOUSE)
    
    print("=== PQ-15 Loading ===")
    print(f"Warehouse: {WAREHOUSE}")
    
    # Load PQ-15 metric SQL views
    print("\n--- Loading PQ-15 Metric Views ---")
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
                view_name = stmt.split()[4]
                print(f"  Created: {view_name}")
            elif stmt.upper().startswith("CREATE TABLE"):
                table_name = stmt.split()[3]
                print(f"  Created table: {table_name}")
        except Exception as e:
            bad.append((i, str(e)))
            print(f"  VIEW LOAD FAILED #{i}: {e}")
            print(f"    Statement: {stmt[:200]}")
    
    if bad:
        print(f"\nFAILED VIEWS: {len(bad)}")
        for idx, err in bad:
            print(f"  #{idx}: {err}")
        sys.exit(1)
    
    print(f"\nAll {len(statements) - len(bad)} PQ-15 metric views loaded successfully.")
    
    # Verify key views
    print("\n--- Verification ---")
    checks = [
        ("star_schema.pq15_company_scorecard", 18),
        ("star_schema.pq15_kpi_targets_company", 8),
        ("star_schema.pq15_validation", 9),
        ("star_schema.pq15_company_kpi_targets", 0),
        ("star_schema.pq15_kpi_trends", 144),  # 8 KPIs * 18 months
    ]
    
    for view, expected in checks:
        try:
            actual = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            status = "OK" if actual >= expected else "LOW"
            print(f"  {view}: {actual} (expected >= {expected}) - {status}")
        except Exception as e:
            print(f"  {view}: ERROR - {e}")
    
    con.close()
    print("\nPQ-15 Load Complete.")

if __name__ == "__main__":
    main()