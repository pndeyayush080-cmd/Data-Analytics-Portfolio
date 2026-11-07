
"""
PQ-13 Cross-Department Impact Dashboard

Streamlit dashboard combining:
- Headcount
- Payroll
- Attendance
- Leave
- Overtime and attrition correlations

Data source:
star_schema.dept_month_combined
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="PQ-13 Cross-Department Impact Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# 2. DATABASE CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

WAREHOUSE_PATH = (
    SCRIPT_DIR.parent
    / "data"
    / "warehouse"
    / "pulseiq_clean.duckdb"
)

TABLE_NAME = "star_schema.dept_month_combined"


def get_connection():
    """Open a read-only DuckDB connection."""

    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found: {WAREHOUSE_PATH}"
        )

    return duckdb.connect(
        str(WAREHOUSE_PATH),
        read_only=True
    )


# ============================================================
# 3. DATABASE LOOKUPS
# ============================================================

@st.cache_data(ttl=300)
def get_available_months():

    con = get_connection()

    try:
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

        return (
            pd.to_datetime(df["month"])
            .dt.strftime("%Y-%m")
            .tolist()
        )

    finally:
        con.close()


@st.cache_data(ttl=300)
def get_departments():

    con = get_connection()

    try:
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

    finally:
        con.close()


# ============================================================
# 4. FILTER GENERATION
# ============================================================

def build_filters(
    start_month,
    end_month,
    selected_dept_ids
):
    """Build SQL filters from the sidebar selections."""

    dept_filter = ""

    if selected_dept_ids:

        dept_values = ", ".join(
            "'" + str(d).replace("'", "''") + "'"
            for d in selected_dept_ids
        )

        dept_filter = (
            f"AND department_id IN ({dept_values})"
        )

    month_filter = (
        f"AND month >= DATE '{start_month}-01' "
        f"AND month <= DATE '{end_month}-01'"
    )

    return month_filter, dept_filter


# ============================================================
# 5. COMMON DATA HELPERS
# ============================================================

def show_empty_message(df, message):

    if df.empty:
        st.info(message)
        return True

    return False


def format_month_column(df):

    if not df.empty and "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])

    return df


def fetch_department_month_data(
    con,
    columns,
    month_filter,
    dept_filter,
    extra_filter=""
):
    """Fetch filtered department-month data."""

    query = f"""
        SELECT
            {columns}
        FROM {TABLE_NAME}
        WHERE 1=1
        {month_filter}
        {dept_filter}
        {extra_filter}
        ORDER BY month, department_name
    """

    return format_month_column(
        con.execute(query).fetchdf()
    )


# ============================================================
# 6. EXECUTIVE OVERVIEW
# ============================================================

def render_overview(con, month_filter, dept_filter):

    st.subheader("📊 Executive Overview")

    # --------------------------------------------------------
    # KPI calculation
    # --------------------------------------------------------

    latest_headcount_query = f"""
        WITH latest_month AS (
            SELECT MAX(month) AS latest_month
            FROM {TABLE_NAME}
            WHERE 1=1
            {month_filter}
            {dept_filter}
        )
        SELECT
            SUM(headcount_end)
        FROM {TABLE_NAME}
        WHERE month = (
            SELECT latest_month FROM latest_month
        )
        {dept_filter}
    """

    headcount = (
        con.execute(latest_headcount_query).fetchone()[0]
        or 0
    )

    kpi_query = f"""
        SELECT
            SUM(employer_cost),
            SUM(overtime_pay),
            SUM(present_days),
            SUM(scheduled_days),
            SUM(total_leave_days),
            AVG(attrition_rate_monthly_pct)
        FROM {TABLE_NAME}
        WHERE 1=1
        {month_filter}
        {dept_filter}
    """

    kpis = con.execute(kpi_query).fetchone()

    employer_cost = kpis[0] or 0
    overtime_pay = kpis[1] or 0
    present_days = kpis[2] or 0
    scheduled_days = kpis[3] or 0
    total_leave_days = kpis[4] or 0
    avg_attrition = kpis[5] or 0

    attendance = (
        present_days / scheduled_days * 100
        if scheduled_days else 0
    )

    # --------------------------------------------------------
    # KPI cards
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    col1.metric(
        "Latest Headcount",
        f"{int(headcount):,}"
    )

    col2.metric(
        "Employer Cost",
        f"₹{employer_cost / 1e7:.2f} Cr"
    )

    col3.metric(
        "Overtime Pay",
        f"₹{overtime_pay / 1e7:.2f} Cr"
    )

    col4.metric(
        "Weighted Attendance",
        f"{attendance:.2f}%"
    )

    col5.metric(
        "Total Leave Days",
        f"{total_leave_days:,.0f}"
    )

    col6.metric(
        "Average Monthly Attrition",
        f"{avg_attrition or 0:.2f}%"
    )

    # --------------------------------------------------------
    # Monthly trend
    # --------------------------------------------------------

    trend_query = f"""
        SELECT
            month,
            SUM(headcount_end) AS total_headcount,
            SUM(employer_cost) AS total_cost,
            SUM(overtime_pay) AS total_overtime,
            SUM(present_days) AS present_days,
            SUM(scheduled_days) AS scheduled_days
        FROM {TABLE_NAME}
        WHERE 1=1
        {month_filter}
        {dept_filter}
        GROUP BY month
        ORDER BY month
    """

    trend_df = format_month_column(
        con.execute(trend_query).fetchdf()
    )

    if show_empty_message(
        trend_df,
        "No monthly trend data available."
    ):
        return

    trend_df["month_str"] = (
        trend_df["month"].dt.strftime("%Y-%m")
    )

    trend_df["total_cost_cr"] = (
        trend_df["total_cost"] / 1e7
    )

    # Two-axis chart

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=trend_df["month_str"],
            y=trend_df["total_headcount"],
            name="Headcount"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=trend_df["month_str"],
            y=trend_df["total_cost_cr"],
            name="Employer Cost (Cr)",
            mode="lines+markers",
            yaxis="y2"
        )
    )

    fig.update_layout(
        title="Monthly Headcount and Employer Cost",
        xaxis_title="Month",
        yaxis=dict(title="Headcount"),
        yaxis2=dict(
            title="Employer Cost (Cr)",
            overlaying="y",
            side="right"
        ),
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # --------------------------------------------------------
    # Department comparison
    # --------------------------------------------------------

    dept_query = f"""
        SELECT
            department_id,
            department_name,
            SUM(employer_cost) AS total_cost,
            SUM(headcount_end) AS cumulative_headcount,
            AVG(attrition_rate_monthly_pct) AS avg_attrition,
            AVG(overtime_share_pct) AS avg_overtime_share,
            AVG(attendance_rate_pct) AS avg_attendance,
            AVG(leave_days_per_head) AS avg_leave_per_head
        FROM {TABLE_NAME}
        WHERE 1=1
        {month_filter}
        {dept_filter}
        GROUP BY department_id, department_name
        ORDER BY total_cost DESC
    """

    dept_df = con.execute(dept_query).fetchdf()

    if dept_df.empty:
        return

    col1, col2 = st.columns(2)

    with col1:

        fig = px.bar(
            dept_df,
            x="department_name",
            y="total_cost",
            title="Employer Cost by Department",
            color="total_cost"
        )

        fig.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with col2:

        fig = px.bar(
            dept_df,
            x="department_name",
            y="avg_attrition",
            title="Average Monthly Attrition by Department",
            color="avg_attrition"
        )

        fig.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ============================================================
# 7. HEADCOUNT ANALYTICS
# ============================================================

def render_headcount(con, month_filter, dept_filter):

    st.subheader("👥 Headcount Analytics")

    columns = """
        month,
        department_name,
        headcount_start,
        hires,
        exits,
        voluntary_exits,
        transfers_in,
        transfers_out,
        headcount_end,
        attrition_rate_monthly_pct,
        attrition_rate_rolling_12m_pct,
        voluntary_attrition_rate_12m_pct
    """

    df = fetch_department_month_data(
        con,
        columns,
        month_filter,
        dept_filter,
        "AND headcount_end > 0"
    )

    if show_empty_message(df, "No headcount data available."):
        return

    fig = px.line(
        df,
        x="month",
        y="headcount_end",
        color="department_name",
        title="Headcount Trend by Department"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        df,
        x="month",
        y="attrition_rate_monthly_pct",
        color="department_name",
        title="Monthly Attrition Rate"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        df,
        x="month",
        y="attrition_rate_rolling_12m_pct",
        color="department_name",
        title="Rolling 12-Month Attrition Rate"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Hires versus exits

    movement_df = df.melt(
        id_vars=["month", "department_name"],
        value_vars=["hires", "exits"],
        var_name="movement_type",
        value_name="employee_count"
    )

    fig = px.bar(
        movement_df,
        x="month",
        y="employee_count",
        color="movement_type",
        facet_col="department_name",
        facet_col_wrap=3,
        barmode="group",
        title="Monthly Hires vs Exits by Department"
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 8. PAYROLL ANALYTICS
# ============================================================

def render_payroll(con, month_filter, dept_filter):

    st.subheader("💰 Payroll Analytics")

    columns = """
        month,
        department_name,
        employees_paid,
        gross_pay,
        net_pay,
        employer_cost,
        overtime_pay,
        variable_pay,
        overtime_hours_paid,
        overtime_share_pct,
        cost_per_head,
        variable_pay_share_pct,
        headcount_end
    """

    df = fetch_department_month_data(
        con,
        columns,
        month_filter,
        dept_filter,
        "AND employees_paid > 0"
    )

    if show_empty_message(df, "No payroll data available."):
        return

    fig = px.line(
        df,
        x="month",
        y="employer_cost",
        color="department_name",
        title="Employer Cost Trend"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        df,
        x="month",
        y="cost_per_head",
        color="department_name",
        title="Cost Per Head by Department"
    )

    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:

        fig = px.line(
            df,
            x="month",
            y="overtime_share_pct",
            color="department_name",
            title="Overtime Share %"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:

        fig = px.bar(
            df,
            x="month",
            y="overtime_pay",
            color="department_name",
            title="Overtime Pay by Department"
        )

        st.plotly_chart(fig, use_container_width=True)

    # Latest-month cost per head

    latest_month = df["month"].max()

    latest = df[df["month"] == latest_month]

    fig = px.scatter(
        latest,
        x="headcount_end",
        y="cost_per_head",
        size="employer_cost",
        color="department_name",
        hover_data=[
            "department_name",
            "employees_paid"
        ],
        title="Cost Per Head vs Headcount (Latest Month)"
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 9. ATTENDANCE ANALYTICS
# ============================================================

def render_attendance(con, month_filter, dept_filter):

    st.subheader("📅 Attendance Analytics")

    columns = """
        month,
        department_name,
        scheduled_days,
        present_days,
        wfh_days,
        half_days_unpaid,
        paid_leave_days,
        unpaid_absence_days,
        late_arrivals,
        attendance_rate_pct,
        late_arrival_rate_pct,
        overtime_hours
    """

    df = fetch_department_month_data(
        con,
        columns,
        month_filter,
        dept_filter,
        "AND scheduled_days > 0"
    )

    if show_empty_message(df, "No attendance data available."):
        return

    fig = px.line(
        df,
        x="month",
        y="attendance_rate_pct",
        color="department_name",
        title="Attendance Rate Trend"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        df,
        x="month",
        y="late_arrival_rate_pct",
        color="department_name",
        title="Late Arrival Rate by Department"
    )

    st.plotly_chart(fig, use_container_width=True)

    attendance_long = df.melt(
        id_vars=["month", "department_name"],
        value_vars=["scheduled_days", "present_days"],
        var_name="day_type",
        value_name="days"
    )

    fig = px.bar(
        attendance_long,
        x="month",
        y="days",
        color="day_type",
        facet_col="department_name",
        facet_col_wrap=3,
        barmode="group",
        title="Scheduled vs Present Days"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.bar(
        df,
        x="month",
        y="late_arrivals",
        color="department_name",
        title="Late Arrivals by Department"
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 10. LEAVE ANALYTICS
# ============================================================

def render_leave(con, month_filter, dept_filter):

    st.subheader("🏖️ Leave Analytics")

    columns = """
        month,
        department_name,
        medical_leave_days,
        annual_leave_days,
        lop_days,
        other_leave_days,
        total_leave_days,
        leave_days_per_head,
        headcount_end
    """

    df = fetch_department_month_data(
        con,
        columns,
        month_filter,
        dept_filter,
        "AND total_leave_days > 0"
    )

    if show_empty_message(df, "No leave data available."):
        return

    fig = px.line(
        df,
        x="month",
        y="leave_days_per_head",
        color="department_name",
        title="Leave Days Per Head by Department"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Leave composition

    leave_long = df.melt(
        id_vars=["month", "department_name"],
        value_vars=[
            "medical_leave_days",
            "annual_leave_days",
            "lop_days",
            "other_leave_days"
        ],
        var_name="leave_type",
        value_name="leave_days"
    )

    fig = px.bar(
        leave_long,
        x="month",
        y="leave_days",
        color="leave_type",
        facet_col="department_name",
        facet_col_wrap=3,
        title="Leave Composition by Department"
    )

    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        df,
        x="month",
        y="lop_days",
        color="department_name",
        title="Leave Without Pay (LOP) Days"
    )

    st.plotly_chart(fig, use_container_width=True)

    latest_month = df["month"].max()

    latest = df[df["month"] == latest_month]

    fig = px.scatter(
        latest,
        x="headcount_end",
        y="leave_days_per_head",
        size="total_leave_days",
        color="department_name",
        hover_data=[
            "department_name",
            "total_leave_days"
        ],
        title="Leave Days Per Head vs Headcount"
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 11. CORRELATION ANALYTICS
# ============================================================

def render_correlations(con, month_filter, dept_filter):

    st.subheader("🔗 Overtime vs Attrition Correlation Analysis")

    # --------------------------------------------------------
    # Monthly correlation
    # --------------------------------------------------------

    query = f"""
        SELECT
            month,

            CORR(
                overtime_share_pct,
                attrition_rate_monthly_pct
            ) AS monthly_corr,

            CORR(
                overtime_share_pct,
                attrition_rate_rolling_12m_pct
            ) AS rolling_corr

        FROM {TABLE_NAME}

        WHERE headcount_end >= 5
        {month_filter}
        {dept_filter}

        AND overtime_share_pct IS NOT NULL
        AND attrition_rate_monthly_pct IS NOT NULL

        GROUP BY month
        ORDER BY month
    """

    corr_df = format_month_column(
        con.execute(query).fetchdf()
    )

    if show_empty_message(
        corr_df,
        "Insufficient data for monthly correlation analysis."
    ):
        return

    fig = px.line(
        corr_df,
        x="month",
        y=["monthly_corr", "rolling_corr"],
        title="Overtime vs Attrition Correlation Over Time"
    )

    st.plotly_chart(fig, use_container_width=True)

    # --------------------------------------------------------
    # Department-level comparison
    # --------------------------------------------------------

    dept_corr_query = f"""
        SELECT
            department_id,
            department_name,

            AVG(overtime_share_pct)
                AS avg_overtime_share,

            AVG(attrition_rate_monthly_pct)
                AS avg_attrition,

            AVG(attrition_rate_rolling_12m_pct)
                AS avg_rolling_attrition,

            AVG(voluntary_attrition_rate_12m_pct)
                AS avg_voluntary_attrition,

            AVG(overtime_pay)
                AS avg_overtime_pay,

            AVG(employer_cost)
                AS avg_employer_cost,

            AVG(headcount_end)
                AS avg_headcount

        FROM {TABLE_NAME}

        WHERE headcount_end >= 5
        {month_filter}
        {dept_filter}

        AND overtime_share_pct IS NOT NULL
        AND attrition_rate_monthly_pct IS NOT NULL

        GROUP BY department_id, department_name

        ORDER BY department_id
    """

    dept_corr = con.execute(
        dept_corr_query
    ).fetchdf()

    if show_empty_message(
        dept_corr,
        "No department-level correlation data available."
    ):
        return

    col1, col2 = st.columns(2)

    with col1:

        fig = px.scatter(
            dept_corr,
            x="avg_overtime_share",
            y="avg_attrition",
            size="avg_headcount",
            color="department_name",
            hover_data=["department_name"],
            title="Overtime Share vs Monthly Attrition"
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:

        fig = px.scatter(
            dept_corr,
            x="avg_overtime_share",
            y="avg_rolling_attrition",
            size="avg_headcount",
            color="department_name",
            hover_data=["department_name"],
            title="Overtime Share vs Rolling 12M Attrition"
        )

        st.plotly_chart(fig, use_container_width=True)

    # Department-level data table

    st.subheader("Department-Level Correlation Summary")

    st.dataframe(
        dept_corr.round(2),
        use_container_width=True
    )


# ============================================================
# 12. MAIN APPLICATION
# ============================================================

def main():

    st.title(
        "📊 PQ-13 Cross-Department Impact Dashboard"
    )

    st.markdown(
        "**Department-Month Analytics** | "
        "Headcount • Payroll • Attendance • Leave"
    )

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    st.sidebar.header("🔍 Dashboard Filters")

    try:
        months = get_available_months()
        departments = get_departments()

    except Exception as exc:
        st.error(
            f"Unable to load dashboard filters: {exc}"
        )
        return

    if not months:
        st.warning("No month data available.")
        return

    if not departments:
        st.warning("No department data available.")
        return

    start_month, end_month = st.sidebar.select_slider(
        "Month Range",
        options=months,
        value=(months[0], months[-1])
    )

    dept_labels = [
        f"{d['department_id']} - {d['department_name']}"
        for d in departments
    ]

    dept_ids = [
        d["department_id"]
        for d in departments
    ]

    selected_labels = st.sidebar.multiselect(
        "Departments",
        options=dept_labels,
        default=dept_labels
    )

    selected_dept_ids = [
        dept_ids[dept_labels.index(label)]
        for label in selected_labels
    ]

    if not selected_dept_ids:
        st.warning("Select at least one department.")
        return

    metric_category = st.sidebar.radio(
        "Metric Category",
        [
            "📊 Overview",
            "👥 Headcount",
            "💰 Payroll",
            "📅 Attendance",
            "🏖️ Leave",
            "🔗 Correlations"
        ]
    )

    month_filter, dept_filter = build_filters(
        start_month,
        end_month,
        selected_dept_ids
    )

    # --------------------------------------------------------
    # Database connection lifecycle
    # --------------------------------------------------------

    try:

        con = get_connection()

        try:

            if metric_category == "📊 Overview":

                render_overview(
                    con,
                    month_filter,
                    dept_filter
                )

            elif metric_category == "👥 Headcount":

                render_headcount(
                    con,
                    month_filter,
                    dept_filter
                )

            elif metric_category == "💰 Payroll":

                render_payroll(
                    con,
                    month_filter,
                    dept_filter
                )

            elif metric_category == "📅 Attendance":

                render_attendance(
                    con,
                    month_filter,
                    dept_filter
                )

            elif metric_category == "🏖️ Leave":

                render_leave(
                    con,
                    month_filter,
                    dept_filter
                )

            elif metric_category == "🔗 Correlations":

                render_correlations(
                    con,
                    month_filter,
                    dept_filter
                )

        finally:
            con.close()

    except Exception as exc:

        st.error(
            f"Dashboard execution failed: {exc}"
        )


# ============================================================
# 13. APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
