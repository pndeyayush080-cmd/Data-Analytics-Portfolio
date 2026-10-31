
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FOLDER = PROJECT_ROOT / "data" / "raw" / "extracted"

ATTENDANCE_FILE = DATA_FOLDER / "fact_attendance_monthly.csv"
EMPLOYEE_FILE = DATA_FOLDER / "dim_employee.csv"


def main():
    attendance = pd.read_csv(ATTENDANCE_FILE)
    employees = pd.read_csv(EMPLOYEE_FILE)

    # Use the current employee record for the initial check
    current_employees = employees[
        employees["is_current"].astype(str).str.upper().isin(["Y", "TRUE", "1"])
    ].copy()

    current_employees["exit_date"] = pd.to_datetime(
        current_employees["exit_date"],
        errors="coerce"
    )

    attendance["period_end_date"] = pd.to_datetime(
        attendance["period_end_date"],
        errors="coerce"
    )

    checked = attendance.merge(
        current_employees[["employee_id", "exit_date"]],
        on="employee_id",
        how="left"
    )

    issue_mask = (
        checked["exit_date"].notna()
        & (
            checked["period_end_date"].dt.to_period("M")
            > checked["exit_date"].dt.to_period("M")
        )
    )

    issues = checked.loc[issue_mask]

    print("ATTENDANCE AFTER EXIT CHECK")
    print("=" * 45)
    print(f"Attendance rows checked: {len(attendance)}")
    print(f"Rows flagged for review: {len(issues)}")

    if issues.empty:
        print("No rows flagged by this initial check.")
    else:
        print(
            issues[
                ["attendance_fact_id", "employee_id", "period_end_date", "exit_date"]
            ].head(20).to_string(index=False)
        )


if __name__ == "__main__":
    main()
