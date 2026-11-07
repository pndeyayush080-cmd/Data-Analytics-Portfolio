
from pathlib import Path
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)
OUTPUT_FOLDER = PROJECT_ROOT / "data" / "raw" / "extracted"

# HR-related source sheets for Task 1
SHEETS_TO_EXTRACT = [
    "dim_employee",
    "dim_department",
    "dim_role",
    "dim_date",
    "dim_leave_type",
    "fact_payroll",
    "fact_attendance_monthly",
    "fact_leave",
    "fact_headcount_monthly",
    "fact_ledger",
    "fact_invoice",
    "fact_expense",
    "fact_task",
]

def main():
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source workbook not found: {SOURCE_FILE}"
        )

    print("Starting data extraction...")

    for sheet_name in SHEETS_TO_EXTRACT:
        df = pd.read_excel(
            SOURCE_FILE,
            sheet_name=sheet_name
        )

        output_file = OUTPUT_FOLDER / f"{sheet_name}.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")

        print(
            f"{sheet_name}: "
            f"{len(df)} rows extracted -> {output_file.name}"
        )

    print("\nExtraction completed successfully.")

if __name__ == "__main__":
    main()
