"""Build and validate the Task 2 star-schema warehouse in DuckDB.

The raw schema is read only by convention: this program creates only the
``warehouse`` schema and a warehouse validation report.  Source employee IDs
are used solely to resolve a historical surrogate ``employee_key`` while the
warehouse is built; employee-facing fact joins use ``employee_key`` only.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "pulseiq.duckdb"
REPORT_PATH = PROJECT_ROOT / "data" / "warehouse" / "task2_validation_report.json"

# Target table name: (source select, declared primary-key columns)
TABLE_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "dim_date": ("SELECT * FROM raw.dim_date", ("date_key",)),
    "dim_department": ("SELECT * FROM raw.dim_department", ("department_id",)),
    "dim_employee": ("SELECT * FROM raw.dim_employee", ("employee_key",)),
    "dim_leave_type": ("SELECT * FROM raw.dim_leave_type", ("leave_type_code",)),
    "dim_role": ("SELECT * FROM raw.dim_role", ("role_id",)),
    "dim_sprint": ("SELECT * FROM raw.dim_sprint", ("sprint_id",)),
    "dim_team": ("SELECT * FROM raw.dim_team", ("team_id",)),
    "fact_payroll": (
        "SELECT * EXCLUDE (employee_id) FROM raw.fact_payroll",
        ("payroll_item_id",),
    ),
    "fact_attendance_monthly": (
        "SELECT * EXCLUDE (employee_id) FROM raw.fact_attendance_monthly",
        ("attendance_fact_id",),
    ),
    "fact_leave": (
        "SELECT * EXCLUDE (employee_id) FROM raw.fact_leave",
        ("leave_request_id",),
    ),
    "fact_headcount_monthly": (
        "SELECT * FROM raw.fact_headcount_monthly",
        ("date_key", "department_id"),
    ),
    "fact_ledger": ("SELECT * FROM raw.fact_ledger", ("line_id",)),
    "fact_invoice": ("SELECT * FROM raw.fact_invoice", ("invoice_id",)),
    "fact_expense": ("SELECT * FROM raw.fact_expense", ("expense_id",)),
    "fact_forecast": ("SELECT * FROM raw.fact_forecast", ("forecast_id",)),
    "fact_attrition_risk": (
        "SELECT * EXCLUDE (employee_id) FROM raw.fact_attrition_risk",
        ("prediction_id",),
    ),
    # The source has only employee_id.  Resolve a single SCD Type 2 version at
    # the task creation date and store its surrogate key for analytic joins.
    "fact_task": (
        """
        SELECT f.* EXCLUDE (assignee_employee_id), d.employee_key AS assignee_employee_key
        FROM raw.fact_task AS f
        LEFT JOIN raw.dim_employee AS d
          ON f.assignee_employee_id = d.employee_id
         AND f.created_date >= d.valid_from
         AND f.created_date <= d.valid_to
        """,
        ("task_id",),
    ),
    # The source has only employee_id.  Resolve the historical version at the
    # anomaly period, retaining every source row even when it cannot resolve.
    "fact_anomaly": (
        """
        SELECT f.* EXCLUDE (employee_id), d.employee_key
        FROM raw.fact_anomaly AS f
        LEFT JOIN raw.dim_employee AS d
          ON f.employee_id = d.employee_id
         AND f.period >= d.valid_from
         AND f.period <= d.valid_to
        """,
        ("result_id",),
    ),
}

ORPHAN_CHECKS = (
    ("fact_payroll.employee_key -> dim_employee", "fact_payroll", "employee_key", "dim_employee", "employee_key"),
    ("fact_payroll.date_key -> dim_date", "fact_payroll", "date_key", "dim_date", "date_key"),
    ("fact_payroll.department_id -> dim_department", "fact_payroll", "department_id", "dim_department", "department_id"),
    ("fact_payroll.role_id -> dim_role", "fact_payroll", "role_id", "dim_role", "role_id"),
    ("fact_attendance_monthly.employee_key -> dim_employee", "fact_attendance_monthly", "employee_key", "dim_employee", "employee_key"),
    ("fact_attendance_monthly.date_key -> dim_date", "fact_attendance_monthly", "date_key", "dim_date", "date_key"),
    ("fact_attendance_monthly.department_id -> dim_department", "fact_attendance_monthly", "department_id", "dim_department", "department_id"),
    ("fact_leave.employee_key -> dim_employee", "fact_leave", "employee_key", "dim_employee", "employee_key"),
    ("fact_leave.leave_type_code -> dim_leave_type", "fact_leave", "leave_type_code", "dim_leave_type", "leave_type_code"),
    ("fact_leave.start_date_key -> dim_date", "fact_leave", "start_date_key", "dim_date", "date_key"),
    ("fact_leave.end_date_key -> dim_date", "fact_leave", "end_date_key", "dim_date", "date_key"),
    ("fact_headcount_monthly.date_key -> dim_date", "fact_headcount_monthly", "date_key", "dim_date", "date_key"),
    ("fact_headcount_monthly.department_id -> dim_department", "fact_headcount_monthly", "department_id", "dim_department", "department_id"),
    ("fact_ledger.date_key -> dim_date", "fact_ledger", "date_key", "dim_date", "date_key"),
    ("fact_ledger.cost_center_department_id -> dim_department", "fact_ledger", "cost_center_department_id", "dim_department", "department_id"),
    ("fact_invoice.invoice_date_key -> dim_date", "fact_invoice", "invoice_date_key", "dim_date", "date_key"),
    ("fact_expense.expense_date_key -> dim_date", "fact_expense", "expense_date_key", "dim_date", "date_key"),
    ("fact_expense.department_id -> dim_department", "fact_expense", "department_id", "dim_department", "department_id"),
    ("fact_forecast.forecast_month_key -> dim_date", "fact_forecast", "forecast_month_key", "dim_date", "date_key"),
    ("fact_attrition_risk.employee_key -> dim_employee", "fact_attrition_risk", "employee_key", "dim_employee", "employee_key"),
    ("fact_attrition_risk.as_of_date_key -> dim_date", "fact_attrition_risk", "as_of_date_key", "dim_date", "date_key"),
    ("fact_attrition_risk.department_id -> dim_department", "fact_attrition_risk", "department_id", "dim_department", "department_id"),
    ("fact_task.team_id -> dim_team", "fact_task", "team_id", "dim_team", "team_id"),
    ("fact_task.sprint_id -> dim_sprint", "fact_task", "sprint_id", "dim_sprint", "sprint_id"),
    ("fact_task.assignee_employee_key -> dim_employee", "fact_task", "assignee_employee_key", "dim_employee", "employee_key"),
    ("fact_anomaly.period_key -> dim_date", "fact_anomaly", "period_key", "dim_date", "date_key"),
    ("fact_anomaly.employee_key -> dim_employee", "fact_anomaly", "employee_key", "dim_employee", "employee_key"),
)


def validate_primary_keys(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    """Fail before writing if a declared source primary key is invalid."""
    results: list[dict[str, object]] = []
    for table, (_, key_columns) in TABLE_SPECS.items():
        columns = ", ".join(key_columns)
        null_test = " OR ".join(f"{column} IS NULL" for column in key_columns)
        duplicate_groups = connection.execute(
            f"SELECT COUNT(*) FROM (SELECT {columns}, COUNT(*) FROM raw.{table} "
            f"GROUP BY {columns} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        null_rows = connection.execute(
            f"SELECT COUNT(*) FROM raw.{table} WHERE {null_test}"
        ).fetchone()[0]
        result = {
            "table": table,
            "primary_key": list(key_columns),
            "duplicate_key_groups": duplicate_groups,
            "null_key_rows": null_rows,
        }
        results.append(result)
        if duplicate_groups or null_rows:
            raise ValueError(f"Cannot build warehouse: invalid primary key in raw.{table}: {result}")
    return results


def create_warehouse(connection: duckdb.DuckDBPyConnection, replace: bool) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS warehouse")
    existing = [
        table
        for (table,) in connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'warehouse' AND table_type = 'BASE TABLE'"
        ).fetchall()
        if table in TABLE_SPECS
    ]
    if existing and not replace:
        names = ", ".join(sorted(existing))
        raise FileExistsError(
            f"Warehouse tables already exist ({names}). Re-run with --replace only when you intend to rebuild them."
        )
    if replace:
        for table in TABLE_SPECS:
            connection.execute(f"DROP TABLE IF EXISTS warehouse.{table}")
    for table, (select_sql, key_columns) in TABLE_SPECS.items():
        connection.execute(f"CREATE TABLE warehouse.{table} AS {select_sql}")
        connection.execute(
            f"ALTER TABLE warehouse.{table} ADD PRIMARY KEY ({', '.join(key_columns)})"
        )


def row_count_reconciliation(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for table in TABLE_SPECS:
        raw_rows = connection.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        warehouse_rows = connection.execute(f"SELECT COUNT(*) FROM warehouse.{table}").fetchone()[0]
        rows.append(
            {
                "table": table,
                "raw_rows": raw_rows,
                "warehouse_rows": warehouse_rows,
                "reconciles": raw_rows == warehouse_rows,
            }
        )
    return rows


def orphan_checks(connection: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, fact, foreign_key, dimension, primary_key in ORPHAN_CHECKS:
        null_foreign_keys = connection.execute(
            f"SELECT COUNT(*) FROM warehouse.{fact} WHERE {foreign_key} IS NULL"
        ).fetchone()[0]
        orphan_foreign_keys = connection.execute(
            f"SELECT COUNT(*) FROM warehouse.{fact} AS f "
            f"LEFT JOIN warehouse.{dimension} AS d ON f.{foreign_key} = d.{primary_key} "
            f"WHERE f.{foreign_key} IS NOT NULL AND d.{primary_key} IS NULL"
        ).fetchone()[0]
        rows.append(
            {
                "relationship": name,
                "null_foreign_keys": null_foreign_keys,
                "orphan_foreign_keys": orphan_foreign_keys,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Task 2's validated star-schema warehouse.")
    parser.add_argument("--replace", action="store_true", help="Rebuild existing warehouse tables.")
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DATABASE_PATH))
    try:
        primary_key_checks = validate_primary_keys(connection)
        create_warehouse(connection, replace=args.replace)
        reconciliation = row_count_reconciliation(connection)
        orphans = orphan_checks(connection)
        report = {
            "run_at_utc": datetime.now(UTC).isoformat(),
            "database": str(DATABASE_PATH),
            "raw_schema_modified": False,
            "warehouse_schema": "warehouse",
            "primary_key_checks": primary_key_checks,
            "row_count_reconciliation": reconciliation,
            "orphan_checks": orphans,
            "all_row_counts_reconcile": all(row["reconciles"] for row in reconciliation),
            "orphan_foreign_key_total": sum(row["orphan_foreign_keys"] for row in orphans),
            "null_foreign_key_total": sum(row["null_foreign_keys"] for row in orphans),
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
