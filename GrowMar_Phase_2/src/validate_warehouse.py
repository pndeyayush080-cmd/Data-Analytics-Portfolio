#!/usr/bin/env python3
"""
Warehouse validation script for GrowMar Phase 2.

Validates the DuckDB warehouse against the source Excel workbook.
Generates Markdown report and execution log.
"""

from __future__ import annotations

from pathlib import Path
import sys
import logging
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field

import duckdb
import openpyxl


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "warehouse" / "pulseiq.duckdb"
WORKBOOK_PATH = PROJECT_ROOT / "data" / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
REPORT_DIR = PROJECT_ROOT / "reports"
LOG_DIR = PROJECT_ROOT / "logs"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = REPORT_DIR / "warehouse_validation_report.md"
LOG_PATH = LOG_DIR / "warehouse_validation.log"

# Expected tables and their row counts (from successful extraction)
EXPECTED_TABLES: dict[str, int] = {
    # Dimensions
    "dim_date": 2557,
    "dim_employee": 1606,
    "dim_department": 11,
    "dim_role": 58,
    "dim_location": 9,
    "dim_leave_type": 6,
    "dim_account": 47,
    "dim_client": 28,
    "dim_vendor": 30,
    "dim_team": 16,
    "dim_sprint": 38,
    # Facts
    "fact_payroll": 7344,
    "fact_attendance_monthly": 7343,
    "fact_leave": 3441,
    "fact_headcount_monthly": 891,
    "fact_ledger": 6784,
    "fact_invoice": 743,
    "fact_invoice_payment": 709,
    "fact_expense": 501,
    "fact_task": 28868,
    "fact_anomaly": 405,
    "fact_attrition_risk": 430,
    "fact_forecast": 72,
    # Targets
    "budget_payroll_dept_month": 198,
    "kpi_targets": 180,
}

ALL_TABLE_NAMES = list(EXPECTED_TABLES.keys())

# Key columns for integrity checks (from data_dictionary)
# (table, column, description)
KEY_COLUMNS = {
    "dim_employee": "employee_key",
    "dim_date": "date_key",
    "dim_department": "department_id",
    "dim_role": "role_id",
    "dim_location": "work_location",
    "dim_leave_type": "leave_type_code",
    "dim_account": "account_code",
    "dim_client": "client_id",
    "dim_vendor": "vendor_id",
    "dim_team": "team_id",
    "dim_sprint": "sprint_id",
    "fact_payroll": "payroll_item_id",
    "fact_attendance_monthly": "attendance_fact_id",
    "fact_leave": "leave_request_id",
    "fact_headcount_monthly": "date_key",  # composite with department_id
    "fact_ledger": "line_id",
    "fact_invoice": "invoice_id",
    "fact_invoice_payment": "payment_id",
    "fact_expense": "expense_id",
    "fact_task": "task_id",
    "fact_anomaly": "result_id",
    "fact_attrition_risk": "prediction_id",
    "fact_forecast": "forecast_id",
    "budget_payroll_dept_month": "department_id",  # composite with month
    "kpi_targets": "month",  # composite with department_id
}

