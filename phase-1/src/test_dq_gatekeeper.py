"""Proof tests for every Task 3 data-quality check.

Each test creates an in-memory copy of the raw tables, adds one deliberate bad
record to that copy, and proves the targeted check reports it.  The production
database and source CSV files are only attached read-only and are never edited.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

import run_dq_gatekeeper as gatekeeper


TABLES = [
    "dim_employee", "fact_anomaly", "fact_attendance_monthly",
    "fact_attrition_risk", "fact_expense", "fact_invoice", "fact_leave",
    "fact_ledger", "fact_payroll", "fact_task",
]


class GatekeeperProofTests(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect(":memory:")
        database = str(gatekeeper.DATABASE_PATH).replace("'", "''")
        self.connection.execute(f"ATTACH '{database}' AS source (READ_ONLY)")
        self.connection.execute("CREATE SCHEMA raw")
        for table in TABLES:
            self.connection.execute(
                f"CREATE TABLE raw.{table} AS SELECT * FROM source.raw.{table}"
            )
        self.connection.execute("DETACH source")

        # The sandbox's OS temp directory is read-only; keep this disposable
        # fixture under the project and remove it in tearDown.
        self.tempdir = tempfile.TemporaryDirectory(dir=gatekeeper.PROJECT_ROOT)
        self.original_log_path = gatekeeper.ETL_LOG_PATH
        gatekeeper.ETL_LOG_PATH = Path(self.tempdir.name) / "etl_run_log.json"
        gatekeeper.ETL_LOG_PATH.write_text(json.dumps({
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETE",
        }), encoding="utf-8")

    def tearDown(self):
        gatekeeper.ETL_LOG_PATH = self.original_log_path
        self.connection.close()
        self.tempdir.cleanup()

    def assert_detected(self, check_id, injected_finding):
        findings = gatekeeper.run_check(self.connection, check_id)
        self.assertTrue(injected_finding(findings), f"{check_id} did not detect its injected bad row")

    def test_c01_to_c14_each_detect_an_isolated_bad_row(self):
        c = self.connection

        c.execute("""
            INSERT INTO raw.fact_payroll
            SELECT * REPLACE (
                'TEST-C01' AS payroll_item_id,
                'TEST-C01' AS run_id,
                DATE '2099-12-31' AS period_end_date
            ) FROM raw.fact_payroll LIMIT 1
        """)
        self.assert_detected("DQ-C01", lambda f: (f["month"] == "2099-12-01").any())

        c.execute("""
            INSERT INTO raw.fact_ledger
            SELECT * REPLACE (
                'TEST-C02' AS line_id, 'TEST-C02' AS entry_id,
                1.0 AS debit, 0.0 AS credit
            ) FROM raw.fact_ledger LIMIT 1
        """)
        self.assert_detected("DQ-C02", lambda f: (f["entry_id"] == "TEST-C02").any())

        c.execute("""
            INSERT INTO raw.fact_payroll
            SELECT * REPLACE ('TEST-C03-A' AS payroll_item_id, 'TEST-C03' AS run_id)
            FROM raw.fact_payroll LIMIT 1
        """)
        c.execute("""
            INSERT INTO raw.fact_payroll
            SELECT * REPLACE ('TEST-C03-B' AS payroll_item_id, 'TEST-C03' AS run_id)
            FROM raw.fact_payroll LIMIT 1
        """)
        self.assert_detected("DQ-C03", lambda f: (f["run_id"] == "TEST-C03").any())

        c.execute("""
            INSERT INTO raw.fact_payroll
            SELECT * REPLACE ('TEST-C04' AS payroll_item_id, 'TEST-ORPHAN' AS employee_id)
            FROM raw.fact_payroll LIMIT 1
        """)
        self.assert_detected("DQ-C04", lambda f: (f["employee_id"] == "TEST-ORPHAN").any())

        c.execute("""
            INSERT INTO raw.fact_attendance_monthly
            SELECT * REPLACE (
                'TEST-C05' AS attendance_fact_id,
                (SELECT employee_id FROM raw.dim_employee
                 WHERE is_current = 'Y' AND exit_date IS NOT NULL LIMIT 1) AS employee_id,
                DATE '2099-12-31' AS period_end_date
            ) FROM raw.fact_attendance_monthly LIMIT 1
        """)
        self.assert_detected("DQ-C05", lambda f: (f["attendance_fact_id"] == "TEST-C05").any())

        c.execute("""
            INSERT INTO raw.fact_attendance_monthly
            SELECT * REPLACE (
                'TEST-C06' AS attendance_fact_id, 'TEST-C06' AS employee_id,
                1 AS unpaid_absence_days
            ) FROM raw.fact_attendance_monthly LIMIT 1
        """)
        self.assert_detected("DQ-C06", lambda f: (f["employee_id"] == "TEST-C06").any())

        c.execute("""
            INSERT INTO raw.fact_invoice
            SELECT * REPLACE (
                'TEST-C07' AS invoice_id, total_amount + 1 AS amount_paid,
                -1 AS balance_due
            ) FROM raw.fact_invoice LIMIT 1
        """)
        self.assert_detected("DQ-C07", lambda f: (f["invoice_id"] == "TEST-C07").any())

        c.execute("""
            INSERT INTO raw.fact_expense
            SELECT * REPLACE ('TEST-C08' AS expense_id, total_amount + 1 AS total_amount)
            FROM raw.fact_expense LIMIT 1
        """)
        self.assert_detected("DQ-C08", lambda f: (f["expense_id"] == "TEST-C08").any())

        c.execute("""
            INSERT INTO raw.fact_task
            SELECT * REPLACE (
                'TEST-C09' AS task_id, DATE '2099-02-01' AS started_date,
                DATE '2099-01-31' AS completed_date
            ) FROM raw.fact_task LIMIT 1
        """)
        self.assert_detected("DQ-C09", lambda f: (f["task_id"] == "TEST-C09").any())

        c.execute("""
            INSERT INTO raw.fact_leave
            SELECT * REPLACE (
                'TEST-C10' AS leave_request_id, DATE '2099-02-01' AS start_date,
                DATE '2099-01-31' AS end_date
            ) FROM raw.fact_leave LIMIT 1
        """)
        self.assert_detected("DQ-C10", lambda f: (f["leave_request_id"] == "TEST-C10").any())

        c.execute("""
            INSERT INTO raw.fact_attrition_risk
            SELECT * REPLACE ('TEST-C11' AS prediction_id, DATE '1900-01-01' AS as_of_date)
            FROM raw.fact_attrition_risk LIMIT 1
        """)
        self.assert_detected("DQ-C11", lambda f: (f["record_id"] == "TEST-C11").any())

        for key, valid_from, valid_to in (
            (990001, "2099-01-01", "2099-12-31"),
            (990002, "2099-06-01", "2100-05-31"),
        ):
            c.execute(f"""
                INSERT INTO raw.dim_employee
                SELECT * REPLACE (
                    {key} AS employee_key, 'TEST-C12' AS employee_id,
                    DATE '{valid_from}' AS valid_from, DATE '{valid_to}' AS valid_to
                ) FROM raw.dim_employee LIMIT 1
            """)
        self.assert_detected("DQ-C12", lambda f: (f["employee_id"] == "TEST-C12").any())

        gatekeeper.ETL_LOG_PATH.write_text(json.dumps({
            "run_at_utc": "2000-01-01T00:00:00+00:00", "status": "COMPLETE",
        }), encoding="utf-8")
        self.assert_detected("DQ-C13", lambda f: f["finding"].str.contains("older than 24 hours").any())

        c.execute("""
            CREATE TABLE manager_aggregate_groups (
                output_name VARCHAR, metric_id VARCHAR, group_key VARCHAR,
                distinct_employee_count INTEGER, minimum_group_size INTEGER
            )
        """)
        c.execute("""
            INSERT INTO manager_aggregate_groups VALUES
            ('test_manager_report', 'M01', 'safe', 5, 5),
            ('test_manager_report', 'M01', 'unsafe', 4, 5)
        """)
        self.assert_detected("DQ-C14", lambda f: (f["group_key"] == "unsafe").any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
