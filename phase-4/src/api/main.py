"""
Task 19 — Metrics API (Phase 2: KPI Endpoints).

FastAPI application exposing 5 business metrics through a versioned API.

Endpoints:
- GET /api/v1/metrics — list all metrics with metadata
- GET /api/v1/metrics/{metric_key} — metric value, definition, source, refresh
- GET /api/v1/metrics/{metric_key}/trend — monthly time series
- GET /api/v1/metrics/{metric_key}/departments — department breakdown (workforce KPIs only)
- GET /api/v1/lineage/{metric_key} — data lineage (5 stages)
- GET /api/v1/freshness — data freshness statement
- GET /health — health check with database connectivity

All database access is read-only. Department-level queries enforce the
minimum headcount privacy threshold of 5.
"""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .db import check_databases, get_clean_db_connection, get_public_db_connection, verify_databases

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WAREHOUSE_DIR = PROJECT_ROOT / "phase-3" / "data" / "warehouse"

# ---------------------------------------------------------------------------
# Metric definitions (5 selected metrics)
# ---------------------------------------------------------------------------
METRIC_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "revenue": {
        "key": "revenue",
        "name": "Revenue",
        "description": "Total recognized revenue for the reporting month across all business units",
        "unit": "INR",
        "direction": "Higher is better",
        "source_table": "star_schema.m16_revenue",
        "metric_view": "star_schema.pq15_company_scorecard",
        "calculation": "SUM(revenue) from m16_revenue where month = reporting_month",
        "domain": "financial",
        "db": "clean",
        "scorecard_column": "revenue",
        "privacy_notice": "Company-level metric — no privacy suppression applied",
    },
    "net_profit": {
        "key": "net_profit",
        "name": "Net Profit",
        "description": "Bottom-line profitability for the reporting month after all expenses",
        "unit": "INR",
        "direction": "Higher is better",
        "source_table": "star_schema.m17_net_profit",
        "metric_view": "star_schema.pq15_company_scorecard",
        "calculation": "SUM(net_profit) from m17_net_profit where month = reporting_month",
        "domain": "financial",
        "db": "clean",
        "scorecard_column": "net_profit",
        "privacy_notice": "Company-level metric — no privacy suppression applied",
    },
    "operating_margin": {
        "key": "operating_margin",
        "name": "Operating Margin",
        "description": "Operating profit as a percentage of revenue for the reporting month",
        "unit": "%",
        "direction": "Higher is better",
        "source_table": "star_schema.m18_operating_margin",
        "metric_view": "star_schema.pq15_company_scorecard",
        "calculation": "operating_margin_pct from m18_operating_margin where month = reporting_month",
        "domain": "financial",
        "db": "clean",
        "scorecard_column": "operating_margin_pct",
        "privacy_notice": "Company-level metric — no privacy suppression applied",
    },
    "headcount": {
        "key": "headcount",
        "name": "Total Headcount",
        "description": "Total number of employees at the end of the reporting month",
        "unit": "count",
        "direction": "Context dependent",
        "source_table": "star_schema.dept_month_headcount",
        "metric_view": "star_schema.pq15_company_scorecard",
        "calculation": "SUM(headcount_end) from dept_month_headcount where month = reporting_month",
        "domain": "workforce",
        "db": "clean",
        "scorecard_column": "total_headcount",
        "privacy_notice": "Company-level metric — no privacy suppression applied",
        "supports_departments": True,
        "dept_column": "headcount_end",
        "dept_table": "star_schema.dept_month_combined",
        "dept_db": "public",
    },
    "attrition_rate": {
        "key": "attrition_rate",
        "name": "Rolling 12M Attrition",
        "description": "Rolling 12-month attrition rate: exits over 12 months / average headcount over 12 months",
        "unit": "%",
        "direction": "Lower is better",
        "source_table": "star_schema.dept_month_headcount",
        "metric_view": "star_schema.pq15_company_scorecard",
        "calculation": "SUM(exits over 12M) / AVG(headcount_end over 12M) * 100",
        "domain": "workforce",
        "db": "clean",
        "scorecard_column": "attrition_rolling_12m_pct",
        "privacy_notice": "Company-level metric — no privacy suppression applied",
    },
}

