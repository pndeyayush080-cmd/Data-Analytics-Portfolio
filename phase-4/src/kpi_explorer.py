#!/usr/bin/env python
"""
Self-Service KPI Explorer — Phase 4 Day 18
==========================================

Streamlit dashboard for authorized exploration of workforce and business
metrics. Reads exclusively from the privacy-safe deployment database
(phase-3/data/warehouse/pulseiq_public.duckdb) in read-only mode.

Role-based access control is enforced at the data/query layer, not merely
by hiding UI elements. A default-deny policy is used: roles only see
explicitly permitted KPIs.

IMPORTANT: The role selector in the sidebar is a development/demo
mechanism. No authentication system exists in this codebase. Do not treat
role selection as secure production authentication.
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Role configuration
# ---------------------------------------------------------------------------
# Each role lists the KPI keys it is permitted to view. Unknown roles get
# no access (default-deny).
ROLE_CONFIG = {
    "Executive": {
        "description": "High-level organizational KPIs",
        "kpis": [
            "headcount",
            "employer_cost",
            "overtime_pay",
            "overtime_share_pct",
            "attendance_rate_pct",
            "total_leave_days",
            "attrition_rate_monthly_pct",
            "cost_per_head",
        ],
    },
    "Manager": {
        "description": "Departmental KPIs",
        "kpis": [
            "headcount",
            "attendance_rate_pct",
            "total_leave_days",
        ],
    },
    "Analyst": {
        "description": "All analytical metrics",
        "kpis": [
            "headcount",
            "employer_cost",
            "overtime_pay",
            "overtime_share_pct",
            "attendance_rate_pct",
            "total_leave_days",
            "attrition_rate_monthly_pct",
            "cost_per_head",
        ],
    },
}

# KPI metadata: column name, unit, aggregation, and display name.
# All columns come from star_schema.dept_month_combined in the public DB.
KPI_METADATA = {
    "headcount": {
        "name": "Headcount",
        "column": "headcount_end",
        "unit": "count",
        "agg": "SUM",
        "metric_type": "stock",
    },
    "employer_cost": {
        "name": "Employer Cost",
        "column": "employer_cost",
        "unit": "INR",
        "agg": "SUM",
        "metric_type": "flow",
    },
    "overtime_pay": {
        "name": "Overtime Pay",
        "column": "overtime_pay",
        "unit": "INR",
        "agg": "SUM",
        "metric_type": "flow",
    },
    "overtime_share_pct": {
        "name": "Overtime Share",
        "column": "overtime_share_pct",
        "unit": "%",
        "agg": "AVG",
        "metric_type": "rate",
    },
    "attendance_rate_pct": {
        "name": "Attendance Rate",
        "column": "attendance_rate_pct",
        "unit": "%",
        "agg": "AVG",
        "metric_type": "rate",
    },
    "total_leave_days": {
        "name": "Total Leave Days",
        "column": "total_leave_days",
        "unit": "count",
        "agg": "SUM",
        "metric_type": "flow",
    },
    "attrition_rate_monthly_pct": {
        "name": "Attrition Rate",
        "column": "attrition_rate_monthly_pct",
        "unit": "%",
        "agg": "AVG",
        "metric_type": "rate",
    },
    "cost_per_head": {
        "name": "Cost Per Head",
        "column": "cost_per_head",
        "unit": "INR",
        "agg": "AVG",
        "metric_type": "rate",
    },
}

# Privacy threshold: suppress any department-month group with fewer than
# this many employees. Prevents recovery of individual employee data.
MIN_HEADCOUNT = 5

TABLE_NAME = "star_schema.dept_month_combined"

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

WAREHOUSE_PATH = (
    SCRIPT_DIR.parent.parent / "phase-3" / "data" / "warehouse" / "pulseiq_public.duckdb"
)


def get_connection():
    """Open a read-only DuckDB connection to the public deployment database.

    Raises FileNotFoundError if the database file does not exist.
    The connection is read-only; no writes are possible.
    """
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found: {WAREHOUSE_PATH}"
        )
    return duckdb.connect(str(WAREHOUSE_PATH), read_only=True)


# ---------------------------------------------------------------------------
# Role-based access helpers
# ---------------------------------------------------------------------------
def get_role_kpis(role: str) -> list[str]:
    """Return the list of KPI keys a role is permitted to view.

    Unknown roles return an empty list (default-deny).
    """
    role_config = ROLE_CONFIG.get(role)
    if role_config is None:
        return []
    return list(role_config["kpis"])


def is_kpi_allowed(role: str, kpi_key: str) -> bool:
    """Return True if the role is permitted to view the given KPI."""
    return kpi_key in get_role_kpis(role)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def fetch_kpi_data(
    con,
    kpi_keys: list[str],
    month_filter: str,
    dept_filter: str,
) -> pd.DataFrame:
    """Fetch KPI data for the given keys, filtered by month and department.

    Only KPIs present in ``kpi_keys`` are selected. Every query includes the
    privacy filter ``headcount_end >= MIN_HEADCOUNT`` so that small groups
    (fewer than 5 employees) are excluded at the database level.
    """
    if not kpi_keys:
        return pd.DataFrame()

    select_parts = ["month", "department_id", "department_name"]
    for kpi_key in kpi_keys:
        meta = KPI_METADATA[kpi_key]
        col = meta["column"]
        agg = meta["agg"]
        select_parts.append(f"{agg}({col}) AS {kpi_key}")

    select_clause = ", ".join(select_parts)

    query = f"""
        SELECT
            {select_clause}
        FROM {TABLE_NAME}
        WHERE headcount_end >= {MIN_HEADCOUNT}
          AND 1=1
          {month_filter}
          {dept_filter}
        GROUP BY month, department_id, department_name
        ORDER BY month, department_name
    """

    df = con.execute(query).fetchdf()

    if not df.empty and "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])

    return df


def compute_department_comparison(
    con,
    kpi_keys: list[str],
    month_filter: str,
    dept_filter: str,
) -> pd.DataFrame:
    """Compute department-level comparison values for the selected KPIs.

    Stock KPIs (headcount) use the latest month's value per department.
    Flow KPIs use SUM across the selected period.
    Rate KPIs use AVG across the selected period.

    Returns a DataFrame with one row per department and one column per KPI.
    """
    if not kpi_keys:
        return pd.DataFrame()

    # Separate KPIs by metric type
    stock_kpis = [
        k for k in kpi_keys if KPI_METADATA[k].get("metric_type") == "stock"
    ]
    agg_kpis = [
        k
        for k in kpi_keys
        if KPI_METADATA[k].get("metric_type") in ("flow", "rate")
    ]

    # --- Stock KPIs: latest month value per department ---
    stock_df = pd.DataFrame()
    if stock_kpis:
        latest_month_row = con.execute(
            f"""
            SELECT MAX(month) FROM {TABLE_NAME}
            WHERE headcount_end >= {MIN_HEADCOUNT}
              AND 1=1
              {month_filter}
              {dept_filter}
            """
        ).fetchone()

        if latest_month_row and latest_month_row[0] is not None:
            latest_month = latest_month_row[0]
            stock_select = ", ".join(
                [
                    f"{KPI_METADATA[k]['agg']}({KPI_METADATA[k]['column']}) AS {k}"
                    for k in stock_kpis
                ]
            )
            stock_query = f"""
                SELECT department_name, {stock_select}
                FROM {TABLE_NAME}
                WHERE month = DATE '{latest_month.strftime('%Y-%m-%d')}'
                  AND headcount_end >= {MIN_HEADCOUNT}
                  AND 1=1
                  {dept_filter}
                GROUP BY department_name
                ORDER BY department_name
            """
            stock_df = con.execute(stock_query).fetchdf()

    # --- Flow/Rate KPIs: aggregated across period ---
    agg_df = pd.DataFrame()
    if agg_kpis:
        select_parts = ["department_name"]
        for kpi_key in agg_kpis:
            meta = KPI_METADATA[kpi_key]
            col = meta["column"]
            agg = meta["agg"]
            select_parts.append(f"{agg}({col}) AS {kpi_key}")

        select_clause = ", ".join(select_parts)
        agg_query = f"""
            SELECT
                {select_clause}
            FROM {TABLE_NAME}
            WHERE headcount_end >= {MIN_HEADCOUNT}
              AND 1=1
              {month_filter}
              {dept_filter}
            GROUP BY department_name
            ORDER BY department_name
        """
        agg_df = con.execute(agg_query).fetchdf()

    # --- Merge stock and aggregate data ---
    if not stock_df.empty and not agg_df.empty:
        result = stock_df.merge(agg_df, on="department_name", how="outer")
    elif not stock_df.empty:
        result = stock_df
    elif not agg_df.empty:
        result = agg_df
    else:
        result = pd.DataFrame()

    return result


def compute_monthly_trend(
    con,
    kpi_keys: list[str],
    month_filter: str,
    dept_filter: str,
) -> pd.DataFrame:
    """Compute monthly trend data for selected KPIs.

    Returns a DataFrame with columns: month (datetime), month_str (str),
    department_name, and one column per KPI.
    """
    df = fetch_kpi_data(con, kpi_keys, month_filter, dept_filter)
    if df.empty:
        return pd.DataFrame()

    df["month_str"] = df["month"].dt.strftime("%Y-%m")
    return df


def get_available_months(con) -> list[str]:
    """Return sorted list of available month strings (YYYY-MM)."""
    df = con.execute(
        f"""
        SELECT DISTINCT month
        FROM {TABLE_NAME}
        WHERE month IS NOT NULL
        ORDER BY month
        """
    ).fetchdf()
    if df.empty:
        return []
    return pd.to_datetime(df["month"]).dt.strftime("%Y-%m").tolist()


def get_departments(con) -> list[dict]:
    """Return list of department dicts (id, name)."""
    df = con.execute(
        f"""
        SELECT DISTINCT
            department_id,
            department_name
        FROM {TABLE_NAME}
        WHERE department_id IS NOT NULL
        ORDER BY department_id
        """
    ).fetchdf()
    return df.to_dict("records")


def build_filters(start_month, end_month, selected_dept_ids):
    """Build SQL filter fragments from sidebar selections."""
    dept_filter = ""
    if selected_dept_ids:
        dept_values = ", ".join(
            "'" + str(d).replace("'", "''") + "'"
            for d in selected_dept_ids
        )
        dept_filter = f"AND department_id IN ({dept_values})"

    month_filter = (
        f"AND month >= DATE '{start_month}-01' "
        f"AND month <= DATE '{end_month}-01'"
    )
    return month_filter, dept_filter


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------
def format_kpi_value(value, unit: str) -> str:
    """Format a numeric KPI value for display."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    if unit == "count":
        return f"{int(value):,}"
    if unit == "INR":
        return f"₹{value:,.2f}"
    if unit == "%":
        return f"{value:.2f}%"
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def render_kpi_cards(con, kpi_keys: list[str], month_filter: str, dept_filter: str):
    """Render KPI cards for the latest month."""
    latest_query = f"""
        SELECT month
        FROM {TABLE_NAME}
        WHERE headcount_end >= {MIN_HEADCOUNT}
          AND 1=1
          {month_filter}
          {dept_filter}
        ORDER BY month DESC
        LIMIT 1
    """
    latest_row = con.execute(latest_query).fetchone()
    if latest_row is None:
        st.info("No data available for the selected filters.")
        return

    latest_month = latest_row[0]

    cards = []
    for kpi_key in kpi_keys:
        meta = KPI_METADATA[kpi_key]
        col = meta["column"]
        agg = meta["agg"]
        unit = meta["unit"]

        val_query = f"""
            SELECT {agg}({col})
            FROM {TABLE_NAME}
            WHERE month = DATE '{latest_month.strftime("%Y-%m-%d")}'
              AND headcount_end >= {MIN_HEADCOUNT}
              AND 1=1
              {dept_filter}
        """
        val = con.execute(val_query).fetchone()[0]

        cards.append((meta["name"], format_kpi_value(val, unit), unit))

    # Display cards in rows of 4
    for i in range(0, len(cards), 4):
        row_cards = cards[i : i + 4]
        cols = st.columns(len(row_cards))
        for col, (name, value, unit) in zip(cols, row_cards):
            col.metric(name, value)


