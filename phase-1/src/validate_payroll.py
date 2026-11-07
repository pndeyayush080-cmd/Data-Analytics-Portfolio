
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAYROLL_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "extracted"
    / "fact_payroll.csv"
)


def main():
    df = pd.read_csv(PAYROLL_FILE)

    print("PAYROLL KEY VALIDATION")
    print("=" * 50)

    duplicate_mask = df.duplicated(
        subset=["employee_id", "run_id"],
        keep=False
    )

    duplicates = df.loc[duplicate_mask].sort_values(
        ["employee_id", "run_id"]
    )

    print(f"Total payroll rows: {len(df)}")
    print(f"Rows involved in duplicate keys: {len(duplicates)}")

    if duplicates.empty:
        print("PASS: No duplicate employee_id + run_id combinations.")
    else:
        print("FAIL: Duplicate payroll keys found.")
        print("\nComplete duplicate records for comparison:")
        print(duplicates.to_string(index=False))


if __name__ == "__main__":
    main()
