
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT / "data" / "raw" / "extracted" / "fact_payroll.csv"
)
CLEAN_FOLDER = PROJECT_ROOT / "data" / "clean"
REJECTED_FOLDER = PROJECT_ROOT / "data" / "rejected"


def main():
    CLEAN_FOLDER.mkdir(parents=True, exist_ok=True)
    REJECTED_FOLDER.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_FILE)

    # Detect repeated employee + payroll run combinations
    duplicate_mask = df.duplicated(
        subset=["employee_id", "run_id"],
        keep="first"
    )

    rejected = df.loc[duplicate_mask].copy()
    clean = df.loc[~duplicate_mask].copy()

    # Document why each rejected row was rejected
    rejected["rejection_reason"] = (
        "Duplicate employee_id + run_id; DQ-C03"
    )

    # Save both outputs separately
    clean.to_csv(
        CLEAN_FOLDER / "fact_payroll.csv",
        index=False,
        encoding="utf-8-sig"
    )

    rejected.to_csv(
        REJECTED_FOLDER / "fact_payroll_rejected.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("PAYROLL CLEANING SUMMARY")
    print("=" * 45)
    print(f"Input rows: {len(df)}")
    print(f"Clean rows: {len(clean)}")
    print(f"Rejected rows: {len(rejected)}")
    print("\nRejected payroll item IDs:")
    print(rejected["payroll_item_id"].to_string(index=False))


if __name__ == "__main__":
    main()

from pathlib import Path
from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCEL_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)

TARGET_IDS = {
    "FA-X0001",
    "FA-X0002",
    "FA-X0003",
    "FA-X0004",
}

workbook = load_workbook(
    EXCEL_FILE,
    read_only=True,
    data_only=True
)

sheet = workbook["dq_known_issues"]

print("ATTENDANCE ISSUE VERIFICATION")
print("=" * 60)

for row in sheet.iter_rows(values_only=True):
    if any(record_id in str(value) for value in row for record_id in TARGET_IDS):
        print(row)

workbook.close()
