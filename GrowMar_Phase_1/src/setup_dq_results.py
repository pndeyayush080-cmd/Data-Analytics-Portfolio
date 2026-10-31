from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "pulseiq.duckdb"

connection = duckdb.connect(str(DATABASE_PATH))

try:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dq_results (
            run_id VARCHAR NOT NULL,
            check_id VARCHAR NOT NULL,
            check_name VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            source_table VARCHAR,
            status VARCHAR NOT NULL,
            violation_count BIGINT NOT NULL,
            details_json VARCHAR,
            executed_at_utc TIMESTAMP NOT NULL,
            PRIMARY KEY (run_id, check_id)
        )
    """)
    connection.execute(
        "ALTER TABLE dq_results ADD COLUMN IF NOT EXISTS source_table VARCHAR"
    )

    print("DQ results table is ready.")
    print(
        connection.execute("""
            DESCRIBE dq_results
        """).fetchdf().to_string(index=False)
    )
finally:
    connection.close()