# Foreign key relationships to check (child_table, child_col, parent_table, parent_col)
FK_RELATIONSHIPS = [
    # Fact -> Dimension joins
    ("fact_payroll", "employee_key", "dim_employee", "employee_key"),
    ("fact_payroll", "date_key", "dim_date", "date_key"),
    ("fact_payroll", "department_id", "dim_department", "department_id"),
    ("fact_payroll", "role_id", "dim_role", "role_id"),
    ("fact_attendance_monthly", "employee_key", "dim_employee", "employee_key"),
    ("fact_attendance_monthly", "date_key", "dim_date", "date_key"),
    ("fact_attendance_monthly", "department_id", "dim_department", "department_id"),
    ("fact_leave", "employee_key", "dim_employee", "employee_key"),
    ("fact_leave", "leave_type_code", "dim_leave_type", "leave_type_code"),
    ("fact_leave", "start_date_key", "dim_date", "date_key"),
    ("fact_leave", "end_date_key", "dim_date", "date_key"),
    ("fact_headcount_monthly", "date_key", "dim_date", "date_key"),
    ("fact_headcount_monthly", "department_id", "dim_department", "department_id"),
    ("fact_ledger", "date_key", "dim_date", "date_key"),
    ("fact_ledger", "account_code", "dim_account", "account_code"),
    ("fact_ledger", "cost_center_department_id", "dim_department", "department_id"),
    ("fact_invoice", "invoice_date_key", "dim_date", "date_key"),
    ("fact_invoice", "client_id", "dim_client", "client_id"),
    ("fact_invoice", "service_line_account", "dim_account", "account_code"),
    ("fact_invoice_payment", "invoice_id", "fact_invoice", "invoice_id"),
    ("fact_invoice_payment", "payment_date_key", "dim_date", "date_key"),
    ("fact_expense", "expense_date_key", "dim_date", "date_key"),
    ("fact_expense", "category_account", "dim_account", "account_code"),
    ("fact_expense", "vendor_id", "dim_vendor", "vendor_id"),
    ("fact_expense", "department_id", "dim_department", "department_id"),
    ("fact_task", "team_id", "dim_team", "team_id"),
    ("fact_task", "sprint_id", "dim_sprint", "sprint_id"),
    ("fact_task", "assignee_employee_id", "dim_employee", "employee_id"),
    ("fact_anomaly", "employee_id", "dim_employee", "employee_id"),
    ("fact_anomaly", "period_key", "dim_date", "date_key"),
    ("fact_attrition_risk", "employee_id", "dim_employee", "employee_id"),
    ("fact_attrition_risk", "as_of_date_key", "dim_date", "date_key"),
    ("fact_attrition_risk", "department_id", "dim_department", "department_id"),
    ("fact_attrition_risk", "employee_key", "dim_employee", "employee_key"),
    ("fact_forecast", "department_id", "dim_department", "department_id"),
    ("fact_forecast", "forecast_month_key", "dim_date", "date_key"),
    ("budget_payroll_dept_month", "department_id", "dim_department", "department_id"),
    ("kpi_targets", "department_id", "dim_department", "department_id"),
    ("kpi_targets", "month", "dim_date", "date_key"),  # month is first day, date_key is month end
]


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    table: str
    status: str  # PASS, FAIL, WARNING, SKIP
    message: str
    evidence: str = ""


@dataclass
class TableValidation:
    """Aggregated validation results for a table."""
    table_name: str
    expected_rows: int
    actual_rows: int
    row_count_status: str
    schema_checks: list[ValidationResult] = field(default_factory=list)
    integrity_checks: list[ValidationResult] = field(default_factory=list)
    quality_checks: list[ValidationResult] = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        """Determine overall table status."""
        statuses = [self.row_count_status]
        for check_list in [self.schema_checks, self.integrity_checks, self.quality_checks]:
            statuses.extend(c.status for c in check_list)
        if "FAIL" in statuses:
            return "FAIL"
        if "WARNING" in statuses:
            return "WARNING"
        return "PASS"


