
from pathlib import Path
import pandas as pd

project_root = Path(__file__).resolve().parent.parent

payroll_file = (
    project_root
    / "data"
    / "clean"
    / "fact_payroll.csv"
)

target_record_ids = {"PI-X0003", "PI-X0004"}

payroll = pd.read_csv(payroll_file, dtype=str)

print("DQ-03 ORPHAN PAYROLL VERIFICATION")
print("=" * 55)

record_id_column = "payroll_item_id"

if record_id_column not in payroll.columns:
    print("Column not found:", record_id_column)
    print("Available columns:")
    print(payroll.columns.tolist())
else:
    affected = payroll[
        payroll[record_id_column].isin(target_record_ids)
    ]

    print("Matching records:", len(affected))

    if not affected.empty:
        print(
            affected[
                [record_id_column, "employee_id", "run_id"]
            ].to_string(index=False)
        )

    print("\nAll payroll employee IDs involved in DQ-03:")
    print(
        payroll.loc[
            payroll[record_id_column].isin(target_record_ids),
            "employee_id"
        ].tolist()
    )
