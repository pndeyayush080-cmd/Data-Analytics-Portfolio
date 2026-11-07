
from pathlib import Path
from openpyxl import load_workbook

project_root = Path(__file__).resolve().parent.parent
excel_file = (
    project_root
    / "data"
    / "raw"
    / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)

target_ids = {"FA-X0001", "FA-X0002", "FA-X0003", "FA-X0004"}

workbook = load_workbook(
    excel_file,
    read_only=True,
    data_only=True
)

sheet = workbook["dq_known_issues"]

print("ATTENDANCE ISSUE VERIFICATION")
print("=" * 60)

for row in sheet.iter_rows(values_only=True):
    if any(
        record_id in str(value)
        for value in row
        for record_id in target_ids
    ):
        print(row)

workbook.close()