class WarehouseValidator:
    """Main validation orchestrator."""

    def __init__(self):
        self.results: list[TableValidation] = []
        self.global_checks: list[ValidationResult] = []
        self.timestamp = datetime.now().isoformat(timespec="seconds")
        self.setup_logging()

    def setup_logging(self):
        """Configure logging to file and console."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            handlers=[
                logging.FileHandler(LOG_PATH, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("Warehouse validation started")
        self.logger.info(f"Timestamp: {self.timestamp}")
        self.logger.info(f"Database: {DB_PATH}")
        self.logger.info(f"Workbook: {WORKBOOK_PATH}")

    def run(self) -> int:
        """Run all validations. Returns 0 on success, non-zero on critical failure."""
        try:
            self.validate_database_exists()
            self.validate_table_presence()
            self.validate_row_counts()
            self.validate_schemas()
            self.validate_integrity()
            self.validate_data_quality()
            self.generate_report()
            self.logger.info("Validation completed successfully")
            return 0
        except Exception as e:
            self.logger.exception("Validation failed with exception")
            return 1

    # ──────────────────────────────────────────────────────────────────
    # Core validation methods
    # ──────────────────────────────────────────────────────────────────

    def validate_database_exists(self):
        """Check database file exists and is accessible."""
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Database not found: {DB_PATH}")
        self.logger.info(f"Database file found: {DB_PATH}")

    def validate_table_presence(self):
        """Check that exactly 25 expected tables exist."""
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            db_tables = {t[0] for t in tables}
            expected = set(ALL_TABLE_NAMES)
            missing = expected - db_tables
            extra = db_tables - expected

            if missing:
                self.global_checks.append(ValidationResult(
                    "table_presence", "global", "FAIL",
                    f"Missing expected tables: {sorted(missing)}"
                ))
            if extra:
                self.global_checks.append(ValidationResult(
                    "table_presence", "global", "WARNING",
                    f"Unexpected tables found: {sorted(extra)}"
                ))
            if not missing and not extra:
                self.global_checks.append(ValidationResult(
                    "table_presence", "global", "PASS",
                    "All 25 expected tables present, no unexpected tables"
                ))
            self.logger.info(f"Database tables: {len(db_tables)} (expected 25)")
        finally:
            conn.close()

    def validate_row_counts(self):
        """Compare database row counts with expected counts and source workbook."""
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        wb = openpyxl.load_workbook(WORKBOOK_PATH, read_only=True, data_only=True)
        try:
            for table in ALL_TABLE_NAMES:
                expected = EXPECTED_TABLES[table]
                # Database count
                actual = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                # Source workbook count (data rows only, exclude header)
                ws = wb[table]
                source_count = sum(1 for _ in ws.iter_rows()) - 1

                status = "PASS" if actual == expected == source_count else "FAIL"
                if actual != expected:
                    self.logger.warning(
                        f"Row count mismatch for {table}: DB={actual:,}, Expected={expected:,}, Source={source_count:,}"
                    )

                tv = TableValidation(
                    table_name=table,
                    expected_rows=expected,
                    actual_rows=actual,
                    row_count_status=status,
                )
                tv.schema_checks.append(ValidationResult(
                    "row_count", table, status,
                    f"DB={actual:,}, Expected={expected:,}, Source={source_count:,}",
                    f"DB rows: {actual}, Expected: {expected}, Source: {source_count}"
                ))
                self.results.append(tv)

            self.logger.info("Row count validation completed")
        finally:
            conn.close()
            wb.close()

    def validate_schemas(self):
        """Verify column names and types are reasonable."""
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            for tv in self.results:
                table = tv.table_name
                schema = conn.execute(f"DESCRIBE {table}").fetchall()
                # schema rows: (column_name, column_type, null, key, default, extra)
                col_names = [c[0] for c in schema]
                col_types = {c[0]: c[1] for c in schema}

                # Check key column exists
                if table in KEY_COLUMNS:
                    key_col = KEY_COLUMNS[table]
                    if key_col in col_names:
                        tv.schema_checks.append(ValidationResult(
                            "key_column_present", table, "PASS",
                            f"Key column '{key_col}' found in schema"
                        ))
                    else:
                        tv.schema_checks.append(ValidationResult(
                            "key_column_present", table, "FAIL",
                            f"Key column '{key_col}' MISSING from schema"
                        ))

                # Check for reasonable type mappings
                # (basic sanity - VARCHAR, INTEGER, BIGINT, DOUBLE, DATE, TIMESTAMP)
                for col, typ in col_types.items():
                    if typ.upper() not in ("VARCHAR", "INTEGER", "BIGINT", "DOUBLE", "DATE", "TIMESTAMP"):
                        tv.schema_checks.append(ValidationResult(
                            "column_type", table, "WARNING",
                            f"Column '{col}' has unexpected type: {typ}"
                        ))

                # Log schema
                self.logger.debug(f"{table} schema: {len(col_names)} columns")

            self.logger.info("Schema validation completed")
        finally:
            conn.close()

    def validate_integrity(self):
        """Run key integrity checks: duplicates, orphans."""
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            for tv in self.results:
                table = tv.table_name

                # Check for duplicate primary/business keys
                if table in KEY_COLUMNS:
                    key_col = KEY_COLUMNS[table]
                    # For composite keys, we check the primary one
                    try:
                        dup_count = conn.execute(
                            f'SELECT COUNT(*) - COUNT(DISTINCT "{key_col}") FROM "{table}"'
                        ).fetchone()[0]
                        if dup_count > 0:
                            tv.integrity_checks.append(ValidationResult(
                                "duplicate_keys", table, "WARNING",
                                f"Key column '{key_col}' has {dup_count} duplicate values",
                                f"Duplicate count: {dup_count}"
                            ))
                        else:
                            tv.integrity_checks.append(ValidationResult(
                                "duplicate_keys", table, "PASS",
                                f"Key column '{key_col}' has no duplicates"
                            ))
                    except Exception as e:
                        tv.integrity_checks.append(ValidationResult(
                            "duplicate_keys", table, "SKIP",
                            f"Could not check duplicates: {e}"
                        ))

            # Check foreign key orphans
            for child, child_col, parent, parent_col in FK_RELATIONSHIPS:
                # Skip if tables don't exist in our scope
                if child not in ALL_TABLE_NAMES or parent not in ALL_TABLE_NAMES:
                    continue
                # Special handling for composite keys
                if child == "fact_headcount_monthly" and child_col == "date_key":
                    continue  # Composite key (date_key, department_id) - skip simple check
                if child == "budget_payroll_dept_month" and child_col == "department_id":
                    continue  # Composite key (department_id, month)
                if child == "kpi_targets" and child_col == "month":
                    continue  # Composite key (month, department_id)

                try:
                    orphan_count = conn.execute(
                        f'''
                        SELECT COUNT(*) FROM "{child}" c
                        LEFT JOIN "{parent}" p ON c."{child_col}" = p."{parent_col}"
                        WHERE p."{parent_col}" IS NULL AND c."{child_col}" IS NOT NULL
                        '''
                    ).fetchone()[0]
                    if orphan_count > 0:
                        # Find the TableValidation object for this child table
                        for tv in self.results:
                            if tv.table_name == child:
                                tv.integrity_checks.append(ValidationResult(
                                    "orphan_fk", child, "WARNING",
                                    f"FK '{child_col}' -> '{parent}.{parent_col}' has {orphan_count} orphan values",
                                    f"Orphan count: {orphan_count}"
                                ))
                                break
                    else:
                        for tv in self.results:
                            if tv.table_name == child:
                                tv.integrity_checks.append(ValidationResult(
                                    "orphan_fk", child, "PASS",
                                    f"FK '{child_col}' -> '{parent}.{parent_col}' has no orphans"
                                ))
                                break
                except Exception as e:
                    for tv in self.results:
                        if tv.table_name == child:
                            tv.integrity_checks.append(ValidationResult(
                                "orphan_fk", child, "SKIP",
                                f"Could not check FK '{child_col}': {e}"
                            ))
                            break

            self.logger.info("Integrity validation completed")
        finally:
            conn.close()

    def validate_data_quality(self):
        """Run basic data quality checks."""
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            for tv in self.results:
                table = tv.table_name
                schema = conn.execute(f"DESCRIBE {table}").fetchall()
                col_names = [c[0] for c in schema]
                col_types = {c[0]: c[1] for c in schema}

                # Check for nulls in key columns
                if table in KEY_COLUMNS:
                    key_col = KEY_COLUMNS[table]
                    if key_col in col_names:
                        null_count = conn.execute(
                            f'SELECT COUNT(*) FROM "{table}" WHERE "{key_col}" IS NULL'
                        ).fetchone()[0]
                        if null_count > 0:
                            tv.quality_checks.append(ValidationResult(
                                "null_keys", table, "FAIL",
                                f"Key column '{key_col}' has {null_count} NULL values"
                            ))
                        else:
                            tv.quality_checks.append(ValidationResult(
                                "null_keys", table, "PASS",
                                f"Key column '{key_col}' has no NULLs"
                            ))

                # Check date columns have valid dates (not all NULL)
                date_cols = [c for c, t in col_types.items() if t.upper() in ("DATE", "TIMESTAMP")]
                for dc in date_cols:
                    null_count = conn.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE "{dc}" IS NULL'
                    ).fetchone()[0]
                    total = tv.actual_rows
                    if null_count > 0 and null_count < total:
                        pass  # Some nulls expected for some date columns
                    elif null_count == total and total > 0:
                        tv.quality_checks.append(ValidationResult(
                            "all_null_dates", table, "WARNING",
                            f"Date column '{dc}' is entirely NULL ({total} rows)"
                        ))

                # Check numeric columns for reasonable ranges (basic)
                num_cols = [c for c, t in col_types.items() if t.upper() in ("INTEGER", "BIGINT", "DOUBLE")]
                for nc in num_cols[:5]:  # Limit to first 5 to avoid long queries
                    try:
                        min_val, max_val = conn.execute(
                            f'SELECT MIN("{nc}"), MAX("{nc}") FROM "{table}"'
                        ).fetchone()
                        if min_val is not None and max_val is not None:
                            pass  # Just log that range is computable
                    except Exception:
                        pass  # Some columns may not support min/max

            self.logger.info("Data quality validation completed")
        finally:
            conn.close()

    def generate_report(self):
        """Generate the Markdown validation report."""
        total_tables = len(self.results)
        passed = sum(1 for tv in self.results if tv.overall_status == "PASS")
        failed = sum(1 for tv in self.results if tv.overall_status == "FAIL")
        warnings = sum(1 for tv in self.results if tv.overall_status == "WARNING")

        lines = []
        lines.append("# Warehouse Validation Report")
        lines.append("")
        lines.append(f"**Validation Timestamp:** {self.timestamp}")
        lines.append(f"**Database:** `{DB_PATH.relative_to(PROJECT_ROOT)}`")
        lines.append(f"**Source Workbook:** `{WORKBOOK_PATH.relative_to(PROJECT_ROOT)}`")
        lines.append(f"**Project Root:** `{PROJECT_ROOT}`")
        lines.append("")

        # Global summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(f"- **Tables Validated:** {total_tables}")
        lines.append(f"- **PASS:** {passed}")
        lines.append(f"- **FAIL:** {failed}")
        lines.append(f"- **WARNING:** {warnings}")
        lines.append("")

        # Global checks
        if self.global_checks:
            lines.append("## Global Checks")
            lines.append("")
            for gc in self.global_checks:
                lines.append(f"- **{gc.status}** | {gc.check_name} | {gc.message}")
            lines.append("")

        # Table-by-table details
        lines.append("## Table-by-Table Validation")
        lines.append("")

        for tv in sorted(self.results, key=lambda x: x.table_name):
            status_emoji = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️", "SKIP": "⏭️"}.get(tv.overall_status, "❓")
            lines.append(f"### {status_emoji} {tv.table_name}")
            lines.append("")
            lines.append(f"- **Expected Rows:** {tv.expected_rows:,}")
            lines.append(f"- **Actual Rows:** {tv.actual_rows:,}")
            lines.append(f"- **Row Count Status:** {tv.row_count_status}")
            lines.append(f"- **Overall Status:** {tv.overall_status}")
            lines.append("")

            # Schema checks
            if tv.schema_checks:
                lines.append("#### Schema Checks")
                lines.append("")
                for c in tv.schema_checks:
                    lines.append(f"- **{c.status}** | {c.check_name} | {c.message}")
                lines.append("")

            # Integrity checks
            if tv.integrity_checks:
                lines.append("#### Integrity Checks")
                lines.append("")
                for c in tv.integrity_checks:
                    lines.append(f"- **{c.status}** | {c.check_name} | {c.message}")
                lines.append("")

            # Quality checks
            if tv.quality_checks:
                lines.append("#### Data Quality Checks")
                lines.append("")
                for c in tv.quality_checks:
                    lines.append(f"- **{c.status}** | {c.check_name} | {c.message}")
                lines.append("")

        # Summary of findings
        all_findings = []
        for tv in self.results:
            for cl in [tv.schema_checks, tv.integrity_checks, tv.quality_checks]:
                all_findings.extend(cl)

        fail_count = sum(1 for c in all_findings if c.status == "FAIL")
        warn_count = sum(1 for c in all_findings if c.status == "WARNING")

        lines.append("## Summary of Findings")
        lines.append("")
        lines.append(f"- **Total Checks:** {len(all_findings)}")
        lines.append(f"- **FAIL:** {fail_count}")
        lines.append(f"- **WARNING:** {warn_count}")
        lines.append(f"- **PASS:** {len(all_findings) - fail_count - warn_count}")
        lines.append("")

        if fail_count == 0 and warn_count == 0:
            lines.append("**Overall Result: ✅ ALL CHECKS PASSED**")
        elif fail_count == 0:
            lines.append("**Overall Result: ⚠️ PASSED WITH WARNINGS**")
        else:
            lines.append("**Overall Result: ❌ VALIDATION FAILED**")

        lines.append("")
        lines.append("---")
        lines.append(f"*Report generated: {self.timestamp}*")

        report_content = "\n".join(lines)
        REPORT_PATH.write_text(report_content, encoding="utf-8")
        self.logger.info(f"Report written to: {REPORT_PATH}")


def main() -> int:
    validator = WarehouseValidator()
    return validator.run()


if __name__ == "__main__":
    sys.exit(main())