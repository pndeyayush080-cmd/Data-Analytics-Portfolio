# Task 4 — Governed Metric Layer Report

## Completion status

**Complete.** The DuckDB file now contains 28 official metric views and the
`metric_catalog` view. The SQL definitions are in
`metric_layer/metric_views.sql`. This task did not run ETL and did not modify
raw inputs, raw tables, warehouse tables, or Task 1–3 code and evidence.

## Catalog and governance

`metric_catalog` contains **28 rows**, **28 distinct metric IDs**, and **28
distinct view names**. It records each metric's ID, view name, business
definition, source, owner, grain, and minimum group size from the supplied
metric dictionary.

The duplicate M25–M28 declarations were removed so every official metric has
one authoritative SQL definition.

## Formula and privacy decisions

- **M01–M03:** Department-month groups with ending headcount below the
  dictionary's minimum of 5 are suppressed. This produces a common,
  manager-safe population rule for headcount, hires, and exits.
- **M04:** Uses the supplied official formula, `exits / headcount_start *
  100`, and is suppressed below 10 starting employees. This is intentionally
  different from an ending- or average-headcount denominator.
- **M10:** Requires at least 5 distinct paid employees in the
  department-month before showing employer cost or cost per head.
- **M20:** Is calculated at each available month end from the accounts
  receivable control account (`1100`): closing receivables are the cumulative
  invoice debits and payment credits through the report date. The denominator
  is invoice postings to that account during the previous 90 calendar days,
  which are GST-inclusive credit sales. Only complete 90-day windows are
  shown. This avoids the former errors of using the first day of a month,
  multiplying monthly revenue through an invoice join, and treating a
  current `balance_due` as a historical month-end balance.
- **M28:** Future forecasts are retained with
  `NOT_YET_EVALUABLE`; no error rate is fabricated until a matching actual is
  available.

Employee-grain payroll views (M07–M09 and M15) remain operational payroll
metrics as specified in the dictionary. They must not be used as manager
aggregate outputs; manager-facing group views enforce their dictionary
thresholds.

## View validation results

| Metric view | Rows |
| --- | ---: |
| M01 `m01_headcount` | 810 |
| M02 `m02_hires` | 810 |
| M03 `m03_exits` | 810 |
| M04 `m04_attrition_rate_monthly` | 646 |
| M05 `m05_attrition_rate_rolling_12m` | 539 |
| M06 `m06_voluntary_attrition_rate` | 539 |
| M07 `m07_gross_pay` | 7,342 |
| M08 `m08_net_pay` | 7,342 |
| M09 `m09_payroll_cost` | 7,342 |
| M10 `m10_cost_per_head` | 180 |
| M11 `m11_overtime_share` | 180 |
| M12 `m12_variable_pay_share` | 180 |
| M13 `m13_attendance_rate` | 180 |
| M14 `m14_late_arrival_rate` | 180 |
| M15 `m15_leave_without_pay_days` | 7,342 |
| M16 `m16_revenue` | 18 |
| M17 `m17_net_profit` | 18 |
| M18 `m18_operating_margin` | 18 |
| M19 `m19_payroll_pct_revenue` | 18 |
| M20 `m20_dso` | 16 |
| M21 `m21_overdue_receivables` | 105 |
| M22 `m22_task_completion_rate` | 608 |
| M23 `m23_on_time_delivery_rate` | 608 |
| M24 `m24_velocity` | 608 |
| M25 `m25_average_cycle_time` | 608 |
| M26 `m26_anomaly_flag_rate` | 36 |
| M27 `m27_high_risk_share` | 10 |
| M28 `m28_forecast_mape` | 66 |

M28 status: 66 `NOT_YET_EVALUABLE`, 0 evaluable rows. Forecast months start
after the supplied actual headcount months, so this is the correct result.

## Independent hand-checks

All comparisons below reproduced the view result directly from the raw
source formula.

| Metric | Slice | Independent calculation | View result | Match |
| --- | --- | ---: | ---: | --- |
| M01 Headcount | D01, 2020-01-01 | source `headcount_end` = 60 | 60 | Yes |
| M02 Hires | D01, 2020-01-01 | source `hires` = 1 | 1 | Yes |
| M03 Exits | D01, 2020-01-01 | source `exits` = 2 | 2 | Yes |
| M04 Monthly attrition | D01, 2020-01-01 | `100 * 2 / 61` = 3.28% | 3.28% | Yes |
| M10 Cost per head | D01, 2025-04-30 | raw employer-cost sum / 145 distinct employees = 147,780.06 | 147,780.06 | Yes |
| M20 DSO | 2026-09-30 | `90 * 139,394,278 / 261,376,644` = 48.00 days | 48.00 days | Yes |

## Privacy validation

The following post-view checks each returned zero rows:

| Check | Disallowed rows |
| --- | ---: |
| M01 row with headcount below 5 | 0 |
| M02 row whose source ending headcount is below 5 | 0 |
| M03 row whose source ending headcount is below 5 | 0 |
| M10 row with fewer than 5 paid employees | 0 |

## Known data-quality context

Task 3's gatekeeper remains blocked for existing raw-data controls. This
metric task exposes governed definitions and does not delete, reclassify, or
silently repair those source records. In particular, finance and payroll
metrics should be used with the Task 3 reconciliation and duplicate-payroll
findings in mind until their owners resolve the source issues.
