# Task 2 — Warehouse Validation Findings

**Status: complete with documented source-data limitations.** The warehouse was
built in the `warehouse` schema from the existing `raw` schema. No raw table
was modified, and no source record was deleted, rewritten, or assigned a
guessed relationship.

## Evidence summary

The final validation report is
[`../data/warehouse/task2_validation_report.json`](../data/warehouse/task2_validation_report.json).
It records the following results:

| Check | Result |
| --- | --- |
| Warehouse tables | 18 (7 dimensions, 11 facts) |
| Declared primary keys | 18 checked; 0 duplicate key groups; 0 null key rows |
| Row-count reconciliation | 18 of 18 tables reconcile to their raw source |
| Raw schema modified | No (`raw_schema_modified: false`) |
| Non-null orphan foreign keys | 38 |
| Null foreign keys | 6,032 |

## Investigated relationship exceptions

### Non-null orphan keys (38)

| Relationship | Rows | Finding | Treatment |
| --- | ---: | --- | --- |
| `fact_payroll.employee_key -> dim_employee` | 2 | `employee_key = -1` on payroll items `PI-X0003` (`EMP-9001`) and `PI-X0004` (`EMP-9002`) has no matching employee dimension version. | Kept as supplied and reported; not remapped. |
| `fact_forecast.forecast_month_key -> dim_date` | 36 | Forecast records for January–March 2027 fall outside the available date dimension. | Kept as supplied and reported; no dates fabricated. |

### Null foreign keys (6,032)

| Relationship | Rows | Finding | Treatment |
| --- | ---: | --- | --- |
| `fact_ledger.cost_center_department_id -> dim_department` | 5,688 | The department reference is null in the source. | Preserved as null. |
| `fact_task.assignee_employee_key -> dim_employee` | 313 | Task dates precede the available employee-history validity window, so no SCD Type 2 employee version can be resolved. | Preserved as null; the source task remains in the warehouse. |
| `fact_anomaly.employee_key -> dim_employee` | 31 | Anomaly periods precede the available employee-history validity window, so no SCD Type 2 employee version can be resolved. | Preserved as null; the source anomaly remains in the warehouse. |

All other declared relationships have zero null and zero orphan keys in the
final validation report.

## Modelling decisions

- `dim_employee` is retained as a Type 2 employee dimension and facts join it
  through `employee_key`.
- Task and anomaly records that supply only `employee_id` are resolved against
  their event date and the employee validity window. Unresolved rows are not
  dropped or guessed.
- Financial facts retain supplied source columns where no matching account,
  client, or vendor dimensions exist in the source data.
- Foreign keys are validated rather than enforced as database constraints,
  because enforcement would reject documented source records.

## Re-run

```powershell
.\.venv\Scripts\python.exe -B .\src\build_star_warehouse.py --replace
```

Use `--replace` only to deliberately rebuild the warehouse tables. The command
refreshes the warehouse and its evidence report; it does not modify `raw`.
