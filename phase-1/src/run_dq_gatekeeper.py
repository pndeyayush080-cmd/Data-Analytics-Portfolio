from pathlib import Path
from datetime import datetime, timezone
import json
import uuid

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "pulseiq.duckdb"
ETL_LOG_PATH = PROJECT_ROOT / "data" / "etl" / "etl_run_log.json"

CHECKS = [
    ("DQ-C01", "Payroll equals ledger", "Critical", "fact_payroll, fact_ledger"),
    ("DQ-C02", "Ledger balanced", "Critical", "fact_ledger"),
    ("DQ-C03", "Unique payroll rows", "Critical", "fact_payroll"),
    ("DQ-C04", "No orphan employees", "Critical", "fact_payroll, dim_employee"),
    ("DQ-C05", "No attendance after exit", "Warning", "fact_attendance_monthly, dim_employee"),
    ("DQ-C06", "Unpaid leave deducted", "Warning", "fact_attendance_monthly, fact_payroll"),
    ("DQ-C07", "Invoice arithmetic", "Warning", "fact_invoice"),
    ("DQ-C08", "Expense arithmetic", "Warning", "fact_expense"),
    ("DQ-C09", "Task dates sensible", "Warning", "fact_task"),
    ("DQ-C10", "Leave dates sensible", "Warning", "fact_leave"),
    ("DQ-C11", "AI feeds fresh", "Warning", "fact_attrition_risk, fact_anomaly"),
    ("DQ-C12", "Employee dimension history no overlap", "Critical", "dim_employee"),
    ("DQ-C13", "Pipeline freshness", "Critical", "etl_run_log.json"),
    ("DQ-C14", "Minimum group size", "Critical", "manager_aggregate_groups"),
]


def records_frame(records):
    return pd.DataFrame(records)


