import json
from pathlib import Path

import duckdb

project_root = Path(__file__).resolve().parents[1]
database_path = project_root / "pulseiq.duckdb"


def main():
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        latest_run = connection.execute("""
            SELECT run_id
            FROM dq_results
            GROUP BY run_id
            ORDER BY MAX(executed_at_utc) DESC
            LIMIT 1
        """).fetchone()

        if latest_run is None:
            raise RuntimeError("No data-quality results have been recorded yet.")

        run_id = latest_run[0]
        rows = connection.execute("""
            SELECT check_id, check_name, severity, source_table, status,
                   violation_count, details_json
            FROM dq_results
            WHERE run_id = ?
            ORDER BY check_id
        """, [run_id]).fetchall()

        print(f"DQ run ID: {run_id}")
        print(f"Recorded checks: {len(rows)}")

        for check_id, check_name, severity, source_table, status, count, details in rows:
            print(f"\n--- {check_id}: {check_name} ---")
            print(f"Table: {source_table} | Severity: {severity} | Status: {status} | Violations: {count}")
            print(json.dumps(json.loads(details), indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