MIN_HEADCOUNT = 5

# Department-level metrics (only headcount supports dept breakdown)
DEPT_METRICS = {"headcount"}

# Valid metric keys (ordered)
METRIC_KEYS = list(METRIC_DEFINITIONS.keys())

# ---------------------------------------------------------------------------
# Lineage data (from plan Section 6, verified/unverified flags)
# ---------------------------------------------------------------------------
LINEAGE_DATA: Dict[str, Dict[str, Any]] = {
    "revenue": {
        "key": "revenue",
        "name": "Revenue",
        "lineage": [
            {
                "stage": "raw",
                "name": "Raw Invoicing Data",
                "description": "Source invoices from ERP billing system",
                "tables": ["raw.invoices"],
                "transformations": "Extract invoice date, amount, customer",
                "verified": False,
            },
            {
                "stage": "etl",
                "name": "Revenue Recognition ETL",
                "description": "Recognize revenue per accounting standards",
                "tables": ["staging.revenue_recognized"],
                "transformations": "Apply rev-rec rules, aggregate by month",
                "verified": False,
            },
            {
                "stage": "warehouse",
                "name": "Revenue Fact Table",
                "description": "Company-level monthly revenue",
                "tables": ["star_schema.m16_revenue"],
                "transformations": "Materialized view from staging",
                "verified": True,
            },
            {
                "stage": "metric_view",
                "name": "Company Scorecard",
                "description": "Executive scorecard joining all 8 KPIs",
                "tables": ["star_schema.pq15_company_scorecard"],
                "transformations": "FULL JOIN across KPI CTEs on month",
                "verified": True,
            },
            {
                "stage": "dashboard",
                "name": "Executive Report / Metrics API",
                "description": "PDF report, Excel workbook, Streamlit dashboard, Metrics API",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.pq15_kpi_trends"],
                "transformations": "Formatting, charting, trend calculation",
                "verified": True,
            },
        ],
        "verified_stages": ["warehouse", "metric_view", "dashboard"],
        "unverified_stages": ["raw", "etl"],
    },
    "net_profit": {
        "key": "net_profit",
        "name": "Net Profit",
        "lineage": [
            {
                "stage": "raw",
                "name": "General Ledger / P&L Source",
                "description": "General ledger and P&L source system",
                "tables": ["raw.general_ledger"],
                "transformations": "Extract revenue and expense transactions",
                "verified": False,
            },
            {
                "stage": "etl",
                "name": "Profit Calculation Pipeline",
                "description": "Calculate net profit from revenue and expenses",
                "tables": ["staging.net_profit"],
                "transformations": "Aggregate revenue minus expenses by month",
                "verified": False,
            },
            {
                "stage": "warehouse",
                "name": "Net Profit Fact Table",
                "description": "Company-level monthly net profit",
                "tables": ["star_schema.m17_net_profit"],
                "transformations": "Materialized view from staging",
                "verified": True,
            },
            {
                "stage": "metric_view",
                "name": "Company Scorecard",
                "description": "Executive scorecard joining all 8 KPIs",
                "tables": ["star_schema.pq15_company_scorecard"],
                "transformations": "FULL JOIN across KPI CTEs on month",
                "verified": True,
            },
            {
                "stage": "dashboard",
                "name": "Executive Report / Metrics API",
                "description": "PDF report, Excel workbook, Streamlit dashboard, Metrics API",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.pq15_kpi_trends"],
                "transformations": "Formatting, charting, trend calculation",
                "verified": True,
            },
        ],
        "verified_stages": ["warehouse", "metric_view", "dashboard"],
        "unverified_stages": ["raw", "etl"],
    },
    "operating_margin": {
        "key": "operating_margin",
        "name": "Operating Margin",
        "lineage": [
            {
                "stage": "raw",
                "name": "GL + Revenue Source",
                "description": "General ledger and revenue source data",
                "tables": ["raw.general_ledger", "raw.invoices"],
                "transformations": "Extract operating expenses and revenue",
                "verified": False,
            },
            {
                "stage": "etl",
                "name": "Margin Calculation",
                "description": "Calculate operating margin from revenue and operating profit",
                "tables": ["staging.operating_margin"],
                "transformations": "Operating profit / revenue * 100 by month",
                "verified": False,
            },
            {
                "stage": "warehouse",
                "name": "Operating Margin Fact Table",
                "description": "Company-level monthly operating margin",
                "tables": ["star_schema.m18_operating_margin"],
                "transformations": "Materialized view from staging",
                "verified": True,
            },
            {
                "stage": "metric_view",
                "name": "Company Scorecard",
                "description": "Executive scorecard joining all 8 KPIs",
                "tables": ["star_schema.pq15_company_scorecard"],
                "transformations": "FULL JOIN across KPI CTEs on month",
                "verified": True,
            },
            {
                "stage": "dashboard",
                "name": "Executive Report / Metrics API",
                "description": "PDF report, Excel workbook, Streamlit dashboard, Metrics API",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.pq15_kpi_trends"],
                "transformations": "Formatting, charting, trend calculation",
                "verified": True,
            },
        ],
        "verified_stages": ["warehouse", "metric_view", "dashboard"],
        "unverified_stages": ["raw", "etl"],
    },
    "headcount": {
        "key": "headcount",
        "name": "Total Headcount",
        "lineage": [
            {
                "stage": "raw",
                "name": "HRIS / Payroll Employee Records",
                "description": "Human resources information system employee records",
                "tables": ["raw.employee_records"],
                "transformations": "Extract employee start/end dates and department",
                "verified": False,
            },
            {
                "stage": "etl",
                "name": "Headcount Spine Build (PQ-13)",
                "description": "Build monthly headcount spine from employee records",
                "tables": ["staging.dept_month_spine"],
                "transformations": "SCD processing of employee movements by month",
                "verified": True,
            },
            {
                "stage": "warehouse",
                "name": "Headcount Warehouse Table",
                "description": "Department-month headcount snapshot",
                "tables": ["star_schema.dept_month_headcount", "star_schema.dept_month_combined"],
                "transformations": "Aggregate employee records to department-month grain",
                "verified": True,
            },
            {
                "stage": "metric_view",
                "name": "Company Scorecard / Dept Combined",
                "description": "Company scorecard SUMs headcount_end; dept view exposes column directly",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.dept_month_combined"],
                "transformations": "SUM(headcount_end) grouped by month; direct column for dept view",
                "verified": True,
            },
            {
                "stage": "dashboard",
                "name": "Executive Report / KPI Explorer / Metrics API",
                "description": "PDF report, Excel workbook, Streamlit dashboard, Metrics API",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.dept_month_combined"],
                "transformations": "Formatting, department breakdown, privacy threshold",
                "verified": True,
            },
        ],
        "verified_stages": ["etl", "warehouse", "metric_view", "dashboard"],
        "unverified_stages": ["raw"],
    },
    "attrition_rate": {
        "key": "attrition_rate",
        "name": "Rolling 12M Attrition",
        "lineage": [
            {
                "stage": "raw",
                "name": "HRIS Termination Records",
                "description": "Human resources information system termination records",
                "tables": ["raw.termination_records"],
                "transformations": "Extract employee exit dates and reasons",
                "verified": False,
            },
            {
                "stage": "etl",
                "name": "Attrition Calculation (PQ-15)",
                "description": "Rolling 12-month attrition from headcount and exits",
                "tables": ["staging.dept_month_headcount"],
                "transformations": "SUM(exits over 12M) / AVG(headcount_end over 12M) * 100",
                "verified": True,
            },
            {
                "stage": "warehouse",
                "name": "Headcount Warehouse Table",
                "description": "Department-month headcount with exits column",
                "tables": ["star_schema.dept_month_headcount"],
                "transformations": "exits and headcount_end columns available per dept-month",
                "verified": True,
            },
            {
                "stage": "metric_view",
                "name": "Company Scorecard",
                "description": "Executive scorecard with attrition_rolling_12m_pct column",
                "tables": ["star_schema.pq15_company_scorecard"],
                "transformations": "CTE attrition_cte: rolling 12M calculation",
                "verified": True,
            },
            {
                "stage": "dashboard",
                "name": "Executive Report / Metrics API",
                "description": "PDF report, Excel workbook, Streamlit dashboard, Metrics API",
                "tables": ["star_schema.pq15_company_scorecard", "star_schema.pq15_kpi_trends"],
                "transformations": "Formatting, trend calculation",
                "verified": True,
            },
        ],
        "verified_stages": ["etl", "warehouse", "metric_view", "dashboard"],
        "unverified_stages": ["raw"],
    },
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ResponseMeta(BaseModel):
    request_id: str
    timestamp: str
    version: str = "1.0.0"


class MetricSummary(BaseModel):
    key: str
    name: str
    description: str
    unit: str
    direction: str
    source_table: str
    metric_view: str
    available_in_dashboard: bool = True
    privacy_level: str = "public"


class MetricValue(BaseModel):
    metric_key: str
    name: str
    value: float
    unit: str
    formatted_value: str
    direction: str
    definition: str
    source_table: str
    metric_view: str
    calculation: str
    period: str
    last_refresh: str
    data_freshness: str
    privacy_notice: str


class TrendPoint(BaseModel):
    month: str
    value: float
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class TrendResponse(BaseModel):
    metric_key: str
    name: str
    unit: str
    trend: List[TrendPoint]
    period: Dict[str, str]
    last_refresh: str
    data_freshness: str


class DepartmentValue(BaseModel):
    department_id: str
    department_name: str
    value: float


class DepartmentResponse(BaseModel):
    metric_key: str
    name: str
    unit: str
    month: str
    departments: List[DepartmentValue]
    suppressed_departments: int
    privacy_threshold: int
    privacy_notice: str
    last_refresh: str
    data_freshness: str


class LineageStage(BaseModel):
    stage: str
    name: str
    description: str
    tables: List[str]
    transformations: str
    verified: bool


class LineageResponse(BaseModel):
    metric_key: str
    name: str
    lineage: List[LineageStage]
    verified_stages: List[str]
    unverified_stages: List[str]


class MetricFreshness(BaseModel):
    metric_key: str
    latest_period: str
    latest_value_date: str
    is_current: bool
    note: Optional[str] = None


class FreshnessResponse(BaseModel):
    statement: str
    warehouse_last_refresh: str
    metrics: List[MetricFreshness]
    dashboard_freshness: str


class HealthResponse(BaseModel):
    status: str
    databases: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _parse_month(month_str: Optional[str]) -> Optional[date]:
    """Parse a YYYY-MM month string into a date (first day of month)."""
    if month_str is None:
        return None
    try:
        parts = month_str.strip().split("-")
        if len(parts) != 2:
            raise ValueError("Invalid month format")
        year = int(parts[0])
        month = int(parts[1])
        if month < 1 or month > 12:
            raise ValueError("Invalid month")
        return date(year, month, 1)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"Invalid month format: '{month_str}'. Expected YYYY-MM.",
            },
        )


