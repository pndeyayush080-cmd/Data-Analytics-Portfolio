
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="PulseIQ | Workforce Breakdown",
    page_icon="👥",
    layout="wide",
)

DB_PATH = Path(__file__).resolve().parents[1] / "pulseiq.duckdb"

st.title("Workforce Breakdown")
st.caption("CEO questions and metric governance")

st.subheader("Five questions for the CEO")
questions = [
    "How has total headcount changed over time?",
    "Which departments have the largest workforces?",
    "How many employees were hired in the selected period?",
    "Which work locations have the largest employee populations?",
    "How is the workforce distributed across Hybrid, Onsite, and Remote work?",
]

for i, question in enumerate(questions, start=1):
    st.markdown(f"**{i}.** {question}")

st.divider()
st.subheader("Current location mix")

@st.cache_data(ttl=300)
def read_location_view():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(
            "SELECT work_location, employee_count "
            "FROM v_workforce_location_mix "
            "ORDER BY employee_count DESC"
        ).df()
    finally:
        con.close()

@st.cache_data(ttl=300)
def read_mode_view():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(
            "SELECT work_mode, employee_count "
            "FROM v_workforce_work_mode_mix "
            "ORDER BY employee_count DESC"
        ).df()
    finally:
        con.close()

try:
    locations = read_location_view()
    modes = read_mode_view()
except Exception as exc:
    st.error(f"Could not load approved supporting views: {exc}")
    st.stop()

left, right = st.columns(2)

with left:
    if not locations.empty:
        fig = px.bar(
            locations,
            x="work_location",
            y="employee_count",
            title="Current employee count by work location",
            labels={
                "work_location": "Location",
                "employee_count": "Employees",
            },
            color_discrete_sequence=["#2563EB"],
        )
        st.plotly_chart(fig, width="stretch")
        top = locations.iloc[0]
        st.caption(
            f"Insight: {top['work_location']} leads with "
            f"{top['employee_count']:,} employees."
        )

with right:
    if not modes.empty:
        fig = px.pie(
            modes,
            names="work_mode",
            values="employee_count",
            title="Current workforce by work mode",
            color_discrete_sequence=["#2563EB", "#0D9488", "#D97706"],
        )
        st.plotly_chart(fig, width="stretch")
        top = modes.iloc[0]
        st.caption(
            f"Insight: {top['work_mode']} is the largest work mode "
            f"with {top['employee_count']:,} employees."
        )

st.divider()
st.subheader("Data governance")
st.markdown(
    """
- **Official metrics:** M01–M04 from the Task 4 metric layer.
- **Supporting views:** `v_workforce_location_mix` and
  `v_workforce_work_mode_mix`.
- **Privacy:** Supporting views exclude groups with fewer than five employees.
- **Read-only:** The application opens DuckDB with `read_only=True`.
- **Historical limitation:** Location and work-mode views show the current
  active workforce, not historical workforce assignments.
- **Not included:** Employee-level payroll metrics M07–M09 and M15 are not
  exposed on this dashboard.
"""
)
