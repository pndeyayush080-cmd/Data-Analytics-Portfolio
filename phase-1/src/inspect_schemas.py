
import duckdb
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
db_path = project_root / "pulseiq.duckdb"

con = duckdb.connect(str(db_path), read_only=True)

try:
    tables = con.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name
    """).fetchall()

    print("Schemas and tables:")
    for schema, table in tables:
        print(f"{schema}.{table}")

finally:
    con.close()
