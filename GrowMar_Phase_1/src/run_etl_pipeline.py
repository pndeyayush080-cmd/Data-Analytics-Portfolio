from pathlib import Path
from datetime import datetime, timezone
import json
import re

import duckdb
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "pulseiq.duckdb"
OUTPUT_DIR = PROJECT_DIR / "data" / "etl"
CONTRACT_TABLE = "raw.data_contracts"

FEEDS = {
    "fact_anomaly": "AI anomaly results (fact_anomaly)",
    "fact_attrition_risk": "AI attrition risk (fact_attrition_risk)",
    "fact_forecast": "AI forecast (fact_forecast)",
    "fact_task": "Task board (fact_task)",
}

KEYS = {
    "fact_anomaly": "result_id",
    "fact_attrition_risk": "prediction_id",
    "fact_forecast": "forecast_id",
    "fact_task": "task_id",
}

VALIDATION_REQUIREMENTS = {
    "fact_anomaly.reason_code": {
        "requirement": "one of the published codes",
        "needed_evidence": "The published, versioned reason-code list and its owner.",
    },
    "fact_anomaly.record_id": {
        "requirement": "exists in source dataset",
        "needed_evidence": (
            "A source_dataset-to-table/key mapping approved by the data owner."
        ),
    },
    "fact_anomaly.scored_at": {
        "requirement": "UTC",
        "needed_evidence": (
            "Source-system or schema documentation that establishes the timezone "
            "semantics of scored_at."
        ),
    },
    "fact_task.derived_flags": {
        "requirement": "documented overdue/on-time formula and cutoff",
        "needed_evidence": (
            "The business definition of is_overdue_at_cutoff and "
            "completed_on_time, including the cutoff timestamp/date."
        ),
    },
}


