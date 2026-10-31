
from pathlib import Path
import duckdb

from run_dq_gatekeeper import main as run_dq_gatekeeper

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "pulseiq.duckdb"
CSV_DIR = PROJECT_DIR / "data" / "raw" / "extracted"

if not CSV_DIR.exists():
    raise FileNotFoundError(f"CSV folder not found: {CSV_DIR}")

csv_files = sorted(CSV_DIR.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {CSV_DIR}")

con = duckdb.connect(str(DB_PATH))

try:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for csv_file in csv_files:
        table_name = csv_file.stem

        # Preserve existing tables: never replace a table automatically.
        exists = con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'raw'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]

        if exists:
            print(f"SKIPPED (table already exists): raw.{table_name}")
            continue

        # Escape single quotes in the file path for SQL.
        csv_path = str(csv_file).replace("\\", "/").replace("'", "''")

        con.execute(
            f"""
            CREATE TABLE raw."{table_name}" AS
            SELECT * FROM read_csv_auto('{csv_path}', header=true)
            """
        )

        count = con.execute(
            f'SELECT COUNT(*) FROM raw."{table_name}"'
        ).fetchone()[0]

        print(f"LOADED raw.{table_name}: {count:,} rows")

    print("\nTables currently in raw schema:")
    print(
        con.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'raw'
            ORDER BY table_name
        """).df().to_string(index=False)
    )

finally:
    con.close()

print("\nLoading completed. Source CSV files were not modified.")
print("\nRunning the data-quality gatekeeper for this load.")
run_dq_gatekeeper()
