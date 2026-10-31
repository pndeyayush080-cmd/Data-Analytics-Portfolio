
from pathlib import Path
import pandas as pd

# Project root
project_root = Path(__file__).resolve().parent.parent

# Input file
invoice_file = (
    project_root
    / "data"
    / "raw"
    / "extracted"
    / "fact_invoice.csv"
)

# Load invoice data
invoices = pd.read_csv(invoice_file)

# Convert monetary columns to numeric values
amount_columns = [
    "subtotal",
    "gst_amount",
    "total_amount",
    "amount_paid",
    "balance_due",
]

for column in amount_columns:
    invoices[column] = pd.to_numeric(
        invoices[column], errors="coerce"
    )

# Apply documented DQ-05 checks
invalid_balance = invoices["balance_due"] < 0

overpaid = invoices["amount_paid"] > invoices["total_amount"]

arithmetic_mismatch = (
    (invoices["subtotal"] + invoices["gst_amount"]
     - invoices["total_amount"]).abs() > 0.01
)

# Combine all invoice validation failures
invalid_mask = (
    invalid_balance
    | overpaid
    | arithmetic_mismatch
)

invalid_invoices = invoices[invalid_mask].copy()

# Add reasons for each failure
def get_reasons(row):
    reasons = []

    if row["balance_due"] < 0:
        reasons.append("Negative balance due")

    if row["amount_paid"] > row["total_amount"]:
        reasons.append("Amount paid exceeds invoice total")

    if abs(
        row["subtotal"] + row["gst_amount"]
        - row["total_amount"]
    ) > 0.01:
        reasons.append("Invoice total arithmetic mismatch")

    return "; ".join(reasons)

invalid_invoices["rejection_reason"] = (
    invalid_invoices.apply(get_reasons, axis=1)
)

# Save validation results separately
output_folder = project_root / "data" / "rejected"
output_folder.mkdir(parents=True, exist_ok=True)

invalid_invoices.to_csv(
    output_folder / "invoice_validation_issues.csv",
    index=False
)

# Print summary
print("INVOICE VALIDATION SUMMARY")
print("=" * 45)
print(f"Total invoices checked: {len(invoices)}")
print(f"Flagged invoices: {len(invalid_invoices)}")
print(f"Valid invoices: {len(invoices) - len(invalid_invoices)}")

print("\nFlagged invoice details:")

if invalid_invoices.empty:
    print("No invoice validation issues found.")
else:
    print(
        invalid_invoices[
            [
                "invoice_id",
                "subtotal",
                "gst_amount",
                "total_amount",
                "amount_paid",
                "balance_due",
                "rejection_reason",
            ]
        ].to_string(index=False)
    )

print("\nResults saved to:")
print(output_folder / "invoice_validation_issues.csv")
