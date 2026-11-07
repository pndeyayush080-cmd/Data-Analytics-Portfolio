
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
raw_folder = project_root / "data" / "raw"

print("Checking raw data folder...")
print(f"Folder location: {raw_folder}")

excel_files = list(raw_folder.glob("*.xlsx")) + list(raw_folder.glob("*.xls"))

if excel_files:
    print("\nExcel files found:")
    for file in excel_files:
        print(file.name)
else:
    print("\nNo Excel files found in data/raw.")
    print("We need to place the source dataset here.")