def _format_value(value: Any, unit: str) -> str:
    """Format a numeric value for display."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "INR":
        return f"₹{v:,.2f}"
    elif unit == "%":
        return f"{v:.2f}%"
    elif unit == "count":
        return f"{int(v):,}"
    else:
        return f"{v:,.2f}"


def _get_latest_month(conn, table: str, column: str = "month") -> Optional[date]:
    """Get the latest month from a table."""
    row = conn.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
    if row and row[0] is not None:
        val = row[0]
        if isinstance(val, date):
            return val
        return date(val.year, val.month, 1)
    return None


def _get_metric_value(conn, metric_key: str, month: Optional[date]) -> Dict[str, Any]:
    """Fetch a single metric value from the company scorecard."""
    definition = METRIC_DEFINITIONS[metric_key]
    col = definition["scorecard_column"]

    if month:
        query = f"""
            SELECT {col}, month
            FROM star_schema.pq15_company_scorecard
            WHERE month = ?
        """
        row = conn.execute(query, [month]).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "METRIC_NOT_FOUND",
                    "message": f"No data for metric '{metric_key}' in month {month.isoformat()[:7]}",
                    "details": {"available_metrics": METRIC_KEYS},
                },
            )
        value = row[0]
        period = row[1].isoformat()[:7] if hasattr(row[1], "isoformat") else str(row[1])[:7]
    else:
        query = f"""
            SELECT {col}, month
            FROM star_schema.pq15_company_scorecard
            ORDER BY month DESC
            LIMIT 1
        """
        row = conn.execute(query).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "METRIC_NOT_FOUND",
                    "message": f"No data for metric '{metric_key}'",
                    "details": {"available_metrics": METRIC_KEYS},
                },
            )
        value = row[0]
        period = row[1].isoformat()[:7] if hasattr(row[1], "isoformat") else str(row[1])[:7]

    latest_month = _get_latest_month(conn, "star_schema.pq15_company_scorecard")
    last_refresh = latest_month.isoformat() + "T00:00:00Z" if latest_month else "unknown"

    return {
        "metric_key": metric_key,
        "name": definition["name"],
        "value": float(value) if value is not None else None,
        "unit": definition["unit"],
        "formatted_value": _format_value(value, definition["unit"]),
        "direction": definition["direction"],
        "definition": definition["description"],
        "source_table": definition["source_table"],
        "metric_view": definition["metric_view"],
        "calculation": definition["calculation"],
        "period": period,
        "last_refresh": last_refresh,
        "data_freshness": f"Data as of {period}",
        "privacy_notice": definition["privacy_notice"],
    }


def _get_metric_trend(
    conn, metric_key: str, start_month: Optional[date], end_month: Optional[date]
) -> Dict[str, Any]:
    """Fetch monthly trend data for a metric from the KPI trends view."""
    definition = METRIC_DEFINITIONS[metric_key]

    # Map metric key to kpi_name in the trends view
    kpi_name_map = {
        "revenue": "Revenue",
        "net_profit": "Net Profit",
        "operating_margin": "Operating Margin",
        "headcount": "Total Headcount",
        "attrition_rate": "Rolling 12M Attrition",
    }
    kpi_name = kpi_name_map[metric_key]

    conditions = ["kpi_name = ?"]
    params: List[Any] = [kpi_name]

    if start_month:
        conditions.append("month >= ?")
        params.append(start_month)
    if end_month:
        conditions.append("month <= ?")
        params.append(end_month)

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT kpi_name, month, value, unit, direction
        FROM star_schema.pq15_kpi_trends
        WHERE {where_clause}
        ORDER BY month
    """
    rows = conn.execute(query, params).fetchall()

    trend = []
    for row in rows:
        month_val = row[1]
        month_str = month_val.isoformat()[:7] if hasattr(month_val, "isoformat") else str(month_val)[:7]
        trend.append(
            TrendPoint(
                month=month_str,
                value=float(row[2]),
                department_id=None,
                department_name="All",
            )
        )

    latest_month = _get_latest_month(conn, "star_schema.pq15_kpi_trends")
    last_refresh = latest_month.isoformat() + "T00:00:00Z" if latest_month else "unknown"

    start_str = start_month.isoformat()[:7] if start_month else trend[0].month if trend else "unknown"
    end_str = end_month.isoformat()[:7] if end_month else trend[-1].month if trend else "unknown"

    return {
        "metric_key": metric_key,
        "name": definition["name"],
        "unit": definition["unit"],
        "trend": [t.model_dump() for t in trend],
        "period": {"start": start_str, "end": end_str},
        "last_refresh": last_refresh,
        "data_freshness": f"Data as of {end_str if end_str != 'unknown' else start_str}",
    }


