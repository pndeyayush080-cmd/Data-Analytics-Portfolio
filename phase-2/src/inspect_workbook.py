"""Workbook inspection script using openpyxl (read-only)."""

from pathlib import Path
import sys

import openpyxl


SENSITIVE_COLUMNS_FACT_PAYROLL = {
    "basic",
    "hra",
    "conveyance",
    "medical",
    "special_allowance",
    "earned_fixed_pay",
    "overtime_pay",
    "variable_pay",
    "gross_pay",
    "pf_employee",
    "esi_employee",
    "professional_tax",
    "tds",
    "other_deductions",
    "total_deductions",
    "net_pay",
    "pf_employer",
    "esi_employer",
    "employer_cost",
}

SENSITIVE_COLUMNS_DIM_EMPLOYEE = {"full_name", "date_of_birth"}

TARGET_SHEETS = [
    "dim_employee",
    "dim_date",
    "fact_payroll",
    "fact_ledger",
    "fact_attendance_monthly",
    "fact_headcount_monthly",
]


def resolve_workbook_path() -> Path:
    """Resolve workbook path relative to project root."""
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "data" / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"


def get_dimensions(ws: openpyxl.worksheet.worksheet.Worksheet) -> tuple[int, int]:
    """Get row and column count for a read-only worksheet."""
    rows = 0
    cols = 0
    for row in ws.iter_rows():
        rows += 1
        if rows == 1:
            cols = len([c for c in row if c.value is not None])
    return rows, cols


def filter_sensitive_headers(headers: list[str], sheet_name: str) -> list[str]:
    """Return headers with sensitive ones marked."""
    if sheet_name == "fact_payroll":
        return [
            f"{h} [SENSITIVE]" if h in SENSITIVE_COLUMNS_FACT_PAYROLL else h
            for h in headers
        ]
    if sheet_name == "dim_employee":
        return [
            f"{h} [SENSITIVE]" if h in SENSITIVE_COLUMNS_DIM_EMPLOYEE else h
            for h in headers
        ]
    return headers


def main() -> int:
    workbook_path = resolve_workbook_path()

    print(f"Project root: {workbook_path.parents[2]}")
    print(f"Workbook: {workbook_path}")
    print()

    if not workbook_path.exists():
        print(f"ERROR: Workbook not found at {workbook_path}", file=sys.stderr)
        return 1

    wb = None
    try:
        wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    except Exception as e:
        print(f"ERROR: Failed to open workbook: {e}", file=sys.stderr)
        return 1

    try:
        # All sheet names, row counts, column counts
        print("=== ALL WORKSHEETS ===")
        for ws in wb.worksheets:
            rows, cols = get_dimensions(ws)
            print(f"  {ws.title:<40}  rows={rows:>6}  cols={cols:>3}")

        print()

        # Headers for target sheets
        print("=== TARGET SHEET HEADERS ===")
        for sheet_name in TARGET_SHEETS:
            if sheet_name not in wb.sheetnames:
                print(f"\n--- {sheet_name} ---")
                print("  NOT FOUND")
                continue

            ws = wb[sheet_name]
            headers = []
            for row in ws.iter_rows(max_row=1, values_only=True):
                if row:
                    headers = [str(v) if v is not None else "" for v in row]
                break

            filtered = filter_sensitive_headers(headers, sheet_name)
            print(f"\n--- {sheet_name} ({len(filtered)} columns) ---")
            for i, h in enumerate(filtered, 1):
                print(f"  {i:>2}. {h}")

        print("\n=== INSPECTION COMPLETE ===")
        return 0

    finally:
        if wb is not None:
            wb.close()


if __name__ == "__main__":
    sys.exit(main())