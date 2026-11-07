
from pathlib import Path
from openpyxl import load_workbook

project_root = Path(__file__).resolve().parent.parent
excel_file = (
    project_root
    / "data"
    / "raw"
    / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)

workbook = load_workbook(
    filename=excel_file,
    read_only=True,
    data_only=True
)

sheet = workbook["data_dictionary"]

print("DATA DICTIONARY — FIRST 20 ENTRIES")
print("=" * 60)

for row in sheet.iter_rows(
    min_row=1,
    max_row=21,
    values_only=True
):
    print(row)

workbook.close()