def _get_department_breakdown(
    conn, metric_key: str, month: date
) -> Dict[str, Any]:
    """Fetch department-level breakdown for a workforce metric."""
    if metric_key not in DEPT_METRICS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"Metric '{metric_key}' does not support department breakdown",
                "details": {"available_dept_metrics": sorted(DEPT_METRICS)},
            },
        )

    definition = METRIC_DEFINITIONS[metric_key]
    dept_col = definition["dept_column"]
    dept_table = definition["dept_table"]

    query = f"""
        SELECT department_id, department_name, SUM({dept_col}) as value
        FROM {dept_table}
        WHERE {dept_col} >= {MIN_HEADCOUNT}
          AND month = ?
        GROUP BY department_id, department_name
        ORDER BY department_name
    """
    rows = conn.execute(query, [month]).fetchall()

    departments = []
    total_depts = 0

    # Count all departments (including suppressed) for transparency
    all_depts_query = f"""
        SELECT COUNT(DISTINCT department_id) FROM {dept_table} WHERE month = ?
    """
    total_depts = conn.execute(all_depts_query, [month]).fetchone()[0]

    for row in rows:
        departments.append(
            DepartmentValue(
                department_id=row[0],
                department_name=row[1],
                value=float(row[2]),
            )
        )

    suppressed = total_depts - len(departments)

    latest_month = _get_latest_month(conn, dept_table)
    last_refresh = latest_month.isoformat() + "T00:00:00Z" if latest_month else "unknown"

    return {
        "metric_key": metric_key,
        "name": definition["name"],
        "unit": definition["unit"],
        "month": month.isoformat()[:7],
        "departments": [d.model_dump() for d in departments],
        "suppressed_departments": suppressed,
        "privacy_threshold": MIN_HEADCOUNT,
        "privacy_notice": "Departments with fewer than 5 employees are excluded from published departmental metrics to protect employee privacy.",
        "last_refresh": last_refresh,
        "data_freshness": f"Data as of {month.isoformat()[:7]}",
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify both database files exist before the API starts accepting requests.

    Raises FileNotFoundError with clear instructions if either database
    is missing. This prevents the API from silently starting without its
    required data assets on Render or any other hosting platform.
    """
    verify_databases()
    yield


app = FastAPI(title="PulseIQ Metrics API", version="1.0.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> Dict[str, Any]:
    """Health check with database connectivity verification.

    Returns the overall API status and per-database accessibility.
    Does not modify any database.
    """
    db_status = check_databases()
    all_healthy = all(d["accessible"] for d in db_status.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "databases": db_status,
    }


# ---------------------------------------------------------------------------
# API v1 routes
# ---------------------------------------------------------------------------
@app.get("/api/v1/metrics", response_model=Dict[str, Any])
def list_metrics() -> Dict[str, Any]:
    """List all 5 available metrics with metadata."""
    data = []
    for key in METRIC_KEYS:
        definition = METRIC_DEFINITIONS[key]
        data.append(
            MetricSummary(
                key=definition["key"],
                name=definition["name"],
                description=definition["description"],
                unit=definition["unit"],
                direction=definition["direction"],
                source_table=definition["source_table"],
                metric_view=definition["metric_view"],
            ).model_dump()
        )
    return {
        "data": data,
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }


@app.get("/api/v1/metrics/{metric_key}", response_model=Dict[str, Any])
def get_metric(
    metric_key: str,
    month: Optional[str] = Query(
        None, description="Reporting month in YYYY-MM format. Defaults to latest available."
    ),
) -> Dict[str, Any]:
    """Get a single metric's value, definition, source, and last refresh."""
    if metric_key not in METRIC_DEFINITIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "METRIC_NOT_FOUND",
                "message": f"Metric '{metric_key}' not found",
                "details": {"available_metrics": METRIC_KEYS},
            },
        )

    parsed_month = _parse_month(month)

    definition = METRIC_DEFINITIONS[metric_key]
    if definition["db"] == "clean":
        conn = get_clean_db_connection()
    else:
        conn = get_public_db_connection()

    try:
        result = _get_metric_value(conn, metric_key, parsed_month)
    finally:
        conn.close()

    return {
        "data": result,
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }


