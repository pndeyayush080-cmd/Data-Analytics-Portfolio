# Task 1 contract-validation status

## Scope and safety

The Task 1 ETL reads `pulseiq.duckdb` in read-only mode. It writes accepted
and quarantine CSV files separately, so rejected source rows remain preserved.
This status record is based only on the project data contract, raw schema, and
project data. It does not use Validation Vault material.

## Open validations

| Contract field | Status | What the pipeline does | Evidence still required |
| --- | --- | --- | --- |
| `fact_anomaly.reason_code` | `UNVERIFIED` | Records the observed values in the run log but does not treat the observed set as an allowed-code list. | A published, versioned reason-code list and its owner. |
| `fact_anomaly.record_id` | `UNVERIFIED` | Reports match counts against the schema-based candidates `fact_attendance_monthly.attendance_fact_id` and `fact_payroll.payroll_item_id`. It does not reject rows based on those candidates. | An approved mapping from each `source_dataset` value to its physical source table and key. |
| `fact_anomaly.scored_at` | `UNVERIFIED` | Records the database column type. A timezone-less `TIMESTAMP` cannot independently establish that stored values are UTC. | Source-system or schema documentation that defines the timestamp timezone semantics. |
| `fact_task.is_overdue_at_cutoff` and `completed_on_time` | `UNVERIFIED` | Records observed flag values but does not recompute or reject the flags. | The formulas, inclusive/exclusive date handling, treatment of unfinished/cancelled work, and the cutoff timestamp/date. |

## How to close a gap

Add the authoritative evidence to the project documentation or data contract,
then change the matching entry in `src/run_etl_pipeline.py` from evidence-only
to an enforced validation. The rule should be versioned and attributable to a
data owner before it is used to quarantine rows.

## Audit output

Every run writes `data/etl/etl_run_log.json`. Its `contract_validation` object
contains the status, observed/candidate evidence, and the evidence needed for
each item. `contract_compliance` remains `PARTIAL` while any item is not
`VERIFIED`.
