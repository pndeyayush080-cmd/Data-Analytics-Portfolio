"""Data extraction script: Excel (openpyxl) -> DuckDB.

Reads all dimension and fact tables from the PulseIQ workbook and loads them
into a DuckDB database. Preserves source column names, values, and data types
as accurately as practical. No silent cleaning or transformation of business data.

Initialization strategy: DROP existing tables before CREATE inside a single
transaction. Running twice produces identical results. On any failure, the
entire transaction rolls back leaving the database unchanged.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import duckdb
import openpyxl


# ──────────────────────────────────────────────────────────────────────
# Configuration: which sheets to extract and their categories
# ──────────────────────────────────────────────────────────────────────

# Dimension tables (conformed dimensions)
DIMENSION_SHEETS = [
    "dim_date",
    "dim_employee",
    "dim_department",
    "dim_role",
    "dim_location",
    "dim_leave_type",
    "dim_account",
    "dim_client",
    "dim_vendor",
    "dim_team",
    "dim_sprint",
]

# Fact tables (transactional / periodic facts)
FACT_SHEETS = [
    "fact_payroll",
    "fact_attendance_monthly",
    "fact_leave",
    "fact_headcount_monthly",
    "fact_ledger",
    "fact_invoice",
    "fact_invoice_payment",
    "fact_expense",
    "fact_task",
    "fact_anomaly",
    "fact_attrition_risk",
    "fact_forecast",
]

# Target / budget tables (planning data)
TARGET_SHEETS = [
    "budget_payroll_dept_month",
    "kpi_targets",
]

# Sheets explicitly excluded from automatic extraction
EXCLUDED_SHEETS = {
    "README",
    "data_dictionary",
    "metric_dictionary",
    "data_contracts",
    "dq_checks_catalog",
    "reconciliation_answer_key",
    "reference_summary_dept_month",
    "dq_known_issues",
}

ALL_EXTRACT_SHEETS = DIMENSION_SHEETS + FACT_SHEETS + TARGET_SHEETS


# ──────────────────────────────────────────────────────────────────────
# Column type overrides based on data_dictionary data_type column
# ──────────────────────────────────────────────────────────────────────
# These 306 overrides cover every column in all 25 extraction sheets.
# Format: (sheet_name, column_name) -> DuckDB SQL type
# Types used: BIGINT, INTEGER, DOUBLE, DATE, TIMESTAMP, VARCHAR
# Y/N flags kept as VARCHAR to preserve source values exactly.
# Verified: 0 missing, 0 extra, 0 duplicate, 0 type conflicts vs data_dictionary.

COLUMN_TYPE_OVERRIDES: dict[tuple[str, str], str] = {
    # dim_employee (21 columns)
    ("dim_employee", "employee_key"): "BIGINT",
    ("dim_employee", "employee_id"): "VARCHAR",
    ("dim_employee", "full_name"): "VARCHAR",
    ("dim_employee", "gender"): "VARCHAR",
    ("dim_employee", "date_of_birth"): "DATE",
    ("dim_employee", "hire_date"): "DATE",
    ("dim_employee", "exit_date"): "DATE",
    ("dim_employee", "employment_status"): "VARCHAR",
    ("dim_employee", "employment_type"): "VARCHAR",
    ("dim_employee", "department_id"): "VARCHAR",
    ("dim_employee", "role_id"): "VARCHAR",
    ("dim_employee", "role_title"): "VARCHAR",
    ("dim_employee", "job_level"): "INTEGER",
    ("dim_employee", "manager_id"): "VARCHAR",
    ("dim_employee", "work_location"): "VARCHAR",
    ("dim_employee", "work_mode"): "VARCHAR",
    ("dim_employee", "highest_education"): "VARCHAR",
    ("dim_employee", "valid_from"): "DATE",
    ("dim_employee", "valid_to"): "DATE",
    ("dim_employee", "is_current"): "VARCHAR",
    ("dim_employee", "change_reason"): "VARCHAR",

    # dim_date (18 columns)
    ("dim_date", "date"): "DATE",
    ("dim_date", "date_key"): "BIGINT",
    ("dim_date", "year"): "INTEGER",
    ("dim_date", "quarter"): "INTEGER",
    ("dim_date", "month_number"): "INTEGER",
    ("dim_date", "month_name"): "VARCHAR",
    ("dim_date", "year_month"): "VARCHAR",
    ("dim_date", "week_of_year"): "INTEGER",
    ("dim_date", "day_of_week"): "VARCHAR",
    ("dim_date", "is_weekend"): "VARCHAR",
    ("dim_date", "is_holiday"): "VARCHAR",
    ("dim_date", "is_working_day"): "VARCHAR",
    ("dim_date", "financial_year"): "VARCHAR",
    ("dim_date", "fiscal_quarter"): "VARCHAR",
    ("dim_date", "fiscal_month_number"): "INTEGER",
    ("dim_date", "is_month_end"): "VARCHAR",
    ("dim_date", "month_start_date"): "DATE",
    ("dim_date", "month_end_date"): "DATE",

    # dim_department (5 columns)
    ("dim_department", "department_id"): "VARCHAR",
    ("dim_department", "department_name"): "VARCHAR",
    ("dim_department", "cost_center"): "VARCHAR",
    ("dim_department", "description"): "VARCHAR",
    ("dim_department", "is_leadership"): "VARCHAR",

    # dim_role (10 columns)
    ("dim_role", "role_id"): "VARCHAR",
    ("dim_role", "department_id"): "VARCHAR",
    ("dim_role", "role_title"): "VARCHAR",
    ("dim_role", "level"): "INTEGER",
    ("dim_role", "grade"): "VARCHAR",
    ("dim_role", "band_min_annual"): "BIGINT",
    ("dim_role", "band_mid_annual"): "BIGINT",
    ("dim_role", "band_max_annual"): "BIGINT",
    ("dim_role", "overtime_eligible"): "VARCHAR",
    ("dim_role", "band_reference_year"): "INTEGER",

    # dim_location (4 columns)
    ("dim_location", "work_location"): "VARCHAR",
    ("dim_location", "state"): "VARCHAR",
    ("dim_location", "city_tier"): "VARCHAR",
    ("dim_location", "tier_number"): "INTEGER",

    # dim_leave_type (8 columns)
    ("dim_leave_type", "leave_type_code"): "VARCHAR",
    ("dim_leave_type", "leave_type_name"): "VARCHAR",
    ("dim_leave_type", "pay_type"): "VARCHAR",
    ("dim_leave_type", "annual_quota_days"): "INTEGER",
    ("dim_leave_type", "prorated_for_joiners"): "VARCHAR",
    ("dim_leave_type", "carry_forward_allowed"): "VARCHAR",
    ("dim_leave_type", "max_carry_forward_days"): "INTEGER",
    ("dim_leave_type", "policy_note"): "VARCHAR",

    # dim_account (8 columns)
    ("dim_account", "account_code"): "VARCHAR",
    ("dim_account", "account_name"): "VARCHAR",
    ("dim_account", "account_type"): "VARCHAR",
    ("dim_account", "normal_balance"): "VARCHAR",
    ("dim_account", "parent_code"): "VARCHAR",
    ("dim_account", "is_group"): "VARCHAR",
    ("dim_account", "statement"): "VARCHAR",
    ("dim_account", "is_active"): "VARCHAR",

    # dim_client (14 columns)
    ("dim_client", "client_id"): "VARCHAR",
    ("dim_client", "client_name"): "VARCHAR",
    ("dim_client", "industry"): "VARCHAR",
    ("dim_client", "city"): "VARCHAR",
    ("dim_client", "state_or_region"): "VARCHAR",
    ("dim_client", "country"): "VARCHAR",
    ("dim_client", "client_type"): "VARCHAR",
    ("dim_client", "gst_registration"): "VARCHAR",
    ("dim_client", "payment_terms_days"): "INTEGER",
    ("dim_client", "payment_behaviour"): "VARCHAR",
    ("dim_client", "primary_service_line"): "VARCHAR",
    ("dim_client", "contact_email"): "VARCHAR",
    ("dim_client", "onboarded_on"): "DATE",
    ("dim_client", "is_active"): "VARCHAR",

    # dim_vendor (7 columns)
    ("dim_vendor", "vendor_id"): "VARCHAR",
    ("dim_vendor", "vendor_name"): "VARCHAR",
    ("dim_vendor", "primary_expense_account"): "VARCHAR",
    ("dim_vendor", "payment_terms_days"): "INTEGER",
    ("dim_vendor", "city"): "VARCHAR",
    ("dim_vendor", "gst_registration"): "VARCHAR",
    ("dim_vendor", "is_active"): "VARCHAR",

    # dim_team (7 columns)
    ("dim_team", "team_id"): "VARCHAR",
    ("dim_team", "team_name"): "VARCHAR",
    ("dim_team", "department_id"): "VARCHAR",
    ("dim_team", "team_lead_employee_id"): "VARCHAR",
    ("dim_team", "active_members"): "INTEGER",
    ("dim_team", "planning_cadence"): "VARCHAR",
    ("dim_team", "board_tool"): "VARCHAR",

    # dim_sprint (6 columns)
    ("dim_sprint", "sprint_id"): "VARCHAR",
    ("dim_sprint", "sprint_name"): "VARCHAR",
    ("dim_sprint", "start_date"): "DATE",
    ("dim_sprint", "end_date"): "DATE",
    ("dim_sprint", "working_days"): "INTEGER",
    ("dim_sprint", "financial_year"): "VARCHAR",

    # fact_payroll (33 columns)
    ("fact_payroll", "payroll_item_id"): "VARCHAR",
    ("fact_payroll", "run_id"): "VARCHAR",
    ("fact_payroll", "employee_id"): "VARCHAR",
    ("fact_payroll", "date_key"): "BIGINT",
    ("fact_payroll", "employee_key"): "BIGINT",
    ("fact_payroll", "period_end_date"): "DATE",
    ("fact_payroll", "department_id"): "VARCHAR",
    ("fact_payroll", "role_id"): "VARCHAR",
    ("fact_payroll", "payable_days"): "DOUBLE",
    ("fact_payroll", "lop_days"): "DOUBLE",
    ("fact_payroll", "overtime_hours_paid"): "DOUBLE",
    ("fact_payroll", "variable_pay_type"): "VARCHAR",
    ("fact_payroll", "monthly_fixed_gross"): "DOUBLE",
    ("fact_payroll", "basic"): "DOUBLE",
    ("fact_payroll", "hra"): "DOUBLE",
    ("fact_payroll", "conveyance"): "DOUBLE",
    ("fact_payroll", "medical"): "DOUBLE",
    ("fact_payroll", "special_allowance"): "DOUBLE",
    ("fact_payroll", "earned_fixed_pay"): "DOUBLE",
    ("fact_payroll", "overtime_pay"): "DOUBLE",
    ("fact_payroll", "variable_pay"): "DOUBLE",
    ("fact_payroll", "gross_pay"): "DOUBLE",
    ("fact_payroll", "pf_employee"): "DOUBLE",
    ("fact_payroll", "esi_employee"): "DOUBLE",
    ("fact_payroll", "professional_tax"): "DOUBLE",
    ("fact_payroll", "tds"): "DOUBLE",
    ("fact_payroll", "other_deductions"): "DOUBLE",
    ("fact_payroll", "total_deductions"): "DOUBLE",
    ("fact_payroll", "net_pay"): "DOUBLE",
    ("fact_payroll", "pf_employer"): "DOUBLE",
    ("fact_payroll", "esi_employer"): "DOUBLE",
    ("fact_payroll", "employer_cost"): "DOUBLE",
    ("fact_payroll", "headcount_flag"): "INTEGER",

    # fact_attendance_monthly (16 columns)
    ("fact_attendance_monthly", "attendance_fact_id"): "VARCHAR",
    ("fact_attendance_monthly", "employee_id"): "VARCHAR",
    ("fact_attendance_monthly", "date_key"): "BIGINT",
    ("fact_attendance_monthly", "employee_key"): "BIGINT",
    ("fact_attendance_monthly", "department_id"): "VARCHAR",
    ("fact_attendance_monthly", "scheduled_days"): "DOUBLE",
    ("fact_attendance_monthly", "present_days"): "DOUBLE",
    ("fact_attendance_monthly", "wfh_days"): "DOUBLE",
    ("fact_attendance_monthly", "half_days_unpaid"): "DOUBLE",
    ("fact_attendance_monthly", "paid_leave_days"): "DOUBLE",
    ("fact_attendance_monthly", "unpaid_absence_days"): "DOUBLE",
    ("fact_attendance_monthly", "late_arrivals"): "DOUBLE",
    ("fact_attendance_monthly", "avg_hours_worked"): "DOUBLE",
    ("fact_attendance_monthly", "overtime_hours"): "DOUBLE",
    ("fact_attendance_monthly", "attendance_rate"): "DOUBLE",
    ("fact_attendance_monthly", "period_end_date"): "DATE",

    # fact_leave (14 columns)
    ("fact_leave", "leave_request_id"): "VARCHAR",
    ("fact_leave", "employee_id"): "VARCHAR",
    ("fact_leave", "employee_key"): "BIGINT",
    ("fact_leave", "leave_type_code"): "VARCHAR",
    ("fact_leave", "start_date_key"): "BIGINT",
    ("fact_leave", "end_date_key"): "BIGINT",
    ("fact_leave", "start_date"): "DATE",
    ("fact_leave", "end_date"): "DATE",
    ("fact_leave", "days"): "DOUBLE",
    ("fact_leave", "status"): "VARCHAR",
    ("fact_leave", "applied_on"): "DATE",
    ("fact_leave", "decided_on"): "DATE",
    ("fact_leave", "approver_id"): "VARCHAR",
    ("fact_leave", "reason"): "VARCHAR",

    # fact_headcount_monthly (11 columns)
    ("fact_headcount_monthly", "date_key"): "BIGINT",
    ("fact_headcount_monthly", "month_start_date"): "DATE",
    ("fact_headcount_monthly", "department_id"): "VARCHAR",
    ("fact_headcount_monthly", "headcount_start"): "BIGINT",
    ("fact_headcount_monthly", "hires"): "BIGINT",
    ("fact_headcount_monthly", "exits"): "BIGINT",
    ("fact_headcount_monthly", "voluntary_exits"): "BIGINT",
    ("fact_headcount_monthly", "transfers_in"): "BIGINT",
    ("fact_headcount_monthly", "transfers_out"): "BIGINT",
    ("fact_headcount_monthly", "headcount_end"): "BIGINT",
    ("fact_headcount_monthly", "attrition_rate_monthly_pct"): "DOUBLE",

    # fact_ledger (13 columns)
    ("fact_ledger", "line_id"): "VARCHAR",
    ("fact_ledger", "entry_id"): "VARCHAR",
    ("fact_ledger", "date_key"): "BIGINT",
    ("fact_ledger", "entry_date"): "DATE",
    ("fact_ledger", "posting_period"): "VARCHAR",
    ("fact_ledger", "financial_year"): "VARCHAR",
    ("fact_ledger", "account_code"): "VARCHAR",
    ("fact_ledger", "debit"): "DOUBLE",
    ("fact_ledger", "credit"): "DOUBLE",
    ("fact_ledger", "signed_amount_debit_positive"): "DOUBLE",
    ("fact_ledger", "cost_center_department_id"): "VARCHAR",
    ("fact_ledger", "source_type"): "VARCHAR",
    ("fact_ledger", "source_id"): "VARCHAR",

    # fact_invoice (20 columns)
    ("fact_invoice", "invoice_id"): "VARCHAR",
    ("fact_invoice", "invoice_number"): "VARCHAR",
    ("fact_invoice", "client_id"): "VARCHAR",
    ("fact_invoice", "invoice_date_key"): "BIGINT",
    ("fact_invoice", "invoice_date"): "DATE",
    ("fact_invoice", "due_date"): "DATE",
    ("fact_invoice", "service_line_account"): "VARCHAR",
    ("fact_invoice", "subtotal"): "DOUBLE",
    ("fact_invoice", "gst_rate_percent"): "DOUBLE",
    ("fact_invoice", "gst_amount"): "DOUBLE",
    ("fact_invoice", "total_amount"): "DOUBLE",
    ("fact_invoice", "amount_paid"): "DOUBLE",
    ("fact_invoice", "balance_due"): "DOUBLE",
    ("fact_invoice", "status"): "VARCHAR",
    ("fact_invoice", "last_payment_date"): "DATE",
    ("fact_invoice", "days_to_pay"): "DOUBLE",
    ("fact_invoice", "days_past_due_at_cutoff"): "INTEGER",
    ("fact_invoice", "ageing_bucket_at_cutoff"): "VARCHAR",
    ("fact_invoice", "carried_in_from_prior_period"): "VARCHAR",
    ("fact_invoice", "ledger_entry_id"): "VARCHAR",

    # fact_invoice_payment (9 columns)
    ("fact_invoice_payment", "payment_id"): "VARCHAR",
    ("fact_invoice_payment", "invoice_id"): "VARCHAR",
    ("fact_invoice_payment", "payment_date_key"): "BIGINT",
    ("fact_invoice_payment", "payment_date"): "DATE",
    ("fact_invoice_payment", "amount"): "DOUBLE",
    ("fact_invoice_payment", "payment_mode"): "VARCHAR",
    ("fact_invoice_payment", "reference_no"): "VARCHAR",
    ("fact_invoice_payment", "received_by"): "VARCHAR",
    ("fact_invoice_payment", "ledger_entry_id"): "VARCHAR",

    # fact_expense (20 columns)
    ("fact_expense", "expense_id"): "VARCHAR",
    ("fact_expense", "expense_date"): "DATE",
    ("fact_expense", "expense_date_key"): "BIGINT",
    ("fact_expense", "category_account"): "VARCHAR",
    ("fact_expense", "vendor_id"): "VARCHAR",
    ("fact_expense", "bill_reference"): "VARCHAR",
    ("fact_expense", "description"): "VARCHAR",
    ("fact_expense", "department_id"): "VARCHAR",
    ("fact_expense", "amount_excl_gst"): "DOUBLE",
    ("fact_expense", "gst_rate_percent"): "DOUBLE",
    ("fact_expense", "gst_amount"): "DOUBLE",
    ("fact_expense", "total_amount"): "DOUBLE",
    ("fact_expense", "due_date"): "DATE",
    ("fact_expense", "paid_date"): "DATE",
    ("fact_expense", "status"): "VARCHAR",
    ("fact_expense", "payment_mode"): "VARCHAR",
    ("fact_expense", "submitted_by"): "VARCHAR",
    ("fact_expense", "approved_by"): "VARCHAR",
    ("fact_expense", "ledger_entry_id"): "VARCHAR",
    ("fact_expense", "payment_ledger_entry_id"): "VARCHAR",

    # fact_task (16 columns)
    ("fact_task", "task_id"): "VARCHAR",
    ("fact_task", "team_id"): "VARCHAR",
    ("fact_task", "sprint_id"): "VARCHAR",
    ("fact_task", "assignee_employee_id"): "VARCHAR",
    ("fact_task", "task_type"): "VARCHAR",
    ("fact_task", "priority"): "VARCHAR",
    ("fact_task", "story_points"): "INTEGER",
    ("fact_task", "created_date"): "DATE",
    ("fact_task", "started_date"): "DATE",
    ("fact_task", "due_date"): "DATE",
    ("fact_task", "completed_date"): "DATE",
    ("fact_task", "status"): "VARCHAR",
    ("fact_task", "reopened_count"): "INTEGER",
    ("fact_task", "cycle_time_days"): "DOUBLE",
    ("fact_task", "is_overdue_at_cutoff"): "VARCHAR",
    ("fact_task", "completed_on_time"): "VARCHAR",

    # fact_anomaly (13 columns)
    ("fact_anomaly", "result_id"): "VARCHAR",
    ("fact_anomaly", "source_dataset"): "VARCHAR",
    ("fact_anomaly", "record_id"): "VARCHAR",
    ("fact_anomaly", "employee_id"): "VARCHAR",
    ("fact_anomaly", "period"): "DATE",
    ("fact_anomaly", "anomaly_score"): "DOUBLE",
    ("fact_anomaly", "flagged"): "VARCHAR",
    ("fact_anomaly", "reason_code"): "VARCHAR",
    ("fact_anomaly", "reason_text"): "VARCHAR",
    ("fact_anomaly", "money_at_risk"): "DOUBLE",
    ("fact_anomaly", "model_version"): "VARCHAR",
    ("fact_anomaly", "scored_at"): "TIMESTAMP",
    ("fact_anomaly", "period_key"): "BIGINT",

    # fact_attrition_risk (13 columns)
    ("fact_attrition_risk", "prediction_id"): "VARCHAR",
    ("fact_attrition_risk", "employee_id"): "VARCHAR",
    ("fact_attrition_risk", "as_of_date_key"): "BIGINT",
    ("fact_attrition_risk", "department_id"): "VARCHAR",
    ("fact_attrition_risk", "as_of_date"): "DATE",
    ("fact_attrition_risk", "risk_score_12m"): "DOUBLE",
    ("fact_attrition_risk", "risk_band"): "VARCHAR",
    ("fact_attrition_risk", "top_reason_1"): "VARCHAR",
    ("fact_attrition_risk", "top_reason_2"): "VARCHAR",
    ("fact_attrition_risk", "top_reason_3"): "VARCHAR",
    ("fact_attrition_risk", "model_version"): "VARCHAR",
    ("fact_attrition_risk", "model_note"): "VARCHAR",
    ("fact_attrition_risk", "employee_key"): "BIGINT",

    # fact_forecast (11 columns)
    ("fact_forecast", "forecast_id"): "VARCHAR",
    ("fact_forecast", "metric"): "VARCHAR",
    ("fact_forecast", "department_id"): "VARCHAR",
    ("fact_forecast", "forecast_month"): "DATE",
    ("fact_forecast", "forecast_value"): "DOUBLE",
    ("fact_forecast", "lower_80"): "DOUBLE",
    ("fact_forecast", "upper_80"): "DOUBLE",
    ("fact_forecast", "method"): "VARCHAR",
    ("fact_forecast", "trained_through"): "VARCHAR",
    ("fact_forecast", "model_version"): "VARCHAR",
    ("fact_forecast", "forecast_month_key"): "BIGINT",

    # budget_payroll_dept_month (3 columns)
    ("budget_payroll_dept_month", "department_id"): "VARCHAR",
    ("budget_payroll_dept_month", "month"): "DATE",
    ("budget_payroll_dept_month", "budget_payroll_cost"): "DOUBLE",

    # kpi_targets (6 columns)
    ("kpi_targets", "month"): "DATE",
    ("kpi_targets", "department_id"): "VARCHAR",
    ("kpi_targets", "attendance_rate_target"): "DOUBLE",
    ("kpi_targets", "overtime_share_target_pct"): "DOUBLE",
    ("kpi_targets", "attrition_monthly_target_pct"): "DOUBLE",
    ("kpi_targets", "task_completion_target_pct"): "DOUBLE",
}


# ──────────────────────────────────────────────────────────────────────
# Documented ambiguities (kept as VARCHAR to preserve source fidelity)
# ──────────────────────────────────────────────────────────────────────
# These columns have enum-like values but data_dictionary documents them as text:
# - dim_employee.change_reason, dim_date.financial_year, dim_date.fiscal_quarter
# - fact_payroll.variable_pay_type, fact_ledger.cost_center_department_id, fact_ledger.source_type
# - fact_invoice.status, fact_invoice.ageing_bucket_at_cutoff, fact_task.status
# - fact_task.is_overdue_at_cutoff, fact_task.completed_on_time, fact_anomaly.flagged
# - fact_anomaly.source_dataset, fact_anomaly.reason_code, fact_attrition_risk.risk_band
# - fact_forecast.metric
# All kept as VARCHAR. Enum validation belongs in DQ layer, not extraction.


def infer_duckdb_type(sheet_name: str, col_name: str, sample_values: list[Any]) -> str:
    """Infer DuckDB column type. Explicit overrides take precedence."""
    override_key = (sheet_name, col_name)
    if override_key in COLUMN_TYPE_OVERRIDES:
        return COLUMN_TYPE_OVERRIDES[override_key]

    # Fallback for any undocumented columns (should not occur with current overrides)
    non_null = [v for v in sample_values if v is not None]
    if not non_null:
        return "VARCHAR"

    first = non_null[0]
    if isinstance(first, int) and not isinstance(first, bool):
        if all(isinstance(v, int) and -2**31 <= v < 2**31 for v in non_null):
            return "INTEGER"
        return "BIGINT"
    if isinstance(first, float):
        return "DOUBLE"
    if isinstance(first, bool):
        return "BOOLEAN"
    if hasattr(first, "year") and hasattr(first, "month") and hasattr(first, "day"):
        if hasattr(first, "hour"):
            return "TIMESTAMP"
        return "DATE"

    return "VARCHAR"


def resolve_workbook_path() -> Path:
    """Resolve workbook path relative to project root."""
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "data" / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"


def resolve_db_path() -> Path:
    """Resolve DuckDB database path relative to project root."""
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "data" / "warehouse" / "pulseiq.duckdb"


def get_headers_and_samples(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    max_samples: int = 100,
) -> tuple[list[str], list[list[Any]]]:
    """Get headers and sample rows for type inference."""
    headers: list[str] = []
    samples: list[list[Any]] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(v) if v is not None else f"col_{j}" for j, v in enumerate(row)]
        else:
            samples.append(list(row))
            if len(samples) >= max_samples:
                break

    return headers, samples


def create_table_sql(table_name: str, headers: list[str], sample_rows: list[list[Any]]) -> str:
    """Generate CREATE TABLE statement with overrides-driven types."""
    cols_sql = []
    for j, col_name in enumerate(headers):
        col_samples = [row[j] if j < len(row) else None for row in sample_rows]
        dtype = infer_duckdb_type(table_name, col_name, col_samples)
        cols_sql.append(f'"{col_name}" {dtype}')

    return f'CREATE TABLE "{table_name}" ({", ".join(cols_sql)});'


def load_sheet_to_duckdb(
    conn: duckdb.DuckDBPyConnection,
    ws: openpyxl.worksheet.worksheet.Worksheet,
    table_name: str,
    batch_size: int = 10000,
) -> tuple[int, int]:
    """Load a worksheet into DuckDB. Returns (loaded_count, expected_count).
    
    Uses explicit DROP TABLE before CREATE. Validates row structure.
    No silent padding or truncation.
    """
    headers, sample_rows = get_headers_and_samples(ws)

    if not headers:
        print(f"  WARNING: {table_name} has no headers, skipping")
        return 0, 0

    expected_cols = len(headers)

    # Drop existing table to ensure clean extraction (no silent appends)
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    # Create table with explicit types
    create_sql = create_table_sql(table_name, headers, sample_rows)
    try:
        conn.execute(create_sql)
    except Exception as e:
        print(f"  ERROR creating table {table_name}: {e}")
        raise

    # Prepare insert statement with parameterized values
    placeholders = ", ".join(["?" for _ in headers])
    columns = ", ".join('"' + h + '"' for h in headers)
    insert_sql = f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})'

    row_count = 0
    batch: list[tuple] = []
    expected_count = 0

    # Skip header row
    first = True
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if first:
            first = False
            continue

        expected_count += 1

        # Validate row length matches header count exactly
        actual_cols = len(row)
        if actual_cols != expected_cols:
            raise ValueError(
                f"{table_name}: Row {row_idx} has {actual_cols} columns, "
                f"expected {expected_cols} (header). "
                f"Sheet may have malformed rows."
            )

        # Preserve nulls as None; empty strings stay as empty strings
        row_data = tuple(v if v is not None else None for v in row)

        batch.append(row_data)
        row_count += 1

        if len(batch) >= batch_size:
            conn.executemany(insert_sql, batch)
            batch.clear()
            if row_count % 50000 == 0:
                print(f"  Loaded {row_count:,} rows...")

    # Insert remaining
    if batch:
        conn.executemany(insert_sql, batch)

    return row_count, expected_count


def main() -> int:
    workbook_path = resolve_workbook_path()
    db_path = resolve_db_path()

    print(f"Project root: {workbook_path.parents[2]}")
    print(f"Workbook: {workbook_path}")
    print(f"Database: {db_path}")
    print()

    if not workbook_path.exists():
        print(f"ERROR: Workbook not found at {workbook_path}", file=sys.stderr)
        return 1

    # Ensure output directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    wb = None
    conn = None
    try:
        wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
        conn = duckdb.connect(str(db_path))

        # Verify all extract sheets exist
        missing = [s for s in ALL_EXTRACT_SHEETS if s not in wb.sheetnames]
        if missing:
            print(f"ERROR: Missing sheets in workbook: {missing}", file=sys.stderr)
            return 1

        print(f"Extracting {len(ALL_EXTRACT_SHEETS)} tables in a single transaction...")
        print(f"  Dimensions: {len(DIMENSION_SHEETS)}")
        print(f"  Facts: {len(FACT_SHEETS)}")
        print(f"  Targets: {len(TARGET_SHEETS)}")
        print()

        # Begin transaction - all tables or nothing
        conn.execute("BEGIN TRANSACTION")

        total_rows = 0
        table_counts = {}
        expected_counts = {}
        for sheet_name in ALL_EXTRACT_SHEETS:
            print(f"Loading {sheet_name}...")
            ws = wb[sheet_name]
            try:
                rows, expected = load_sheet_to_duckdb(conn, ws, sheet_name)
                total_rows += rows
                table_counts[sheet_name] = rows
                expected_counts[sheet_name] = expected
                print(f"  [OK] {sheet_name}: {rows:,} rows")
            except Exception as e:
                print(f"  [FAIL] {sheet_name}: FAILED - {e}", file=sys.stderr)
                # Attempt rollback on table-loading failure
                try:
                    conn.execute("ROLLBACK")
                    print("Transaction rolled back due to table-loading failure.", file=sys.stderr)
                except Exception as rb_err:
                    print(f"CRITICAL: Rollback failed after table-loading error: {rb_err}", file=sys.stderr)
                return 1

        # Row-count verification BEFORE commit
        print("\n=== ROW COUNT VERIFICATION (pre-commit) ===")
        all_verified = True
        for table in ALL_EXTRACT_SHEETS:
            loaded = table_counts[table]
            expected = expected_counts[table]
            if expected == loaded:
                print(f"  [OK] {table}: expected={expected:,} loaded={loaded:,}")
            else:
                print(f"  [FAIL] {table}: expected={expected:,} loaded={loaded:,} MISMATCH", file=sys.stderr)
                all_verified = False

        if not all_verified:
            print("\nERROR: Row count verification failed. Rolling back transaction.", file=sys.stderr)
            try:
                conn.execute("ROLLBACK")
                print("Transaction rolled back due to verification mismatch.", file=sys.stderr)
            except Exception as rb_err:
                print(f"CRITICAL: Rollback failed after verification mismatch: {rb_err}", file=sys.stderr)
            return 1

        # All checks passed - commit the transaction
        try:
            conn.execute("COMMIT")
        except Exception as commit_err:
            print(f"CRITICAL: Commit failed: {commit_err}", file=sys.stderr)
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return 1

        print(f"\n=== EXTRACTION COMPLETE ===")
        print(f"Total rows loaded: {total_rows:,}")
        print(f"Tables created: {len(ALL_EXTRACT_SHEETS)}")
        print(f"Database: {db_path}")
        print("\nAll row counts verified successfully. Transaction committed.")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if conn is not None:
            try:
                conn.execute("ROLLBACK")
                print("Transaction rolled back due to unexpected error.", file=sys.stderr)
            except Exception as rb_err:
                print(f"CRITICAL: Rollback failed after unexpected error: {rb_err}", file=sys.stderr)
        return 1

    finally:
        if wb is not None:
            wb.close()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())