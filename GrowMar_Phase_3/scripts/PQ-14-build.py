"""Load PQ-14 AI Signals views into the DuckDB warehouse.

Run: python PQ-14-build.py
"""
import duckdb, os, sys

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")
SQL_FILE = os.path.join(os.path.dirname(__file__), "PQ-14-ai_views.sql")

def main():
    con = duckdb.connect(WAREHOUSE)
    
    print("=== PQ-14 Loading ===")
    print(f"Warehouse: {WAREHOUSE}")
    
    # Load PQ-14 AI Signals SQL views
    print("\n--- Loading PQ-14 AI Signals Views ---")
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
    
    print(f"\nAll {len(statements) - len(bad)} PQ-14 AI Signals views loaded successfully.")
    
    # Verify key views
    print("\n--- Verification ---")
    checks = [
        ("star_schema.pq14_anomalies_by_risk", 10),
        ("star_schema.pq14_anomaly_detail", 100),
        ("star_schema.pq14_future_forecasts", 10),
        ("star_schema.pq14_forecast_backtest_headcount", 0),
        ("star_schema.pq14_forecast_backtest_attrition", 0),
        ("star_schema.pq14_forecast_error", 0),
        ("star_schema.pq14_attrition_risk_summary", 10),
        ("star_schema.pq14_attrition_risk_detail", 100),
        ("star_schema.pq14_validation", 10),
    ]
    
    for view, expected in checks:
        try:
            actual = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            status = "OK" if actual >= expected else "LOW"
            print(f"  {view}: {actual} (expected ~{expected}) - {status}")
        except Exception as e:
            print(f"  {view}: ERROR - {e}")
    
    con.close()
    print("\nPQ-14 Load Complete.")

if __name__ == "__main__":
    main()