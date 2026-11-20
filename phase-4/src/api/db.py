"""
Read-only database helper for the Task 19 Metrics API.

Provides read-only DuckDB connections to the sanitized API database
(pulseiq_api.duckdb) which contains only aggregate tables safe for public
hosting. No employee-level data, PII, or payroll records at individual level.
No write operations are supported.
"""

from pathlib import Path

import duckdb

# Sanitized database located alongside this module
API_DB_PATH = Path(__file__).resolve().parent / "pulseiq_api.duckdb"


def get_public_db_connection():
    """Open a read-only connection to the sanitized API database.

    The sanitized database contains only aggregate tables derived from both
    pulseiq_clean.duckdb (company metrics) and pulseiq_public.duckdb
    (department metrics). No individual-level data is exposed.

    Raises FileNotFoundError if the database file does not exist.
    The connection is read-only; no writes are possible.
    """
    if not API_DB_PATH.exists():
        raise FileNotFoundError(f"Sanitized API database not found: {API_DB_PATH}")
    return duckdb.connect(str(API_DB_PATH), read_only=True)


def get_clean_db_connection():
    """Open a read-only connection to the sanitized API database.

    Both company and department metrics are served from the single
    sanitized database. This function exists for API compatibility
    with code paths that reference company-level data.

    Raises FileNotFoundError if the database file does not exist.
    The connection is read-only; no writes are possible.
    """
    if not API_DB_PATH.exists():
        raise FileNotFoundError(f"Sanitized API database not found: {API_DB_PATH}")
    return duckdb.connect(str(API_DB_PATH), read_only=True)


def check_databases():
    """Verify the sanitized API database is accessible in read-only mode.

    Returns a dict with status for the database.
    Does not modify any database.
    """
    results = {}
    for name, path, fn in [
        ("api", API_DB_PATH, get_public_db_connection),
    ]:
        try:
            conn = fn()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            results[name] = {"accessible": True, "path": str(path)}
        except Exception as exc:  # noqa: BLE001
            results[name] = {"accessible": False, "path": str(path), "error": str(exc)}
    return results


def verify_databases():
    """Verify the sanitized API database file exists before the API starts.

    Raises FileNotFoundError with clear, actionable instructions if the
    database file is missing. This prevents the API from silently starting
    without its required data assets on Render or any other hosting platform.

    Called during FastAPI app startup via the lifespan context manager.
    """
    if not API_DB_PATH.exists():
        raise FileNotFoundError(
            "Required sanitized API database file is missing. The Metrics API "
            "requires pulseiq_api.duckdb to be provisioned before startup.\n"
            f"Missing file: {API_DB_PATH}\n"
            "\nProvision via GitHub Release Assets:\n"
            "  1. Create a GitHub Release tag (e.g., db-v1.0)\n"
            "  2. Upload pulseiq_api.duckdb as a release asset\n"
            "  3. Update the Release Asset URL in render.yaml buildCommand\n"
            "  4. Redeploy the service\n"
            "\nThe sanitized database contains only aggregate tables:\n"
            "  - pq15_company_scorecard (company-level metrics)\n"
            "  - pq15_kpi_trends (metric time series)\n"
            "  - pq15_kpi_targets_company (KPI targets)\n"
            "  - pq15_validation (validation results)\n"
            "  - dept_month_combined (department-level aggregates)\n"
            "No employee-level data or PII is included.\n"
        )
