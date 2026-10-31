
from pathlib import Path
import pandas as pd

# Project root
project_root = Path(__file__).resolve().parent.parent

# Input file
expense_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "fact_expense.csv"
)

# Load expense data
expenses = pd.read_csv(expense_file)

# Convert amount columns to numeric
amount_columns = [
    "amount_excl_gst",
    "gst_amount",
    "total_amount",
]

for column in amount_columns:
    expenses[column] = pd.to_numeric(
        expenses[column], errors="coerce"
    )

# Calculate expected total
expenses["expected_total"] = (
    expenses["amount_excl_gst"] + expenses["gst_amount"]
)

# Flag differences greater than one paisa
invalid_mask = (
    (expenses["expected_total"] - expenses["total_amount"]).abs()
    > 0.01
)

invalid = expenses[invalid_mask].copy()

# Calculate difference
invalid["difference"] = (
    invalid["total_amount"] - invalid["expected_total"]
)

invalid["rejection_reason"] = (
    "Total amount differs from amount excluding GST + GST; DQ-10"
)

# Save flagged records separately
output_folder = project_root / "data" / "rejected"
output_folder.mkdir(parents=True, exist_ok=True)

output_file = output_folder / "expense_validation_issues.csv"

invalid.to_csv(output_file, index=False)

# Print summary
print("EXPENSE VALIDATION SUMMARY")
print("=" * 45)
print(f"Total expenses checked: {len(expenses)}")
print(f"Valid expenses: {len(expenses) - len(invalid)}")
print(f"Flagged expenses: {len(invalid)}")

print("\nFlagged expense details:")

if invalid.empty:
    print("No expense total mismatches found.")
else:
    print(
        invalid[
            [
                "expense_id",
                "amount_excl_gst",
                "gst_amount",
                "expected_total",
                "total_amount",
                "difference",
                "rejection_reason",
            ]
        ].to_string(index=False)
    )

print("\nResults saved to:")
print(output_file)
