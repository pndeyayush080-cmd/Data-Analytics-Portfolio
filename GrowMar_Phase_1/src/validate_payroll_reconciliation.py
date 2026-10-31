
from pathlib import Path
import pandas as pd

# Project root
project_root = Path(__file__).resolve().parent.parent

# Input files
payroll_file = (
    project_root / "data" / "clean" / "fact_payroll_validated.csv"
)

ledger_file = (
    project_root / "data" / "raw" / "extracted" / "fact_ledger.csv"
)

answer_key_file = (
    project_root / "data" / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
)

# Load data
payroll = pd.read_csv(payroll_file)
ledger = pd.read_csv(ledger_file)
answer_key = pd.read_excel(
    answer_key_file,
    sheet_name="reconciliation_answer_key"
)

# Convert dates and amounts
payroll["period_end_date"] = pd.to_datetime(
    payroll["period_end_date"], errors="coerce"
)
ledger["entry_date"] = pd.to_datetime(
    ledger["entry_date"], errors="coerce"
)

payroll["employer_cost"] = pd.to_numeric(
    payroll["employer_cost"], errors="coerce"
)
ledger["signed_amount_debit_positive"] = pd.to_numeric(
    ledger["signed_amount_debit_positive"], errors="coerce"
)

# Monthly payroll employer cost
payroll["month"] = (
    payroll["period_end_date"].dt.to_period("M").dt.to_timestamp()
)

monthly_payroll = (
    payroll.groupby("month", as_index=False)["employer_cost"]
    .sum()
    .rename(columns={"employer_cost": "payroll_employer_cost"})
)

# Salary-related ledger expense accounts
salary_accounts = ["5001", "5002", "5003", "5004", "5005"]

ledger["account_code"] = ledger["account_code"].astype(str).str.replace(
    r"\.0$", "", regex=True
)

salary_ledger = ledger[
    ledger["account_code"].isin(salary_accounts)
].copy()

salary_ledger["month"] = (
    salary_ledger["entry_date"].dt.to_period("M").dt.to_timestamp()
)

monthly_ledger = (
    salary_ledger.groupby("month", as_index=False)[
        "signed_amount_debit_positive"
    ]
    .sum()
    .rename(
        columns={
            "signed_amount_debit_positive":
                "ledger_salary_related_expense"
        }
    )
)

# Combine monthly results
result = monthly_payroll.merge(
    monthly_ledger, on="month", how="outer"
)

# Compare with official answer key
answer_key["month"] = pd.to_datetime(answer_key["month"])

result = result.merge(
    answer_key[
        ["month", "payroll_employer_cost",
         "ledger_salary_related_expense",
         "payroll_vs_ledger_difference"]
    ],
    on="month",
    how="outer",
    suffixes=("_calculated", "_official")
)

result["calculated_difference"] = (
    result["ledger_salary_related_expense_calculated"]
    - result["payroll_employer_cost_calculated"]
)
# Flag differences greater than one paisa
result["reconciliation_status"] = result[
    "calculated_difference"
].apply(
    lambda difference:
        "MISMATCH"
        if pd.notna(difference) and abs(difference) > 0.01
        else "MATCH"
)

print("\nRECONCILIATION STATUS")
print("=" * 40)

print(
    result[
        ["month", "calculated_difference", "reconciliation_status"]
    ].to_string(index=False)
)

print("\nMismatch months:")
print(
    result.loc[
        result["reconciliation_status"] == "MISMATCH",
        ["month", "calculated_difference"]
    ].to_string(index=False)
)
 

# Save reconciliation report
report_folder = project_root / "data" / "clean"
report_folder.mkdir(parents=True, exist_ok=True)

result.to_csv(
    report_folder / "payroll_reconciliation_report.csv",
    index=False
)

print("PAYROLL RECONCILIATION REPORT")
print("=" * 55)
print(result.to_string(index=False))
print("\nReport saved to:")
print(report_folder / "payroll_reconciliation_report.csv")
