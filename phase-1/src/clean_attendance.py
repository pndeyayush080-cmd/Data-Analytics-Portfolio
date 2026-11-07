
from pathlib import Path
import pandas as pd

# Project folders
project_root = Path(__file__).resolve().parent.parent

raw_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "fact_attendance_monthly.csv"
)

employee_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "dim_employee.csv"
)

clean_folder = project_root / "data" / "clean"
rejected_folder = project_root / "data" / "rejected"

clean_folder.mkdir(parents=True, exist_ok=True)
rejected_folder.mkdir(parents=True, exist_ok=True)

# Load attendance and employee data
attendance = pd.read_csv(raw_file, dtype=str)
employees = pd.read_csv(employee_file, dtype=str)

# Convert dates
attendance["period_end_date"] = pd.to_datetime(
    attendance["period_end_date"], errors="coerce"
)

employees["exit_date"] = pd.to_datetime(
    employees["exit_date"], errors="coerce"
)

# Use each employee's current record
current_employees = employees[
    employees["is_current"].str.upper().isin(["Y", "TRUE", "1"])
].copy()

# Keep the exit date for each employee
employee_exit_dates = current_employees[
    ["employee_id", "exit_date"]
].drop_duplicates(subset=["employee_id"])

# Match attendance with employee records
checked = attendance.merge(
    employee_exit_dates,
    on="employee_id",
    how="left",
    validate="many_to_one"
)

# Identify attendance recorded after the employee's exit month
attendance_month = checked["period_end_date"].dt.to_period("M")
exit_month = checked["exit_date"].dt.to_period("M")

invalid_mask = (
    checked["exit_date"].notna()
    & (attendance_month > exit_month)
)

rejected = checked[invalid_mask].copy()
clean = checked[~invalid_mask].copy()

# Remove the extra exit_date column before saving
rejected = rejected.drop(columns=["exit_date"])
clean = clean.drop(columns=["exit_date"])

rejected["rejection_reason"] = (
    "Attendance after employee exit month; DQ-01"
)

# Save outputs
clean.to_csv(
    clean_folder / "fact_attendance_monthly.csv",
    index=False
)

rejected.to_csv(
    rejected_folder / "fact_attendance_monthly_rejected.csv",
    index=False
)

# Report results
print("ATTENDANCE CLEANING SUMMARY")
print("=" * 45)
print(f"Input rows: {len(attendance)}")
print(f"Clean rows: {len(clean)}")
print(f"Rejected rows: {len(rejected)}")
print(f"Combined rows: {len(clean) + len(rejected)}")
print("\nRejected record IDs:")
print(rejected["attendance_fact_id"].tolist())
