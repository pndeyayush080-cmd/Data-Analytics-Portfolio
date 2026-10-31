
from pathlib import Path
import pandas as pd

# Project root
project_root = Path(__file__).resolve().parent.parent

# Input: payroll after duplicate cleaning
payroll_file = (
    project_root
    / "data"
    / "clean"
    / "fact_payroll.csv"
)

# Load payroll data
payroll = pd.read_csv(payroll_file, dtype=str)

# Officially documented DQ-03 records
orphan_record_ids = {"PI-X0003", "PI-X0004"}

# Identify records to reject
orphan_mask = payroll["payroll_item_id"].isin(
    orphan_record_ids
)

rejected = payroll[orphan_mask].copy()
clean = payroll[~orphan_mask].copy()

# Add rejection reason
rejected["rejection_reason"] = (
    "Orphan employee reference; DQ-03"
)

# Save outputs
clean_folder = project_root / "data" / "clean"
rejected_folder = project_root / "data" / "rejected"

clean_folder.mkdir(parents=True, exist_ok=True)
rejected_folder.mkdir(parents=True, exist_ok=True)

# Save the refined payroll dataset separately
clean.to_csv(
    clean_folder / "fact_payroll_validated.csv",
    index=False
)

rejected.to_csv(
    rejected_folder / "payroll_orphan_rejected.csv",
    index=False
)

# Summary
print("ORPHAN PAYROLL CLEANING SUMMARY")
print("=" * 45)
print(f"Input rows: {len(payroll)}")
print(f"Valid rows: {len(clean)}")
print(f"Rejected rows: {len(rejected)}")
print(f"Combined rows: {len(clean) + len(rejected)}")

print("\nRejected record IDs:")
print(rejected["payroll_item_id"].tolist())

print("\nRejected employee IDs:")
print(rejected["employee_id"].tolist())
