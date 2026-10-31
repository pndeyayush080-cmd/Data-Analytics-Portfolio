
from pathlib import Path
import pandas as pd

# Project root
project_root = Path(__file__).resolve().parent.parent

# Input file
leave_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "fact_leave.csv"
)

# Load leave data
leave = pd.read_csv(leave_file, dtype=str)

# Convert dates
leave["start_date"] = pd.to_datetime(
    leave["start_date"], errors="coerce"
)

leave["end_date"] = pd.to_datetime(
    leave["end_date"], errors="coerce"
)

# Flag records where end date is earlier than start date
invalid_mask = (
    leave["start_date"].notna()
    & leave["end_date"].notna()
    & (leave["end_date"] < leave["start_date"])
)

invalid = leave[invalid_mask].copy()

# Add validation reason
invalid["rejection_reason"] = (
    "End date before start date; DQ-08"
)

# Save flagged records separately
output_folder = project_root / "data" / "rejected"
output_folder.mkdir(parents=True, exist_ok=True)

output_file = output_folder / "leave_validation_issues.csv"

invalid.to_csv(output_file, index=False)

# Summary
print("LEAVE DATE VALIDATION SUMMARY")
print("=" * 45)
print(f"Total leave records checked: {len(leave)}")
print(f"Valid date records: {len(leave) - len(invalid)}")
print(f"Flagged records: {len(invalid)}")

print("\nFlagged leave requests:")

if invalid.empty:
    print("No invalid leave date ranges found.")
else:
    print(
        invalid[
            [
                "leave_request_id",
                "start_date",
                "end_date",
                "status",
                "rejection_reason",
            ]
        ].to_string(index=False)
    )

print("\nResults saved to:")
print(output_file)
