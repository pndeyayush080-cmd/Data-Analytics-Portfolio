# Task 2 — Star Schema Warehouse

## Scope

`src/build_star_warehouse.py` reads the existing `raw` schema and creates a
separate `warehouse` schema in `pulseiq.duckdb`. It never creates, updates, or
deletes a `raw` table. The warehouse contains the seven dimensions and eleven
facts available in the loaded raw schema.

The project does not contain raw account, client, or vendor dimensions, so the
financial facts retain their source columns and are not joined to dimensions
that have not been supplied. No substitute dimensions are invented.

## Grain and primary keys

| Table | Grain | Primary key |
| --- | --- | --- |
| `dim_date` | One calendar date | `date_key` |
| `dim_department` | One department | `department_id` |
| `dim_employee` | One employee SCD Type 2 version | `employee_key` |
| `dim_leave_type` | One leave type | `leave_type_code` |
| `dim_role` | One role | `role_id` |
| `dim_sprint` | One sprint | `sprint_id` |
| `dim_team` | One team | `team_id` |
| `fact_payroll` | One payroll line | `payroll_item_id` |
| `fact_attendance_monthly` | One employee-month attendance row | `attendance_fact_id` |
| `fact_leave` | One leave request | `leave_request_id` |
| `fact_headcount_monthly` | One department-month | `date_key`, `department_id` |
| `fact_ledger` | One journal line | `line_id` |
| `fact_invoice` | One invoice | `invoice_id` |
| `fact_expense` | One expense bill | `expense_id` |
| `fact_forecast` | One forecast record | `forecast_id` |
| `fact_attrition_risk` | One prediction | `prediction_id` |
| `fact_task` | One task | `task_id` |
| `fact_anomaly` | One anomaly result | `result_id` |

## Employee-key rule

The warehouse facts that use employees join to `dim_employee` through
`employee_key`, not `employee_id`:

- Payroll, attendance, leave, and attrition risk retain their supplied
  `employee_key` and omit the raw `employee_id` from the warehouse fact.
- Task and anomaly sources supply only an employee ID. The build resolves a
  surrogate key against the SCD validity window at `created_date` (task) or
  `period` (anomaly), then omits the source employee ID from the warehouse
  fact. A missing resolution is preserved as a null key and reported as a
  data-quality issue; no source row is discarded or guessed.

## Diagram

The standalone, renderable diagram is available at
[`task2_star_schema.svg`](task2_star_schema.svg). The relationship summary is
also shown below for text-only viewers.

```text
                       dim_date
                    /     |      \\
  dim_department -- fact_payroll -- dim_employee (employee_key)
          |        fact_attendance_monthly       |
          |        fact_headcount_monthly        |
          |        fact_expense                  +-- fact_leave
          |        fact_ledger                   +-- fact_attrition_risk
          |        fact_forecast                 +-- fact_task
          |        fact_attrition_risk           +-- fact_anomaly
          |                                      
       dim_role -- fact_payroll
 dim_leave_type -- fact_leave
      dim_team -- fact_task -- dim_sprint
```

## Validation performed

Each build checks every declared primary key for nulls and duplicates, records
raw-versus-warehouse row counts for every table, and checks all relationships
that have an available dimension. The report distinguishes a null foreign key
from a non-null foreign key that does not exist in its dimension. It writes the results to
`data/warehouse/task2_validation_report.json`.

The script intentionally does not add enforced foreign-key constraints: the
raw dataset contains data-quality exceptions, and enforcing them would reject
or alter rows. The checks report those exceptions while keeping source counts
reconciled.

## Run

```powershell
.\.venv\Scripts\python.exe -B .\src\build_star_warehouse.py
```

Use `--replace` only when deliberately rebuilding existing warehouse tables.
