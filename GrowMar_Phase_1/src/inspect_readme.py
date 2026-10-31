
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

sheet = workbook["README"]

for row in sheet.iter_rows(values_only=True):
    values = [str(value) for value in row if value is not None]
    if values:
        print(" | ".join(values))

workbook.close()