def run_check(connection, check_id):
    if check_id == "DQ-C01":
        sql = """
            WITH payroll AS (
                SELECT date_trunc('month', period_end_date)::DATE AS month,
                       SUM(employer_cost) AS cost
                FROM raw.fact_payroll
                GROUP BY 1
            ),
            ledger AS (
                SELECT date_trunc('month', entry_date)::DATE AS month,
                       SUM(signed_amount_debit_positive) AS exp
                FROM raw.fact_ledger
                WHERE account_code BETWEEN 5001 AND 5005
                GROUP BY 1
            )
            SELECT COALESCE(p.month, l.month) AS month,
                   p.cost AS payroll_cost,
                   l.exp AS ledger_expense,
                   p.cost - l.exp AS difference
            FROM payroll p
            FULL OUTER JOIN ledger l USING (month)
            WHERE p.cost IS NULL
               OR l.exp IS NULL
               OR ABS(p.cost - l.exp) > 0.01
            ORDER BY 1
        """
    elif check_id == "DQ-C02":
        sql = """
            SELECT entry_id, SUM(debit) AS total_debit,
                   SUM(credit) AS total_credit,
                   SUM(debit) - SUM(credit) AS difference
            FROM raw.fact_ledger
            GROUP BY entry_id
            HAVING ABS(SUM(debit) - SUM(credit)) > 0.005
            ORDER BY entry_id
        """
    elif check_id == "DQ-C03":
        sql = """
            SELECT employee_id, run_id, COUNT(*) AS row_count
            FROM raw.fact_payroll
            GROUP BY employee_id, run_id
            HAVING COUNT(*) > 1
            ORDER BY employee_id, run_id
        """
    elif check_id == "DQ-C04":
        sql = """
            SELECT f.payroll_item_id, f.employee_id
            FROM raw.fact_payroll f
            LEFT JOIN raw.dim_employee d ON f.employee_id = d.employee_id
            WHERE d.employee_id IS NULL
            ORDER BY f.payroll_item_id
        """
    elif check_id == "DQ-C05":
        sql = """
            SELECT a.attendance_fact_id, a.employee_id,
                   a.period_end_date, d.exit_date
            FROM raw.fact_attendance_monthly a
            JOIN raw.dim_employee d
              ON a.employee_id = d.employee_id AND d.is_current = 'Y'
            WHERE d.exit_date IS NOT NULL
              AND a.period_end_date > last_day(d.exit_date)
            ORDER BY a.employee_id, a.period_end_date
        """
    elif check_id == "DQ-C06":
        sql = """
            WITH attendance AS (
                SELECT employee_id,
                       date_trunc('month', period_end_date)::DATE AS month,
                       SUM(unpaid_absence_days) AS unpaid_days
                FROM raw.fact_attendance_monthly
                GROUP BY 1, 2
            ),
            payroll AS (
                SELECT employee_id,
                       date_trunc('month', period_end_date)::DATE AS month,
                       SUM(lop_days) AS lop_days
                FROM raw.fact_payroll
                GROUP BY 1, 2
            )
            SELECT a.employee_id, a.month, a.unpaid_days,
                   COALESCE(p.lop_days, 0) AS lop_days,
                   a.unpaid_days - COALESCE(p.lop_days, 0) AS difference
            FROM attendance a
            LEFT JOIN payroll p
              ON a.employee_id = p.employee_id AND a.month = p.month
            WHERE a.unpaid_days > 0
              AND ABS(a.unpaid_days - COALESCE(p.lop_days, 0)) > 0.5
            ORDER BY a.month, a.employee_id
        """
    elif check_id == "DQ-C07":
        sql = """
            SELECT invoice_id, amount_paid, total_amount, balance_due
            FROM raw.fact_invoice
            WHERE amount_paid > total_amount + 0.01
               OR balance_due < -0.01
            ORDER BY invoice_id
        """
    elif check_id == "DQ-C08":
        sql = """
            SELECT expense_id, amount_excl_gst, gst_amount, total_amount,
                   total_amount - (amount_excl_gst + gst_amount) AS difference
            FROM raw.fact_expense
            WHERE ABS(total_amount - (amount_excl_gst + gst_amount)) > 0.01
            ORDER BY expense_id
        """
    elif check_id == "DQ-C09":
        sql = """
            SELECT task_id, started_date, completed_date, status
            FROM raw.fact_task
            WHERE (
                started_date IS NOT NULL
                AND completed_date IS NOT NULL
                AND completed_date < started_date
            )
            OR (
                LOWER(TRIM(status)) = 'done'
                AND completed_date IS NULL
            )
            ORDER BY task_id
        """
    elif check_id == "DQ-C10":
        sql = """
            SELECT leave_request_id, start_date, end_date
            FROM raw.fact_leave
            WHERE start_date IS NOT NULL
              AND end_date IS NOT NULL
              AND end_date < start_date
            ORDER BY leave_request_id
        """
    elif check_id == "DQ-C11":
        sql = """
            WITH latest_batch AS (
                SELECT MAX(as_of_date) AS max_as_of_date
                FROM raw.fact_attrition_risk
            )
            SELECT 'fact_attrition_risk' AS feed,
                   prediction_id AS record_id,
                   employee_id,
                   as_of_date AS observed_at,
                   'as_of_date is more than 7 days behind the latest batch' AS finding
            FROM raw.fact_attrition_risk
            WHERE as_of_date < (
                SELECT max_as_of_date - INTERVAL '7 days'
                FROM latest_batch
            )
            ORDER BY as_of_date
        """
        violations = connection.execute(sql).fetchdf()

        # The catalog separately requires that anomaly scoring occurred within
        # 24 hours of the load.  The ETL audit log is the only authoritative
        # load timestamp in this project; do not substitute wall-clock time.
        try:
            log_data = json.loads(ETL_LOG_PATH.read_text(encoding="utf-8"))
            load_at = log_data.get("run_at_utc")
            parsed_load_at = datetime.fromisoformat(
                load_at.replace("Z", "+00:00")
            ) if load_at else None
            if parsed_load_at is None or parsed_load_at.tzinfo is None:
                raise ValueError("run_at_utc is missing or lacks a timezone offset")

            anomaly_sql = """
                SELECT 'fact_anomaly' AS feed,
                       result_id AS record_id,
                       employee_id,
                       scored_at AS observed_at,
                       'scored_at is more than 24 hours before the ETL load' AS finding
                FROM raw.fact_anomaly
                WHERE scored_at IS NULL
                   OR scored_at < ? - INTERVAL '24 hours'
                ORDER BY scored_at, result_id
            """
            anomaly_violations = connection.execute(
                anomaly_sql,
                [parsed_load_at.astimezone(timezone.utc).replace(tzinfo=None)],
            ).fetchdf()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            anomaly_violations = records_frame([{
                "feed": "fact_anomaly",
                "record_id": None,
                "employee_id": None,
                "observed_at": None,
                "finding": f"Cannot evaluate scored_at freshness: {exc}",
            }])

        return pd.concat([violations, anomaly_violations], ignore_index=True)
    elif check_id == "DQ-C12":
        sql = """
            SELECT a.employee_id,
                   a.employee_key AS employee_key_a,
                   a.valid_from AS valid_from_a,
                   a.valid_to AS valid_to_a,
                   b.employee_key AS employee_key_b,
                   b.valid_from AS valid_from_b,
                   b.valid_to AS valid_to_b
            FROM raw.dim_employee a
            JOIN raw.dim_employee b
              ON a.employee_id = b.employee_id
             AND a.employee_key < b.employee_key
             AND a.valid_from <= COALESCE(b.valid_to, DATE '9999-12-31')
             AND b.valid_from <= COALESCE(a.valid_to, DATE '9999-12-31')
            ORDER BY a.employee_id, a.valid_from
        """
    elif check_id == "DQ-C13":
        try:
            log_data = json.loads(ETL_LOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return records_frame([{
                "source": str(ETL_LOG_PATH),
                "finding": f"ETL log missing or invalid: {exc}",
            }])

        run_at = log_data.get("run_at_utc")
        run_status = log_data.get("status")
        violations = []

        if not run_at:
            violations.append({
                "source": str(ETL_LOG_PATH),
                "run_at_utc": run_at,
                "status": run_status,
                "finding": "ETL log is missing run_at_utc",
            })
        else:
            try:
                parsed_time = datetime.fromisoformat(
                    run_at.replace("Z", "+00:00")
                )
                if parsed_time.tzinfo is None:
                    raise ValueError("Timestamp has no timezone offset")
                age_hours = (
                    datetime.now(timezone.utc)
                    - parsed_time.astimezone(timezone.utc)
                ).total_seconds() / 3600
                if age_hours > 24:
                    violations.append({
                        "source": str(ETL_LOG_PATH),
                        "run_at_utc": run_at,
                        "status": run_status,
                        "age_hours": round(age_hours, 2),
                        "finding": "Latest logged ETL run is older than 24 hours",
                    })
            except ValueError as exc:
                violations.append({
                    "source": str(ETL_LOG_PATH),
                    "run_at_utc": run_at,
                    "status": run_status,
                    "finding": f"Invalid run_at_utc timestamp: {exc}",
                })

        if run_status != "COMPLETE":
            violations.append({
                "source": str(ETL_LOG_PATH),
                "run_at_utc": run_at,
                "status": run_status,
                "finding": "ETL status is not COMPLETE",
            })
        return records_frame(violations)
    elif check_id == "DQ-C14":
        # A manager-facing aggregate must be registered with the minimum group
        # size used to publish it.  With no register, publication is blocked:
        # absence of evidence is not evidence that sensitive small groups were
        # suppressed.
        exists = connection.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = 'manager_aggregate_groups'
        """).fetchone()[0]
        if not exists:
            return records_frame([{
                "output_name": None,
                "finding": (
                    "No manager aggregate register is available; group-size "
                    "protection cannot be verified and publication is blocked"
                ),
            }])
        return connection.execute("""
            SELECT output_name, metric_id, group_key, distinct_employee_count,
                   minimum_group_size,
                   'Group is below its required minimum size' AS finding
            FROM manager_aggregate_groups
            WHERE distinct_employee_count < minimum_group_size
            ORDER BY output_name, metric_id, group_key
        """).fetchdf()
    else:
        raise ValueError(f"Unsupported check: {check_id}")

    return connection.execute(sql).fetchdf()


def ensure_results_table(connection):
    """Create the audit table and migrate the pre-Task-3 version in place."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dq_results (
            run_id VARCHAR NOT NULL,
            check_id VARCHAR NOT NULL,
            check_name VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            source_table VARCHAR NOT NULL,
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


def main():
    run_id = str(uuid.uuid4())
    executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    connection = duckdb.connect(str(DATABASE_PATH))

    try:
        ensure_results_table(connection)
        results = []

        for check_id, check_name, severity, source_table in CHECKS:
            violations = run_check(connection, check_id)

            violation_count = len(violations)
            status = "PASS" if violation_count == 0 else "FAIL"
            details = {
                "violation_count": violation_count,
                "sample_violations": json.loads(
                    violations.head(10).to_json(
                        orient="records",
                        date_format="iso",
                    )
                ),
                "sample_limit": 10,
            }

            connection.execute(
                """
                INSERT INTO dq_results (
                    run_id, check_id, check_name, severity, source_table, status,
                    violation_count, details_json, executed_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    check_id,
                    check_name,
                    severity,
                    source_table,
                    status,
                    violation_count,
                    json.dumps(details, default=str),
                    executed_at,
                ],
            )

            results.append({
                "check_id": check_id,
                "check_name": check_name,
                "severity": severity,
                "source_table": source_table,
                "status": status,
                "violation_count": violation_count,
            })

        print(f"DQ run ID: {run_id}")
        print("DQ-C01 to DQ-C14 results:")
        print(json.dumps(results, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
         
