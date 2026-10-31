
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
    excel_file,
    read_only=True,
    data_only=True
)

sheet = workbook["data_contracts"]

print("DATA CONTRACTS")
print("=" * 70)

for row in sheet.iter_rows(values_only=True):
    print(row)

workbook.close()
