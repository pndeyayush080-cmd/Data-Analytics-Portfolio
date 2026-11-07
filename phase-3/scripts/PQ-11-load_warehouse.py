"""Load every CSV under 03_Data/csv into a local DuckDB file as schemas.

Star-schema warehouse layout:
  star_schema.dim_*       — seven dimensions + vendor
  star_schema.fact_*       — 11 fact tables
  star_schema.metric_*.sql — reusable metric views (M01 .. M28)

Run: python PQ-11-load_warehouse.py
"""
import duckdb, glob, os, sys, re

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse", "pulseiq_clean.duckdb")
RAW_SCHEMA = "raw"
STAR_SCHEMA = "star_schema"

# Dims and facts mapped to source CSV files (rows in star_schema only).
# metric_views_examples.sql already defines the M01-M28 views; we only load
# the dimension and fact tables here, then import the SQL text.
DIMS = [
    ("dim_date", "dim_date.csv"),
    ("dim_department", "dim_department.csv"),
    ("dim_account", "dim_account.csv"),
    ("dim_vendor", "dim_vendor.csv"),
    ("dim_location", "dim_location.csv"),
    ("dim_role", "dim_role.csv"),
    ("dim_team", "dim_team.csv"),
    ("dim_sprint", "dim_sprint.csv"),
    ("dim_leave_type", "dim_leave_type.csv"),
]
FACTS = [
    ("fact_attendance_monthly", "fact_attendance_monthly.csv"),
    ("fact_leave", "fact_leave.csv"),
    ("fact_headcount_monthly", "fact_headcount_monthly.csv"),
    ("fact_ledger", "fact_ledger.csv"),
    ("fact_invoice", "fact_invoice.csv"),
    ("fact_invoice_payment", "fact_invoice_payment.csv"),
    ("fact_expense", "fact_expense.csv"),
    ("fact_payroll", "fact_payroll.csv"),
    ("fact_task", "fact_task.csv"),
    ("fact_anomaly", "fact_anomaly.csv"),
    ("fact_attrition_risk", "fact_attrition_risk.csv"),
    ("fact_forecast", "fact_forecast.csv"),
]
METRIC_SQL = os.path.join(os.path.dirname(__file__), "..", "scripts", "PQ-11-pl_views.sql")
SHEET_PREFIX = f"{STAR_SCHEMA}."

def main():
    con = duckdb.connect(WAREHOUSE)
    # Bronze: raw schema from CSV sources (in same connection)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for fname in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "03_Data", "csv", "*.csv"))):
        tbl = os.path.basename(fname)[:-4]
        con.execute(f"CREATE OR REPLACE TABLE raw.{tbl} AS SELECT * FROM read_csv_auto('{fname}', header=true)")
        print(f"raw.{tbl:<32}{con.execute(f'SELECT COUNT(*) FROM raw.{tbl}').fetchone()[0]:>8}")

    # Create star_schema
    con.execute("CREATE SCHEMA IF NOT EXISTS star_schema")

    # Star schema dimensions + facts
    for tbl, src in DIMS + FACTS:
        con.execute(f"CREATE OR REPLACE VIEW {SHEET_PREFIX}{tbl} AS SELECT * FROM raw.{tbl}")
        print(f"{SHEET_PREFIX}{tbl:<32}{con.execute(f'SELECT COUNT(*) FROM {SHEET_PREFIX}{tbl}').fetchone()[0]:>8}")

    # Load metric SQL statements (split by ';') and apply each view.
    with open(METRIC_SQL, encoding="utf-8") as fh:
        sql_text = fh.read()
    
    # Split by semicolon but filter out comments and empty statements
    raw_statements = sql_text.split(";")
    statements = []
    for s in raw_statements:
        s = s.strip()
        if not s:
            continue
        # Remove comment lines
        code_lines = [line for line in s.split('\n') if not line.strip().startswith('--')]
        if not code_lines:
            continue
        # Only keep statements that start with SQL keywords
        joined = '\n'.join(code_lines).strip()
        if joined.upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE", "SELECT", "WITH")):
            statements.append(joined)
    
    bad = []
    for i, stmt in enumerate(statements):
        try:
            con.execute(stmt)
        except Exception as e:
            bad.append((i, str(e)))
            print(f"VIEW LOAD FAILED #{i}: {e}")
            print(f"  Statement: {stmt[:200]}")
    if bad:
        print("\nFAILED VIEWS:")
        for idx, err in bad:
            print(f"  #{idx}: {err}")
        sys.exit(1)
    print("\nAll metric views loaded.")
    con.close()

if __name__ == "__main__":
    main()