@app.get("/api/v1/metrics/{metric_key}/trend", response_model=Dict[str, Any])
def get_metric_trend(
    metric_key: str,
    start_month: Optional[str] = Query(
        None, description="Start month in YYYY-MM format. Defaults to earliest available."
    ),
    end_month: Optional[str] = Query(
        None, description="End month in YYYY-MM format. Defaults to latest available."
    ),
) -> Dict[str, Any]:
    """Get monthly time series for a metric."""
    if metric_key not in METRIC_DEFINITIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "METRIC_NOT_FOUND",
                "message": f"Metric '{metric_key}' not found",
                "details": {"available_metrics": METRIC_KEYS},
            },
        )

    parsed_start = _parse_month(start_month)
    parsed_end = _parse_month(end_month)

    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": "start_month must be before or equal to end_month",
            },
        )

    conn = get_clean_db_connection()
    try:
        result = _get_metric_trend(conn, metric_key, parsed_start, parsed_end)
    finally:
        conn.close()

    return {
        "data": result,
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }


@app.get(
    "/api/v1/metrics/{metric_key}/departments", response_model=Dict[str, Any]
)
def get_metric_departments(
    metric_key: str,
    month: str = Query(
        ..., description="Reporting month in YYYY-MM format. Required for department breakdown."
    ),
) -> Dict[str, Any]:
    """Get department-level breakdown for a workforce metric.

    Enforces the minimum headcount privacy threshold of 5.
    """
    if metric_key not in METRIC_DEFINITIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "METRIC_NOT_FOUND",
                "message": f"Metric '{metric_key}' not found",
                "details": {"available_metrics": METRIC_KEYS},
            },
        )

    if metric_key not in DEPT_METRICS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"Metric '{metric_key}' does not support department breakdown",
                "details": {"available_dept_metrics": sorted(DEPT_METRICS)},
            },
        )

    parsed_month = _parse_month(month)
    if parsed_month is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": "month parameter is required for department breakdown",
            },
        )

    definition = METRIC_DEFINITIONS[metric_key]
    if definition.get("dept_db") == "public":
        conn = get_public_db_connection()
    else:
        conn = get_clean_db_connection()

    try:
        result = _get_department_breakdown(conn, metric_key, parsed_month)
    finally:
        conn.close()

    return {
        "data": result,
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }


