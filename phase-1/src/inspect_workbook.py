
from pathlib import Path
from openpyxl import load_workbook

# Locate the Excel workbook
project_root = Path(__file__).resolve().parent.parent
raw_folder = project_root / "data" / "raw"
excel_file = raw_folder / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"

print("Opening Excel workbook...")

# Read workbook without modifying it
workbook = load_workbook(
    filename=excel_file,
    read_only=True,
    data_only=True
)

print("\nWORKBOOK SUMMARY")
print("=" * 50)

for sheet in workbook.worksheets:
    print(f"\nSheet name: {sheet.title}")
    print(f"Rows: {sheet.max_row}")
    print(f"Columns: {sheet.max_column}")

    # Display the column headers
    headers = next(
        sheet.iter_rows(min_row=1, max_row=1, values_only=True),
        ()
    )

    print("Headers:")
    print(list(headers))

workbook.close()
print("\nWorkbook inspection completed.")
