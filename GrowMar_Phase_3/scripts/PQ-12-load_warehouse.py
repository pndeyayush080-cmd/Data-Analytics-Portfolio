"""Load PQ-12 source CSVs into the existing PQ-11 DuckDB warehouse.

Adds invoice and payment facts to the existing star_schema.
Reuses PQ-11 dimensions and ledger.

Run: python PQ-12-load_warehouse.py
"""
import duckdb, glob, os, sys

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")
STAR_SCHEMA = "star_schema"

# PQ-12 specific tables
PQ12_DIMS = [
    ("dim_client", "dim_client.csv"),
]
PQ12_FACTS = [
    ("fact_invoice", "fact_invoice.csv"),
    ("fact_invoice_payment", "fact_invoice_payment.csv"),
]

# PQ-11 dependencies that PQ-12 views depend on
PQ11_DEPS_DIMS = [
    ("dim_date", "dim_date.csv"),
    ("dim_account", "dim_account.csv"),
]
PQ11_DEPS_FACTS = [
    ("fact_ledger", "fact_ledger.csv"),
]

# PQ-12 metric views
METRIC_SQL = os.path.join(os.path.dirname(__file__), "PQ-12-pl_views.sql")
SHEET_PREFIX = f"{STAR_SCHEMA}."

def main():
    # Connect to existing PQ-11 warehouse
    con = duckdb.connect(WAREHOUSE)
    
    # Create schemas if not exist (needed for fresh warehouse)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS star_schema")
    
    print("=== PQ-12 Loading ===")
    print(f"Warehouse: {WAREHOUSE}")
    
    # Load PQ-11 dependency dimensions (needed by PQ-12 views)
    print("\n--- Loading PQ-11 Dependency Dimensions ---")
    for tbl, src in PQ11_DEPS_DIMS:
        fname = os.path.join(os.path.dirname(__file__), "..", "03_Data", "csv", src)
        con.execute(f"CREATE OR REPLACE TABLE raw.{tbl} AS SELECT * FROM read_csv_auto('{fname}', header=true)")
        cnt = con.execute(f"SELECT COUNT(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl:<32}{cnt:>8}")
    
    # Load PQ-11 dependency facts (needed by PQ-12 views)
    print("\n--- Loading PQ-11 Dependency Facts ---")
    for tbl, src in PQ11_DEPS_FACTS:
        fname = os.path.join(os.path.dirname(__file__), "..", "03_Data", "csv", src)
        con.execute(f"CREATE OR REPLACE TABLE raw.{tbl} AS SELECT * FROM read_csv_auto('{fname}', header=true)")
        cnt = con.execute(f"SELECT COUNT(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl:<32}{cnt:>8}")
    
    # Load PQ-12 dimension CSVs
    print("\n--- Loading PQ-12 Dimensions ---")
    for tbl, src in PQ12_DIMS:
        fname = os.path.join(os.path.dirname(__file__), "..", "03_Data", "csv", src)
        con.execute(f"CREATE OR REPLACE TABLE raw.{tbl} AS SELECT * FROM read_csv_auto('{fname}', header=true)")
        cnt = con.execute(f"SELECT COUNT(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl:<32}{cnt:>8}")
    
    # Load PQ-12 fact CSVs
    print("\n--- Loading PQ-12 Facts ---")
    for tbl, src in PQ12_FACTS:
        fname = os.path.join(os.path.dirname(__file__), "..", "03_Data", "csv", src)
        con.execute(f"CREATE OR REPLACE TABLE raw.{tbl} AS SELECT * FROM read_csv_auto('{fname}', header=true)")
        cnt = con.execute(f"SELECT COUNT(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl:<32}{cnt:>8}")
    
    # Create star_schema views for all dimensions and facts
    print("\n--- Creating star_schema views ---")
    for tbl, src in PQ11_DEPS_DIMS + PQ11_DEPS_FACTS + PQ12_DIMS + PQ12_FACTS:
        con.execute(f"CREATE OR REPLACE VIEW {SHEET_PREFIX}{tbl} AS SELECT * FROM raw.{tbl}")
        cnt = con.execute(f"SELECT COUNT(*) FROM {SHEET_PREFIX}{tbl}").fetchone()[0]
        print(f"  {SHEET_PREFIX}{tbl:<32}{cnt:>8}")
    
    # Load PQ-12 metric SQL views
    print("\n--- Loading PQ-12 Metric Views ---")
    with open(METRIC_SQL, encoding="utf-8") as fh:
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
            # Extract view name for logging
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
    
    print(f"\nAll {len(statements) - len(bad)} PQ-12 metric views loaded successfully.")
    
    # Verify key counts
    print("\n--- Verification ---")
    checks = [
        ("star_schema.dim_client", 28),
        ("star_schema.fact_invoice", 743),
        ("star_schema.fact_invoice_payment", 709),
    ]
    for view, expected in checks:
        actual = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        status = "OK" if actual == expected else "MISMATCH"
        print(f"  {view}: {actual} (expected {expected}) - {status}")
    
    con.close()
    print("\nPQ-12 Load Complete.")

if __name__ == "__main__":
    main()