@app.get("/api/v1/lineage/{metric_key}", response_model=Dict[str, Any])
def get_lineage(metric_key: str) -> Dict[str, Any]:
    """Get the full data lineage for a metric (5 stages: raw → ETL → warehouse → metric view → dashboard)."""
    if metric_key not in METRIC_DEFINITIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "METRIC_NOT_FOUND",
                "message": f"Metric '{metric_key}' not found",
                "details": {"available_metrics": METRIC_KEYS},
            },
        )

    lineage_info = LINEAGE_DATA[metric_key]
    return {
        "data": {
            "metric_key": lineage_info["key"],
            "name": lineage_info["name"],
            "lineage": lineage_info["lineage"],
            "verified_stages": lineage_info["verified_stages"],
            "unverified_stages": lineage_info["unverified_stages"],
        },
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }


@app.get("/api/v1/freshness", response_model=Dict[str, Any])
def get_freshness() -> Dict[str, Any]:
    """Get the data freshness statement for all exposed metrics."""
    clean_conn = get_clean_db_connection()
    try:
        latest_scorecard_month = _get_latest_month(
            clean_conn, "star_schema.pq15_company_scorecard"
        )
    finally:
        clean_conn.close()

    warehouse_last_refresh = (
        latest_scorecard_month.isoformat() + "T00:00:00Z" if latest_scorecard_month else "unknown"
    )

    latest_period = latest_scorecard_month.isoformat()[:7] if latest_scorecard_month else "unknown"
    latest_date = latest_scorecard_month.isoformat() if latest_scorecard_month else "unknown"

    metrics_freshness = []
    for key in METRIC_KEYS:
        definition = METRIC_DEFINITIONS[key]
        note = None
        if key == "attrition_rate":
            note = "Rolling 12M calculation requires 12 months of history"
        metrics_freshness.append(
            MetricFreshness(
                metric_key=key,
                latest_period=latest_period,
                latest_value_date=latest_date,
                is_current=True,
                note=note,
            ).model_dump()
        )

    statement = (
        f"All metrics reflect data as of {latest_period}. "
        f"The warehouse was last refreshed on {latest_date}. "
        "No new data has been loaded since."
    )

    return {
        "data": {
            "statement": statement,
            "warehouse_last_refresh": warehouse_last_refresh,
            "metrics": metrics_freshness,
            "dashboard_freshness": f"Data as of {latest_period}",
        },
        "meta": {
            "request_id": str(uuid4()),
            "timestamp": date.today().isoformat() + "T00:00:00Z",
            "version": "1.0.0",
        },
    }
