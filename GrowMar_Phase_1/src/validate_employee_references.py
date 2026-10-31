
from pathlib import Path
import pandas as pd

# Project root folder
project_root = Path(__file__).resolve().parent.parent

# Input files
payroll_file = (
    project_root
    / "data"
    / "clean"
    / "fact_payroll.csv"
)

employee_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "dim_employee.csv"
)

# Load data
payroll = pd.read_csv(payroll_file, dtype=str)
employees = pd.read_csv(employee_file, dtype=str)

# Get all valid employee IDs
valid_employee_ids = set(
    employees["employee_id"].dropna().str.strip()
)

# Find payroll rows with missing or unknown employee IDs
payroll_employee_ids = payroll["employee_id"].str.strip()

orphan_mask = (
    payroll_employee_ids.isna()
    | ~payroll_employee_ids.isin(valid_employee_ids)
)

orphans = payroll[orphan_mask].copy()

# Save results
rejected_folder = project_root / "data" / "rejected"
rejected_folder.mkdir(parents=True, exist_ok=True)

orphans.to_csv(
    rejected_folder / "payroll_orphan_employees.csv",
    index=False
)

# Display validation summary
print("EMPLOYEE REFERENCE VALIDATION")
print("=" * 45)
print(f"Payroll rows checked: {len(payroll)}")
print(f"Valid employee IDs: {len(valid_employee_ids)}")
print(f"Orphan payroll rows: {len(orphans)}")

if not orphans.empty:
    print("\nOrphan employee IDs:")
    print(orphans["employee_id"].tolist())
else:
    print("\nAll payroll employee IDs exist in dim_employee.")
