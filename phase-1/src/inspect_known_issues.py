
from pathlib import Path
from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXCEL_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)

workbook = load_workbook(
    EXCEL_FILE,
    read_only=True,
    data_only=True
)

sheet = workbook["dq_known_issues"]

print("KNOWN DATA-QUALITY ISSUES")
print("=" * 70)

headers = next(sheet.iter_rows(values_only=True))
print(headers)

for row in sheet.iter_rows(min_row=2, values_only=True):
    row_text = " ".join(str(value) for value in row if value is not None)

    if any(record_id in row_text for record_id in [
        "PI-004059",
        "PI-X0001",
        "PI-000761",
        "PI-X0002",
    ]):
        print(row)

workbook.close()