def missing(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def as_date(value):
    if missing(value):
        return pd.NaT
    return pd.to_datetime(value, errors="coerce")


def as_number(value):
    if missing(value):
        return None
    try:
        number = float(value)
        return number if pd.notna(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def add_reason(reasons, i, message):
    if message not in reasons[i]:
        reasons[i].append(message)


def valid_id(value, pattern):
    return (
        not missing(value)
        and bool(re.fullmatch(pattern, str(value).strip()))
    )


def load_reference_set(con, tables, table, column):
    if table not in tables:
        return None

    values = con.execute(
        f'SELECT "{column}" FROM raw."{table}"'
    ).df()[column]

    return set(values.dropna().astype(str).str.strip())


def table_has_column(con, tables, table, column):
    """Return whether a raw table has a named column, without mutating it."""
    if table not in tables:
        return False

    return bool(con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND table_name = ?
          AND column_name = ?
        """,
        [table, column],
    ).fetchone()[0])


def contract_validation_evidence(con, tables):
    """Collect evidence for contract rules that lack an authoritative definition.

    These checks deliberately do not reject rows.  A candidate table/key match,
    observed values, or a physical database type is evidence, not a replacement
    for the missing business contract.
    """
    anomaly = con.execute('SELECT * FROM raw."fact_anomaly"').df()
    task = con.execute('SELECT * FROM raw."fact_task"').df()

    observed_reason_codes = sorted(
        anomaly["reason_code"].dropna().astype(str).str.strip().unique().tolist()
    )

    # These names are schema-based candidates only.  The contract calls the
    # sources "*_features" but does not publish an approved physical mapping.
    candidate_sources = {
        "attendance_monthly_features": (
            "fact_attendance_monthly", "attendance_fact_id"
        ),
        "payroll_monthly_features": ("fact_payroll", "payroll_item_id"),
    }
    candidate_sets = {}
    mapping_available = True
    for source, (table, column) in candidate_sources.items():
        if not table_has_column(con, tables, table, column):
            mapping_available = False
            continue
        candidate_sets[source] = load_reference_set(con, tables, table, column)

    candidate_rows_checked = 0
    candidate_missing = 0
    candidate_unknown_source = 0
    for _, row in anomaly.iterrows():
        source = row.get("source_dataset")
        record_id = row.get("record_id")
        if source not in candidate_sets:
            candidate_unknown_source += 1
        elif not missing(record_id):
            candidate_rows_checked += 1
            if str(record_id).strip() not in candidate_sets[source]:
                candidate_missing += 1

    scored_at_type = con.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND table_name = 'fact_anomaly'
          AND column_name = 'scored_at'
        """
    ).fetchone()

    flag_counts = {}
    for column in ("is_overdue_at_cutoff", "completed_on_time"):
        counts = task[column].fillna("<blank>").astype(str).value_counts()
        flag_counts[column] = {
            str(value): int(count) for value, count in counts.items()
        }

    return {
        "fact_anomaly.reason_code": {
            "status": "UNVERIFIED",
            "enforced": False,
            "requirement": VALIDATION_REQUIREMENTS[
                "fact_anomaly.reason_code"
            ]["requirement"],
            "observed_values": observed_reason_codes,
            "needed_evidence": VALIDATION_REQUIREMENTS[
                "fact_anomaly.reason_code"
            ]["needed_evidence"],
        },
        "fact_anomaly.record_id": {
            "status": "UNVERIFIED",
            "enforced": False,
            "requirement": VALIDATION_REQUIREMENTS[
                "fact_anomaly.record_id"
            ]["requirement"],
            "candidate_mapping": {
                source: {"table": table, "key": column}
                for source, (table, column) in candidate_sources.items()
            },
            "candidate_mapping_available": mapping_available,
            "candidate_rows_checked": candidate_rows_checked,
            "candidate_missing_matches": candidate_missing,
            "candidate_unknown_source_rows": candidate_unknown_source,
            "needed_evidence": VALIDATION_REQUIREMENTS[
                "fact_anomaly.record_id"
            ]["needed_evidence"],
        },
        "fact_anomaly.scored_at": {
            "status": "UNVERIFIED",
            "enforced": False,
            "requirement": VALIDATION_REQUIREMENTS[
                "fact_anomaly.scored_at"
            ]["requirement"],
            "physical_column_type": scored_at_type[0] if scored_at_type else None,
            "timezone_in_type": "not encoded" if scored_at_type else None,
            "needed_evidence": VALIDATION_REQUIREMENTS[
                "fact_anomaly.scored_at"
            ]["needed_evidence"],
        },
        "fact_task.derived_flags": {
            "status": "UNVERIFIED",
            "enforced": False,
            "requirement": VALIDATION_REQUIREMENTS[
                "fact_task.derived_flags"
            ]["requirement"],
            "observed_flag_values": flag_counts,
            "needed_evidence": VALIDATION_REQUIREMENTS[
                "fact_task.derived_flags"
            ]["needed_evidence"],
        },
    }


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(DB_PATH),
        "raw_tables_modified": False,
        "feeds": {},
        "contract_validation": {},
        "validation_gaps": [],
        "contract_compliance": "PARTIAL",
        "status": "INCOMPLETE",
    }

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        contracts = con.execute(
            f"SELECT * FROM {CONTRACT_TABLE}"
        ).df()

        tables = set(
            con.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'raw'
            """).df()["table_name"]
        )

        evidence_tables = {"fact_anomaly", "fact_task"}
        if evidence_tables.issubset(tables):
            log["contract_validation"] = contract_validation_evidence(
                con, tables
            )
        else:
            for key, requirement in VALIDATION_REQUIREMENTS.items():
                log["contract_validation"][key] = {
                    "status": "UNVERIFIED",
                    "enforced": False,
                    "requirement": requirement["requirement"],
                    "needed_evidence": requirement["needed_evidence"],
                    "evidence_error": (
                        "Required raw table unavailable; no evidence collected."
                    ),
                }

        log["validation_gaps"] = [
            f"{key}: {item['status']}; {item['needed_evidence']}"
            for key, item in log["contract_validation"].items()
            if item["status"] != "VERIFIED"
        ]

        references = {
            "dim_employee": load_reference_set(
                con, tables, "dim_employee", "employee_id"
            ),
            "dim_department": load_reference_set(
                con, tables, "dim_department", "department_id"
            ),
            "dim_sprint": load_reference_set(
                con, tables, "dim_sprint", "sprint_id"
            ),
            "dim_team": load_reference_set(
                con, tables, "dim_team", "team_id"
            ),
        }

        active_employee_ids = set()
        if "dim_employee" in tables:
            active_employee_ids = set(
                con.execute("""
                    SELECT DISTINCT employee_id
                    FROM raw.dim_employee
                    WHERE employment_status = 'Active'
                      AND employee_id IS NOT NULL
                """).df()["employee_id"].astype(str).str.strip()
            )

        sprint_end_dates = {}
        if "dim_sprint" in tables:
            sprint_df = con.execute("""
                SELECT sprint_id, end_date
                FROM raw.dim_sprint
            """).df()

            sprint_end_dates = {
                str(row["sprint_id"]).strip(): as_date(row["end_date"])
                for _, row in sprint_df.iterrows()
            }

        all_reconciled = True
        all_feeds_clean = True

        for table, feed in FEEDS.items():
            feed_contracts = contracts[contracts["feed"] == feed]

            result = {
                "contract_rules": len(feed_contracts),
                "input_rows": None,
                "accepted_rows": None,
                "rejected_rows": None,
                "row_count_reconciles": None,
                "status": "NOT_PROCESSED",
            }

            if table not in tables:
                result["status"] = "MISSING_RAW_TABLE"
                log["feeds"][table] = result
                all_reconciled = False
                all_feeds_clean = False
                print(f"MISSING RAW TABLE: {table}")
                continue

            df = con.execute(
                f'SELECT * FROM raw."{table}"'
            ).df()

            result["input_rows"] = len(df)
            reasons = [[] for _ in range(len(df))]

            # Expand contract definitions into individual columns.
            rules = []
            for _, contract in feed_contracts.iterrows():
                column = str(contract["column_name"]).strip()
                columns = (
                    ["top_reason_1", "top_reason_2", "top_reason_3"]
                    if column == "top_reason_1..3"
                    else [column]
                )

                nullable_value = contract["nullable"]
                nullable = (
                    str(nullable_value).strip().lower() == "true"
                    if isinstance(nullable_value, str)
                    else bool(nullable_value)
                )

                for actual_column in columns:
                    rules.append((
                        actual_column,
                        str(contract["data_type"]).lower().strip(),
                        nullable,
                    ))

            missing_columns = sorted({
                column
                for column, _, _ in rules
                if column not in df.columns
            })

            if missing_columns:
                result["status"] = "SCHEMA_ERROR"
                result["missing_columns"] = missing_columns
                log["feeds"][table] = result
                all_reconciled = False
                all_feeds_clean = False
                print(f"SCHEMA ERROR: {table}: {missing_columns}")
                continue

            # Generic required-value and data-type checks.
            for column, dtype, nullable in rules:
                for i, value in enumerate(df[column].tolist()):
                    if missing(value):
                        if not nullable:
                            add_reason(
                                reasons, i,
                                f"{column}: required value is missing"
                            )
                        continue

                    if dtype in ("date", "timestamp"):
                        if pd.isna(as_date(value)):
                            add_reason(
                                reasons, i, f"{column}: invalid {dtype}"
                            )

                    elif dtype in ("int", "integer"):
                        number = as_number(value)
                        if number is None or not number.is_integer():
                            add_reason(
                                reasons, i, f"{column}: expected integer"
                            )

                    elif dtype.startswith("decimal"):
                        if as_number(value) is None:
                            add_reason(
                                reasons, i, f"{column}: expected decimal"
                            )

                    elif dtype == "char(1)":
                        if str(value).strip() not in ("Y", "N"):
                            add_reason(
                                reasons, i, f"{column}: expected Y or N"
                            )

            # Primary key validation.
            key_column = KEYS[table]
            if key_column in df.columns:
                for i, value in enumerate(df[key_column].tolist()):
                    if missing(value):
                        add_reason(
                            reasons, i, f"{key_column}: missing key"
                        )

                duplicate_mask = df[key_column].duplicated(keep=False)
                for i in df.index[duplicate_mask]:
                    add_reason(
                        reasons, i, f"{key_column}: duplicate key"
                    )

            # Feed-specific validation.
            for i, row in df.iterrows():

                if table == "fact_anomaly":
                    score = as_number(row.get("anomaly_score"))
                    if score is not None and not 0 <= score <= 1:
                        add_reason(
                            reasons, i,
                            "anomaly_score: must be between 0 and 1"
                        )

                    source = row.get("source_dataset")
                    if source not in (
                        "attendance_monthly_features",
                        "payroll_monthly_features",
                    ):
                        add_reason(
                            reasons, i,
                            "source_dataset: value not allowed"
                        )

                    # Source-specific money rules.
                    money_at_risk = row.get("money_at_risk")

                    if source == "attendance_monthly_features":
                        if not missing(money_at_risk):
                            add_reason(
                                reasons, i,
                                "money_at_risk: must be blank for attendance rows"
                            )

                    elif source == "payroll_monthly_features":
                        if missing(money_at_risk):
                            add_reason(
                                reasons, i,
                                "money_at_risk: required for payroll rows"
                            )

                    if not valid_id(row.get("result_id"), r"AN-\d{4}"):
                        add_reason(
                            reasons, i, "result_id: expected AN-nnnn"
                        )

                    version = row.get("model_version")
                    if not missing(version) and not re.fullmatch(
                        r"iforest-(attendance|payroll)-\d+\.\d+",
                        str(version).strip(),
                    ):
                        add_reason(
                            reasons, i,
                            "model_version: invalid model version format"
                        )

                    period = as_date(row.get("period"))
                    if not pd.isna(period):
                        if period.day not in (1, period.days_in_month):
                            add_reason(
                                reasons, i,
                                "period: must be month start or month end"
                            )

                    employee_id = row.get("employee_id")
                    if (
                        not missing(employee_id)
                        and references["dim_employee"] is not None
                        and str(employee_id).strip()
                        not in references["dim_employee"]
                    ):
                        add_reason(
                            reasons, i, "employee_id: reference not found"
                        )

                elif table == "fact_attrition_risk":
                    score = as_number(row.get("risk_score_12m"))
                    if score is not None and not 0 <= score <= 1:
                        add_reason(
                            reasons, i,
                            "risk_score_12m: must be between 0 and 1"
                        )

                    if row.get("risk_band") not in (
                        "Low", "Medium", "High"
                    ):
                        add_reason(
                            reasons, i, "risk_band: value not allowed"
                        )

                    if not valid_id(
                        row.get("prediction_id"), r"AR-\d{4}"
                    ):
                        add_reason(
                            reasons, i,
                            "prediction_id: expected AR-nnnn"
                        )

                    employee_id = row.get("employee_id")
                    if (
                        not missing(employee_id)
                        and str(employee_id).strip()
                        not in active_employee_ids
                    ):
                        add_reason(
                            reasons, i,
                            "employee_id: employee not active or not found"
                        )

                    department_id = row.get("department_id")
                    if (
                        not missing(department_id)
                        and references["dim_department"] is not None
                        and str(department_id).strip()
                        not in references["dim_department"]
                    ):
                        add_reason(
                            reasons, i, "department_id: reference not found"
                        )

                elif table == "fact_forecast":
                    value = as_number(row.get("forecast_value"))
                    lower = as_number(row.get("lower_80"))
                    upper = as_number(row.get("upper_80"))

                    if value is None:
                        add_reason(
                            reasons, i, "forecast_value: expected numeric"
                        )
                    elif value < 0:
                        add_reason(
                            reasons, i, "forecast_value: must be >= 0"
                        )

                    if lower is None:
                        add_reason(
                            reasons, i, "lower_80: expected numeric"
                        )
                    elif value is not None and lower > value:
                        add_reason(
                            reasons, i,
                            "lower_80: must be <= forecast_value"
                        )

                    if upper is None:
                        add_reason(
                            reasons, i, "upper_80: expected numeric"
                        )
                    elif value is not None and upper < value:
                        add_reason(
                            reasons, i,
                            "upper_80: must be >= forecast_value"
                        )

                    if row.get("metric") not in (
                        "headcount_end",
                        "attrition_rate_monthly_pct",
                    ):
                        add_reason(
                            reasons, i, "metric: value not allowed"
                        )

                    month = as_date(row.get("forecast_month"))
                    if not pd.isna(month) and month.day != 1:
                        add_reason(
                            reasons, i,
                            "forecast_month: must be first day of month"
                        )

                    trained = row.get("trained_through")
                    if not missing(trained) and not re.fullmatch(
                        r"\d{4}-(0[1-9]|1[0-2])",
                        str(trained).strip(),
                    ):
                        add_reason(
                            reasons, i,
                            "trained_through: expected YYYY-MM"
                        )

                    if not valid_id(
                        row.get("forecast_id"), r"FC-\d{4}"
                    ):
                        add_reason(
                            reasons, i, "forecast_id: expected FC-nnnn"
                        )

                    department_id = row.get("department_id")
                    if (
                        not missing(department_id)
                        and str(department_id).strip() != "ALL"
                        and references["dim_department"] is not None
                        and str(department_id).strip()
                        not in references["dim_department"]
                    ):
                        add_reason(
                            reasons, i, "department_id: reference not found"
                        )

                elif table == "fact_task":
                    allowed = {
                        "status": {
                            "Done", "In Progress", "Blocked",
                            "To Do", "Cancelled",
                        },
                        "priority": {"P1", "P2", "P3", "P4"},
                        "task_type": {"Feature", "Bug", "Chore", "Spike"},
                        "story_points": {1, 2, 3, 5, 8, 13},
                    }

                    for column, allowed_values in allowed.items():
                        value = row.get(column)
                        if missing(value):
                            continue

                        if column == "story_points":
                            number = as_number(value)
                            value = (
                                int(number)
                                if number is not None and number.is_integer()
                                else None
                            )

                        if value not in allowed_values:
                            add_reason(
                                reasons, i, f"{column}: value not allowed"
                            )

                    status = row.get("status")
                    started = as_date(row.get("started_date"))
                    completed = as_date(row.get("completed_date"))
                    created = as_date(row.get("created_date"))

                    if status == "Done" and pd.isna(completed):
                        add_reason(
                            reasons, i,
                            "completed_date: required when status is Done"
                        )

                    if (
                        not pd.isna(started)
                        and not pd.isna(completed)
                        and completed < started
                    ):
                        add_reason(
                            reasons, i,
                            "completed_date: earlier than started_date"
                        )

                    if (
                        not pd.isna(created)
                        and not pd.isna(started)
                        and created > started
                    ):
                        add_reason(
                            reasons, i,
                            "created_date: later than started_date"
                        )

                    # Validate cycle time when both dates exist.
                    cycle_time = as_number(row.get("cycle_time_days"))
                    if (
                        cycle_time is not None
                        and not pd.isna(started)
                        and not pd.isna(completed)
                    ):
                        expected_cycle_time = (completed - started).days
                        if cycle_time != expected_cycle_time:
                            add_reason(
                                reasons, i,
                                "cycle_time_days: inconsistent with completed_date minus started_date"
                            )

                    if missing(row.get("started_date")) and status != "To Do":
                        add_reason(
                            reasons, i,
                            "started_date: blank only allowed when status is To Do"
                        )

                    reopened = row.get("reopened_count")
                    if not missing(reopened):
                        number = as_number(reopened)
                        if (
                            number is None
                            or not number.is_integer()
                            or number < 0
                        ):
                            add_reason(
                                reasons, i,
                                "reopened_count: must be a non-negative integer"
                            )

                    sprint_id = row.get("sprint_id")
                    due = as_date(row.get("due_date"))

                    if not missing(sprint_id) and not pd.isna(due):
                        sprint_key = str(sprint_id).strip()

                        if sprint_key in sprint_end_dates:
                            expected_end = sprint_end_dates[sprint_key]
                            if (
                                not pd.isna(expected_end)
                                and due.normalize() != expected_end.normalize()
                            ):
                                add_reason(
                                    reasons, i,
                                    "due_date: does not match sprint end_date"
                                )

                    if not valid_id(
                        row.get("task_id"), r"TASK-\d{5}"
                    ):
                        add_reason(
                            reasons, i, "task_id: expected TASK-nnnnn"
                        )

                    for column, reference_table in (
                        ("assignee_employee_id", "dim_employee"),
                        ("sprint_id", "dim_sprint"),
                        ("team_id", "dim_team"),
                    ):
                        value = row.get(column)
                        reference_values = references[reference_table]

                        if (
                            not missing(value)
                            and reference_values is not None
                            and str(value).strip() not in reference_values
                        ):
                            add_reason(
                                reasons, i,
                                f"{column}: reference not found"
                            )

            # Contract requires one as_of_date per attrition batch.
            # Use the most frequent date as the batch reference, not the first row.
            if table == "fact_attrition_risk" and "as_of_date" in df.columns:
                parsed_dates = [
                    as_date(value)
                    for value in df["as_of_date"].tolist()
                    if not missing(value) and not pd.isna(as_date(value))
                ]

                if parsed_dates:
                    date_counts = pd.Series(
                        [value.date() for value in parsed_dates]
                    ).value_counts()
                    batch_date = date_counts.index[0]

                    for i, value in enumerate(df["as_of_date"].tolist()):
                        parsed = as_date(value)

                        if pd.isna(parsed) or parsed.date() != batch_date:
                            add_reason(
                                reasons, i,
                                "as_of_date: inconsistent or invalid batch date"
                            )

            rejected_mask = [bool(items) for items in reasons]

            accepted = df.loc[
                [not bad for bad in rejected_mask]
            ].copy()

            rejected = df.loc[rejected_mask].copy()
            rejected["rejection_reason"] = [
                " | ".join(reasons[i])
                for i, bad in enumerate(rejected_mask)
                if bad
            ]

            accepted_path = OUTPUT_DIR / f"{table}_accepted.csv"
            rejected_path = OUTPUT_DIR / f"{table}_quarantine.csv"

            accepted.to_csv(accepted_path, index=False)
            rejected.to_csv(rejected_path, index=False)

            reconciles = len(accepted) + len(rejected) == len(df)

            if not reconciles:
                all_reconciled = False

            if len(rejected) > 0:
                all_feeds_clean = False

            result.update({
                "accepted_rows": len(accepted),
                "rejected_rows": len(rejected),
                "row_count_reconciles": reconciles,
                "status": (
                    "PROCESSED"
                    if reconciles
                    else "RECONCILIATION_ERROR"
                ),
                "accepted_file": str(
                    accepted_path.relative_to(PROJECT_DIR)
                ),
                "quarantine_file": str(
                    rejected_path.relative_to(PROJECT_DIR)
                ),
            })

            log["feeds"][table] = result

            print(
                f"{table}: input={len(df):,}, "
                f"accepted={len(accepted):,}, "
                f"rejected={len(rejected):,}, "
                f"reconciles={reconciles}"
            )

        all_feeds_processed = (
            len(log["feeds"]) == len(FEEDS)
            and all(
                item["status"] == "PROCESSED"
                for item in log["feeds"].values()
            )
        )

        log["status"] = (
            "COMPLETE"
            if all_feeds_processed and all_reconciled
            else "INCOMPLETE"
        )

        # Processing completion is separate from contract compliance.
        if log["status"] != "COMPLETE":
            log["contract_compliance"] = "FAIL"
        elif log["validation_gaps"]:
            log["contract_compliance"] = "PARTIAL"
        elif all_feeds_clean:
            log["contract_compliance"] = "PASS"
        else:
            log["contract_compliance"] = "PARTIAL"

        log_path = OUTPUT_DIR / "etl_run_log.json"
        log_path.write_text(
            json.dumps(log, indent=2, default=str),
            encoding="utf-8",
        )

        print(f"\nPipeline status: {log['status']}")
        print(f"Contract compliance: {log['contract_compliance']}")
        print(f"Audit log: {log_path}")
        print("Raw database tables were opened read-only.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
