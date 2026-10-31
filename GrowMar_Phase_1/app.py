
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="PulseIQ | Workforce Overview",
    page_icon="📊",
    layout="wide",
)

DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

COLORS = {
    "primary": "#2563EB",
    "positive": "#0D9488",
    "attention": "#D97706",
}

st.title("PulseIQ | Workforce Overview")
st.caption("Workforce intelligence • Metric-layer governed data")

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()


@st.cache_data(ttl=300)
def load_view(view_name: str) -> pd.DataFrame:
    """Load data only from explicitly approved views."""
    allowed = {
        "m01_headcount",
        "m02_hires",
        "m03_exits",
        "m04_attrition_rate_monthly",
        "v_workforce_location_mix",
        "v_workforce_work_mode_mix",
    }

    if view_name not in allowed:
        raise ValueError("Unapproved view")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(f"SELECT * FROM {view_name}").df()
    finally:
        con.close()


try:
    headcount = load_view("m01_headcount")
    hires = load_view("m02_hires")
    exits = load_view("m03_exits")
    attrition = load_view("m04_attrition_rate_monthly")
    locations = load_view("v_workforce_location_mix")
    modes = load_view("v_workforce_work_mode_mix")
except Exception as exc:
    st.error(f"Could not load an approved dashboard view: {exc}")
    st.stop()


# Prepare metric dates.
for frame in [headcount, hires, exits, attrition]:
    if "month_start_date" in frame.columns:
        frame["month_start_date"] = pd.to_datetime(
            frame["month_start_date"]
        )

if headcount.empty:
    st.warning("No headcount data is available.")
    st.stop()


# Sidebar filters.
st.sidebar.header("Filters")

departments = sorted(
    headcount["department_id"].dropna().unique().tolist()
)

selected_departments = st.sidebar.multiselect(
    "Department",
    options=departments,
    default=departments,
)

min_date = headcount["month_start_date"].min().date()
max_date = headcount["month_start_date"].max().date()

date_range = st.sidebar.date_input(
    "Month range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Streamlit can return one or two dates while a range is being selected.
if isinstance(date_range, (tuple, list)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        st.info("Select a start and end date.")
        st.stop()
else:
    start_date = end_date = date_range

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)


def filter_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    return result.loc[
        result["department_id"].isin(selected_departments)
        & result["month_start_date"].between(start_ts, end_ts)
    ]


hc = filter_frame(headcount)
hi = filter_frame(hires)
ex = filter_frame(exits)
at = filter_frame(attrition)

if not selected_departments or hc.empty:
    st.warning(
        "No data matches these filters. "
        "Select another department or date range."
    )
    st.stop()


# KPI cards: latest month in the selected period.
latest_month = hc["month_start_date"].max()

latest_hc = hc.loc[
    hc["month_start_date"] == latest_month, "headcount"
].sum()

latest_hires = hi.loc[
    hi["month_start_date"] == latest_month, "hires"
].sum()

latest_exits = ex.loc[
    ex["month_start_date"] == latest_month, "exits"
].sum()

latest_attrition = at.loc[
    at["month_start_date"] == latest_month, "attrition_rate_pct"
].mean()

st.caption(f"Latest selected month: {latest_month:%B %Y}")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Month-end headcount", f"{latest_hc:,.0f}")
c2.metric("Hires", f"{latest_hires:,.0f}")
c3.metric("Exits", f"{latest_exits:,.0f}")

c4.metric(
    "Mean department attrition",
    (
        f"{latest_attrition:.2f}%"
        if pd.notna(latest_attrition)
        else "N/A"
    ),
)

st.divider()


# Chart 1: headcount trend.
trend = (
    hc.groupby("month_start_date", as_index=False)["headcount"]
    .sum()
    .sort_values("month_start_date")
)

fig_trend = px.line(
    trend,
    x="month_start_date",
    y="headcount",
    markers=True,
    title="Total month-end headcount across the selected period",
    labels={
        "month_start_date": "Month",
        "headcount": "Employees",
    },
)

fig_trend.update_traces(line_color=COLORS["primary"])
st.plotly_chart(fig_trend, width="stretch")

if len(trend) >= 2:
    change = int(
        trend["headcount"].iloc[-1] - trend["headcount"].iloc[0]
    )

    if change > 0:
        direction = "increased"
    elif change < 0:
        direction = "decreased"
    else:
        direction = "remained unchanged"

    st.caption(
        f"Insight: Headcount {direction} by {abs(change):,} employees "
        f"between {trend['month_start_date'].iloc[0]:%b %Y} "
        f"and {trend['month_start_date'].iloc[-1]:%b %Y}."
    )
else:
    st.caption(
        f"Insight: {len(trend)} month of headcount data is selected."
    )


# Chart 2: department mix.
dept = (
    hc.loc[hc["month_start_date"] == latest_month]
    .groupby("department_id", as_index=False)["headcount"]
    .sum()
    .sort_values("headcount", ascending=False)
)

fig_dept = px.bar(
    dept,
    x="department_id",
    y="headcount",
    title=f"Department workforce distribution in {latest_month:%b %Y}",
    labels={
        "department_id": "Department",
        "headcount": "Employees",
    },
    color_discrete_sequence=[COLORS["positive"]],
)

st.plotly_chart(fig_dept, width="stretch")

if not dept.empty:
    leader = dept.iloc[0]

    st.caption(
        f"Insight: {leader['department_id']} is the largest displayed "
        f"department with {leader['headcount']:,.0f} employees."
    )


# Current location and work-mode views are not historical.
# These charts intentionally do not respond to the date/department filters.
st.subheader("Current workforce distribution")

left, right = st.columns(2)

with left:
    if not locations.empty:
        loc = locations.sort_values(
            "employee_count", ascending=False
        )

        top_loc = loc.iloc[0]

        fig_loc = px.bar(
            loc,
            x="work_location",
            y="employee_count",
            title=(
                f"{top_loc['work_location']} has the largest "
                "current location workforce"
            ),
            labels={
                "work_location": "Location",
                "employee_count": "Employees",
            },
            color_discrete_sequence=[COLORS["primary"]],
        )

        st.plotly_chart(fig_loc, width="stretch")

        st.caption(
            f"Insight: {top_loc['work_location']} has "
            f"{top_loc['employee_count']:,} employees "
            "in the current location view."
        )
    else:
        st.info("No location data is available.")


with right:
    if not modes.empty:
        mode = modes.sort_values(
            "employee_count", ascending=False
        )

        top_mode = mode.iloc[0]

        fig_mode = px.bar(
            mode,
            x="work_mode",
            y="employee_count",
            title=(
                f"{top_mode['work_mode']} is the largest "
                "current work mode"
            ),
            labels={
                "work_mode": "Work mode",
                "employee_count": "Employees",
            },
            color_discrete_sequence=[COLORS["positive"]],
        )

        st.plotly_chart(fig_mode, width="stretch")

        st.caption(
            f"Insight: {top_mode['work_mode']} accounts for "
            f"{top_mode['employee_count']:,} employees "
            "in the current work-mode view."
        )
    else:
        st.info("No work-mode data is available.")


st.divider()

st.caption(
    "Governance: Official metrics M01–M04 and aggregated supporting "
    "views only. Employee-level payroll and raw fact tables are not "
    "queried by this app. Location/work-mode distributions show the "
    "current workforce, not historical assignments."
)
