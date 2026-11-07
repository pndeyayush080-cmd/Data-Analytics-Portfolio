
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FOLDER = PROJECT_ROOT / "data" / "raw" / "extracted"

FILES_TO_PROFILE = [
    "dim_employee.csv",
    "fact_payroll.csv",
    "fact_attendance_monthly.csv",
    "fact_leave.csv",
    "fact_headcount_monthly.csv",
]

def main():
    for filename in FILES_TO_PROFILE:
        file_path = DATA_FOLDER / filename
        df = pd.read_csv(file_path)

        print("\n" + "=" * 60)
        print(f"DATASET: {filename}")
        print("=" * 60)

        print(f"Rows: {df.shape[0]}")
        print(f"Columns: {df.shape[1]}")
        print(f"Duplicate complete rows: {df.duplicated().sum()}")

        print("\nMissing values by column:")
        missing = df.isna().sum()
        missing = missing[missing > 0]

        if missing.empty:
            print("No missing values found.")
        else:
            print(missing.to_string())

        print("\nColumn data types:")
        print(df.dtypes.to_string())

if __name__ == "__main__":
    main()