def render_monthly_trend(
    con, kpi_keys: list[str], month_filter: str, dept_filter: str
):
    """Render monthly trend line charts for selected KPIs.

    Each KPI gets its own chart with its own y-axis scale, so values with
    different units and magnitudes are not visually compared on the same
    scale.
    """
    df = compute_monthly_trend(con, kpi_keys, month_filter, dept_filter)
    if df.empty:
        st.info("No trend data available for the selected filters.")
        return

    kpi_cols = [k for k in kpi_keys if k in df.columns]
    if not kpi_cols:
        st.info("No KPI data columns available.")
        return

    for kpi_key in kpi_cols:
        meta = KPI_METADATA[kpi_key]
        kpi_df = df[["month_str", "department_name", kpi_key]].copy()
        kpi_df = kpi_df.rename(columns={kpi_key: "value"})
        kpi_df = kpi_df.dropna(subset=["value"])

        if kpi_df.empty:
            continue

        fig = px.line(
            kpi_df,
            x="month_str",
            y="value",
            color="department_name",
            title=f"{meta['name']} Monthly Trend ({meta['unit']})",
        )
        fig.update_xaxes(tickangle=45)
        fig.update_yaxes(title=f"{meta['name']} ({meta['unit']})")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)


def render_department_comparison(
    con, kpi_keys: list[str], month_filter: str, dept_filter: str
):
    """Render department-level comparison bar charts.

    Stock KPIs (headcount) use the latest month's value per department.
    Flow KPIs use SUM across the selected period.
    Rate KPIs use AVG across the selected period.
    """
    if not kpi_keys:
        st.info("No KPIs selected for comparison.")
        return

    df = compute_department_comparison(con, kpi_keys, month_filter, dept_filter)
    if df.empty:
        st.info("No department comparison data available.")
        return

    kpi_cols = [k for k in kpi_keys if k in df.columns]
    if not kpi_cols:
        st.info("No comparison data columns available.")
        return

    # Show one bar chart per KPI
    for kpi_key in kpi_cols:
        meta = KPI_METADATA[kpi_key]
        fig = px.bar(
            df,
            x="department_name",
            y=kpi_key,
            color=kpi_key,
            title=f"{meta['name']} by Department ({meta['unit']})",
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Aura Workforce — Self-Service KPI Explorer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📊 Self-Service KPI Explorer")
    st.markdown(
        "Department-month workforce analytics. "
        "Select a role, month range, and departments to explore KPIs."
    )

    # Privacy disclosure (preserved from Day 17 dashboard)
    st.info(
        "Small-group departments with fewer than five employees are excluded "
        "from published departmental metrics to protect employee privacy. "
        "Reported totals reflect eligible published departments only."
    )

    # --- Role selection (development/demo, not production auth) ---
    st.sidebar.header("🔐 Access Control (Demo)")
    st.sidebar.caption(
        "Role selection is a development/demo mechanism. "
        "No production authentication system exists."
    )
    role = st.sidebar.radio(
        "Select role",
        options=["Executive", "Manager", "Analyst"],
        index=0,
        help="Determines which KPIs are available. "
             "Access is enforced at the query layer.",
    )

    role_kpis = get_role_kpis(role)
    if not role_kpis:
        st.error(
            f"Role '{role}' has no permitted KPIs. "
            "Contact your administrator."
        )
        return

    # Show which KPIs are available for this role
    with st.sidebar.expander("Available KPIs for this role", expanded=False):
        for k in role_kpis:
            meta = KPI_METADATA[k]
            st.write(f"• {meta['name']} ({meta['unit']})")

    # --- Data filters ---
    st.sidebar.header("🔍 Data Filters")

    con = get_connection()
    try:
        months = get_available_months(con)
        departments = get_departments(con)
    except Exception as exc:
        st.error(f"Unable to load filter options: {exc}")
        return
    finally:
        con.close()

    if not months:
        st.warning("No month data available.")
        return
    if not departments:
        st.warning("No department data available.")
        return

    start_month, end_month = st.sidebar.select_slider(
        "Month Range",
        options=months,
        value=(months[0], months[-1]),
    )

    dept_labels = [
        f"{d['department_id']} - {d['department_name']}"
        for d in departments
    ]
    dept_ids = [d["department_id"] for d in departments]

    selected_labels = st.sidebar.multiselect(
        "Departments",
        options=dept_labels,
        default=dept_labels,
    )

    selected_dept_ids = [
        dept_ids[dept_labels.index(label)]
        for label in selected_labels
    ]

    if not selected_dept_ids:
        st.warning("Select at least one department.")
        return

    # --- KPI selection (filtered by role) ---
    st.sidebar.header("📊 KPI Selection")

    kpi_options = {
        k: KPI_METADATA[k]["name"] for k in role_kpis
    }

    selected_kpi_keys = st.sidebar.multiselect(
        "Select KPIs",
        options=list(kpi_options.keys()),
        default=list(kpi_options.keys()),
        format_func=lambda k: kpi_options[k],
    )

    if not selected_kpi_keys:
        st.warning("Select at least one KPI.")
        return

    # Enforce role-based access at the application layer as well
    selected_kpi_keys = [k for k in selected_kpi_keys if is_kpi_allowed(role, k)]
    if not selected_kpi_keys:
        st.error("No permitted KPIs selected for this role.")
        return

    # --- Build filters and connect ---
    month_filter, dept_filter = build_filters(
        start_month, end_month, selected_dept_ids
    )

    con = get_connection()
    try:
        # --- KPI Cards ---
        st.subheader("📈 Key Metrics (Latest Month)")
        render_kpi_cards(con, selected_kpi_keys, month_filter, dept_filter)

        st.divider()

        # --- Monthly Trends ---
        st.subheader("📉 Monthly Trends")
        render_monthly_trend(con, selected_kpi_keys, month_filter, dept_filter)

        st.divider()

        # --- Department Comparison ---
        st.subheader("🏢 Department Comparison")
        render_department_comparison(con, selected_kpi_keys, month_filter, dept_filter)

    except Exception as exc:
        st.error(f"Explorer error: {exc}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
