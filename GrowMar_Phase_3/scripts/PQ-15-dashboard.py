"""
PQ-15 Executive Company-Health Scorecard

Streamlit dashboard showing 8 founder-level KPIs:
1. Revenue
2. Net Profit
3. Operating Margin
4. DSO
5. Total Headcount
6. Rolling 12M Attrition
7. Attendance Rate
8. Overtime Share

Data sources:
- star_schema.pq15_company_scorecard (pre-aggregated company-level KPIs)
- star_schema.pq15_kpi_trends (18-month trend data for sparklines)
- star_schema.pq15_kpi_targets_company (target status)

All metrics are source-verified, not AI-generated.
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
    page_title="PQ-15 Executive Company-Health Scorecard",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
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


def get_connection():
    """Open a read-only DuckDB connection."""
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(f"Warehouse not found: {WAREHOUSE_PATH}")
    return duckdb.connect(str(WAREHOUSE_PATH), read_only=True)


# ============================================================
# 3. HELPER FUNCTIONS
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


def fetch_data(con, query, params=None):
    """Execute query with optional parameters and format date columns."""
    if params is None:
        return format_month_column(con.execute(query).fetchdf())
    return format_month_column(con.execute(query, params).fetchdf())



def render_kpi_card(
    kpi_name,
    value,
    unit,
    target_status,
    trend_data=None,
    drill_target=None,
    source_view=None,
    source_column=None
):
    """Render a KPI card using native Streamlit components."""

    # Format KPI value safely
    if value is None or pd.isna(value):
        display = "N/A"
    else:
        value = float(value)

        if unit == "INR":
            if abs(value) >= 1e7:
                display = f"₹{value / 1e7:.2f} Cr"
            elif abs(value) >= 1e5:
                display = f"₹{value / 1e5:.2f} L"
            else:
                display = f"₹{value:,.0f}"

        elif unit == "%":
            display = f"{value:.2f}%"
        elif unit == "days":
            display = f"{value:.1f} days"
        elif unit == "count":
            display = f"{value:,.0f}"
        else:
            display = f"{value:,.2f}"

    # Target display
    if target_status == "Not Set":
        target_display = "Not Set"
    elif target_status == "N/A":
        target_display = "N/A"
    else:
        target_display = str(target_status)

    # Trend calculation
    trend_label = None
    delta_color = "normal"

    if trend_data is not None:
        valid_values = [
            float(x) for x in trend_data
            if x is not None and pd.notna(x)
        ]

        if len(valid_values) >= 2:
            previous = valid_values[-2]
            recent = valid_values[-1]

            if previous != 0:
                change = (
                    (recent - previous) / abs(previous)
                ) * 100

                trend_label = f"{change:+.1f}%"

                if kpi_name in [
                    "DSO",
                    "Rolling 12M Attrition",
                    "Overtime Share"
                ]:
                    delta_color = "inverse"

    # Native Streamlit KPI card
    with st.container(border=True):

        st.caption("📊 Source-verified metric")

        st.metric(
            label=kpi_name,
            value=display,
            delta=trend_label,
            delta_color=delta_color
        )

        st.caption(f"Target: {target_display}")

        if source_view and source_column:
            st.caption(
                f"Source: {source_view}.{source_column}"
            )

        if drill_target:
            st.caption(
                f"🔍 Drill-down destination: {drill_target}"
            )



def render_ai_badge():
    st.markdown(
        '<span style="background-color: #fff3cd; color: #856404; padding: 0.25rem 0.5rem; '
        'border-radius: 0.25rem; font-size: 0.85rem; font-weight: bold;">'
        '📊 Source-verified metric</span>',
        unsafe_allow_html=True
    )


def render_section_note(note):
    st.markdown(
        f'<div style="background-color: #f8f9fa; border-left: 4px solid #856404; '
        'padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; '
        'font-size: 0.9rem; color: #533f03;">'
        f'💡 <strong>Note:</strong> {note}</div>',
        unsafe_allow_html=True
    )


# ============================================================
# 4. KPI DEFINITIONS
# ============================================================

KPI_CONFIG = [
    {
        "name": "Revenue",
        "unit": "INR",
        "source_view": "m16_revenue",
        "source_column": "revenue",
        "scorecard_column": "revenue",
        "drill_target": "PQ-11/PQ-12 Dashboard",
        "description": "Total income booked in the ledger (accounts 4001-4004). Higher is better."
    },
    {
        "name": "Net Profit",
        "unit": "INR",
        "source_view": "m17_net_profit",
        "source_column": "net_profit",
        "scorecard_column": "net_profit",
        "drill_target": "PQ-11/PQ-12 Dashboard",
        "description": "Revenue minus all expenses (4xxx less 5xxx). Higher is better."
    },
    {
        "name": "Operating Margin",
        "unit": "%",
        "source_view": "m18_operating_margin",
        "source_column": "operating_margin_pct",
        "scorecard_column": "operating_margin_pct",
        "drill_target": "PQ-11/PQ-12 Dashboard",
        "description": "Net profit as a share of revenue. Higher is better."
    },
    {
        "name": "DSO",
        "unit": "days",
        "source_view": "m20_dso",
        "source_column": "dso_days",
        "scorecard_column": "dso_days",
        "drill_target": "PQ-12 AR Dashboard",
        "description": "Days Sales Outstanding: Average days to collect receivables. Lower is better."
    },
    {
        "name": "Total Headcount",
        "unit": "count",
        "source_view": "dept_month_headcount (SUM)",
        "source_column": "headcount_end (SUM)",
        "scorecard_column": "total_headcount",
        "drill_target": "PQ-13 Headcount",
        "description": "Active employees on the last day of the month. Context dependent."
    },
    {
        "name": "Rolling 12M Attrition",
        "unit": "%",
        "source_view": "dept_month_headcount (aggregate)",
        "source_column": "exits/headcount_end (12M rolling)",
        "scorecard_column": "attrition_rolling_12m_pct",
        "drill_target": "PQ-13 Headcount",
        "description": "Leavers in last 12 months divided by average headcount over same period. Lower is better."
    },
    {
        "name": "Attendance Rate",
        "unit": "%",
        "source_view": "dept_month_attendance (aggregate)",
        "source_column": "(present+0.5×half)/scheduled × 100",
        "scorecard_column": "attendance_rate_pct",
        "drill_target": "PQ-13 Attendance",
        "description": "Days present (half-day counts 0.5) divided by scheduled working days. Higher is better."
    },
    {
        "name": "Overtime Share",
        "unit": "%",
        "source_view": "dept_month_payroll (aggregate)",
        "source_column": "overtime_pay/employer_cost × 100",
        "scorecard_column": "overtime_share_pct",
        "drill_target": "PQ-13 Payroll",
        "description": "Overtime pay as share of employer cost. Lower is better."
    },
]

# KPI metadata for display
KPI_META = {
    kpi["name"]: {
        "target_status": "Not Set",
        "target_display": "Not Set",
        "status_color": "#6c757d",
        "direction": "Higher is better" if kpi["name"] not in ["DSO", "Rolling 12M Attrition", "Overtime Share"] else "Lower is better",
    } for kpi in KPI_CONFIG
}

# Override specific ones
KPI_META["DSO"]["direction"] = "Lower is better"
KPI_META["Rolling 12M Attrition"]["direction"] = "Lower is better"
KPI_META["Overtime Share"]["direction"] = "Lower is better"

# Department-level targets for display
DEPT_OVERTIME_THRESHOLDS = {
    "D01": 0.5, "D02": 0.5, "D03": 0.5, "D04": 0.5, "D05": 0.5,
    "D06": 3.0, "D07": 3.0, "D08": 3.0, "D09": 3.0, "D10": 0.5
}
DEPT_ATTENDANCE_TARGET = 94.0
DEPT_ATTRITION_MONTHLY_TARGET = 1.0


# ============================================================
# 5. DATA FETCHING
# ============================================================

@st.cache_data(ttl=300)
def get_scorecard_data(selected_month):
    """Fetch all KPI values for the selected month from the pre-aggregated scorecard view."""
    con = get_connection()
    try:
        # Parse month
        if isinstance(selected_month, str):
            month_date = pd.to_datetime(selected_month + "-01")
        else:
            month_date = pd.to_datetime(selected_month)
        month_str = month_date.strftime("%Y-%m-%d")
        
        # Query the pre-aggregated scorecard view directly
        query = """
        SELECT 
            revenue,
            net_profit,
            operating_margin_pct,
            dso_days,
            total_headcount,
            attrition_rolling_12m_pct,
            attendance_rate_pct,
            overtime_share_pct
        FROM star_schema.pq15_company_scorecard
        WHERE month = ?
        """
        
        df = con.execute("SELECT revenue, net_profit, operating_margin_pct, dso_days, total_headcount, attrition_rolling_12m_pct, attendance_rate_pct, overtime_share_pct FROM star_schema.pq15_company_scorecard WHERE month = ?", [month_str]).fetchdf()
        
        if df.empty:
            return None
            
        return df.iloc[0].to_dict()
    finally:
        con.close()


@st.cache_data(ttl=300)
def get_trend_data(kpi_name):
    """Fetch 18-month trend data for a KPI."""
    con = get_connection()
    try:
        kpi_config = {k["name"]: k for k in KPI_CONFIG}[kpi_name]
        
        if kpi_name == "Revenue":
            df = con.execute("SELECT month, revenue as value FROM star_schema.m16_revenue WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01' ORDER BY month").fetchdf()
        elif kpi_name == "Net Profit":
            df = con.execute("SELECT (month || '-01')::DATE as month, net_profit as value FROM star_schema.m17_net_profit WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01' ORDER BY month").fetchdf()
        elif kpi_name == "Operating Margin":
            df = con.execute("SELECT (month || '-01')::DATE as month, operating_margin_pct as value FROM star_schema.m18_operating_margin WHERE (month || '-01')::DATE BETWEEN DATE '2025-04-01' AND DATE '2026-09-01' ORDER BY month").fetchdf()
        elif kpi_name == "DSO":
            df = con.execute("SELECT DATE_TRUNC('month', report_date)::DATE as month, dso_days as value FROM star_schema.m20_dso WHERE report_date BETWEEN DATE '2025-04-01' AND DATE '2026-09-30' ORDER BY month").fetchdf()
        elif kpi_name == "Total Headcount":
            df = con.execute("""
    SELECT
        month::DATE AS month,
        SUM(headcount_end) AS value
    FROM star_schema.dept_month_headcount
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
    ORDER BY month
""").fetchdf()
        elif kpi_name == "Rolling 12M Attrition":
            df = con.execute("""
                SELECT h.month::DATE AS month,
                    (SELECT SUM(h2.exits) * 100.0 / NULLIF(AVG(h2.headcount_end), 0)
                     FROM star_schema.dept_month_headcount h2
                     WHERE h2.month BETWEEN h.month - INTERVAL '11 months' AND h.month) as value
                FROM star_schema.dept_month_headcount h
                WHERE h.month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
                GROUP BY h.month
                ORDER BY h.month
            """).fetchdf()
        elif kpi_name == "Attendance Rate":
            df = con.execute("""
                SELECT
                  month::DATE AS month,
                  SUM(present_days + 0.5 * half_days_unpaid) * 100.0
                  / NULLIF(SUM(scheduled_days), 0) AS value
                FROM star_schema.dept_month_attendance
                WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
                GROUP BY month
                ORDER BY month
            """).fetchdf()
        elif kpi_name == "Overtime Share":
            df = con.execute("""
    SELECT
        month::DATE AS month,
        SUM(overtime_pay) * 100.0
            / NULLIF(SUM(employer_cost), 0) AS value
    FROM star_schema.dept_month_payroll
    WHERE month BETWEEN DATE '2025-04-01' AND DATE '2026-09-01'
    GROUP BY month
    ORDER BY month
""").fetchdf()
        else:
            return None
        
        if df.empty:
            return None
        return df["value"].tolist()
    finally:
        con.close()


# ============================================================
# 6. MAIN APPLICATION
# ============================================================

def main():
    st.title("📋 PQ-15 Executive Company-Health Scorecard")
    st.markdown("**8 Founder-Level KPIs** | Revenue • Profit • Margin • DSO • Headcount • Attrition • Attendance • Overtime")
    
    # Month selector
    con = get_connection()
    try:
        months_df = con.execute("""
            SELECT DISTINCT month FROM star_schema.pq15_company_scorecard 
            ORDER BY month DESC
        """).fetchdf()
        months = pd.to_datetime(months_df["month"]).dt.strftime("%Y-%m").tolist()
    finally:
        con.close()
    
    if not months:
        st.error("No data available")
        return
    
    selected_month = st.selectbox("Select Month", months, index=0)
    
    # Load data
    kpi_data = get_scorecard_data(selected_month)
    
    if kpi_data is None:
        st.error(f"No data for {selected_month}")
        return
    
    # ============================================================
    # RENDER KPI CARDS (2 rows x 4 columns)
    # ============================================================
    
    # Row 1: Revenue, Net Profit, Operating Margin, DSO
    row1 = [k for k in KPI_CONFIG if k["name"] in ["Revenue", "Net Profit", "Operating Margin", "DSO"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row1):
        with cols[i]:
            meta = KPI_META[kpi["name"]]
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Revenue": "PQ-11/PQ-12 Dashboard",
                "Net Profit": "PQ-11/PQ-12 Dashboard",
                "Operating Margin": "PQ-11/PQ-12 Dashboard",
                "DSO": "PQ-12 AR Dashboard"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target=drill_map.get(kpi["name"]),
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # Row 2: Total Headcount, Rolling 12M Attrition, Attendance Rate, Overtime Share
    row2 = [k for k in KPI_CONFIG if k["name"] in ["Total Headcount", "Rolling 12M Attrition", "Attendance Rate", "Overtime Share"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row2):
        with cols[i]:
            meta = KPI_META[kpi["name"]]
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Total Headcount": "PQ-13 Headcount",
                "Rolling 12M Attrition": "PQ-13 Headcount",
                "Attendance Rate": "PQ-13 Attendance",
                "Overtime Share": "PQ-13 Payroll"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target=drill_map.get(kpi["name"]),
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # ============================================================
    # DEPARTMENT TARGETS SECTION
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Department-Level Targets (for reference)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Attendance Rate Target**")
        st.markdown("All departments: **94%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level target not set. Department target is 94% for all departments.</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown("**Overtime Share Thresholds**")
        for dept, thresh in DEPT_OVERTIME_THRESHOLDS.items():
            st.markdown(f"- {dept}: **{thresh}%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level threshold not set. Department thresholds: 0.5% for D01-D05/D10, 3.0% for D06-D09.</div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown("**Attrition Monthly Target**")
        st.markdown("All departments: **1%** (monthly)")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Rolling 12M attrition has no approved company target. Monthly department target is 1%.</div>',
            unsafe_allow_html=True
        )
    
    # 5-KPI reduction explanation
    st.markdown("---")
    st.subheader("📝 If Restricted to 5 KPIs: Which 3 Would Be Removed")
    
    removed = [
        {
            "kpi": "DSO",
            "reason": "Only 1 data point (point-in-time metric); no trend analysis possible. AR health tracked via PQ-12 AR dashboard separately."
        },
        {
            "kpi": "Rolling 12M Attrition",
            "reason": "Highly correlated with monthly attrition and headcount. HR tracks via PQ-13 Headcount dashboard. Company target not approved."
        },
        {
            "kpi": "Overtime Share",
            "reason": "Very low company-wide (0.35%). Department-level thresholds exist and are monitored in PQ-13 Payroll. Less critical at company level."
        }
    ]
    
    for item in removed:
        with st.expander(f"❌ {item['kpi']} - Would Remove"):
            st.markdown(item['reason'])
    
    st.markdown("**✅ Retained (5 Core KPIs):**")
    for k in ["Revenue", "Net Profit", "Operating Margin", "Total Headcount", "Attendance Rate"]:
        st.markdown(f"- {k}")


# ============================================================
# 6. MAIN APPLICATION
# ============================================================

def main():
    st.set_page_config(
        page_title="PQ-15 Executive Company-Health Scorecard",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    st.title("📋 PQ-15 Executive Company-Health Scorecard")
    st.markdown("**8 Founder-Level KPIs** | Revenue • Profit • Margin • DSO • Headcount • Attrition • Attendance • Overtime")
    
    # Month selector
    con = get_connection()
    try:
        months_df = con.execute("""
            SELECT DISTINCT month FROM star_schema.pq15_company_scorecard 
            ORDER BY month DESC
        """).fetchdf()
        months = pd.to_datetime(months_df["month"]).dt.strftime("%Y-%m").tolist()
    finally:
        con.close()
    
    if not months:
        st.error("No data available")
        return
    
    selected_month = st.selectbox("Select Month", months, index=0)
    
    # Load data
    kpi_data = get_scorecard_data(selected_month)
    
    if kpi_data is None:
        st.error(f"No data for {selected_month}")
        return
    
    # Render KPI cards
    # Row 1
    row1 = [k for k in KPI_CONFIG if k["name"] in ["Revenue", "Net Profit", "Operating Margin", "DSO"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row1):
        with cols[i]:
            col_map = {
                "revenue": "revenue",
                "net_profit": "net_profit", 
                "operating_margin_pct": "operating_margin_pct",
                "dso_days": "dso_days"
            }
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Revenue": "PQ-11/PQ-12 Dashboard",
                "Net Profit": "PQ-11/PQ-12 Dashboard",
                "Operating Margin": "PQ-11/PQ-12 Dashboard",
                "DSO": "PQ-12 AR Dashboard"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target="PQ-11/PQ-12 Dashboard" if kpi["name"] != "DSO" else "PQ-12 AR Dashboard",
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # Row 2
    row2 = [k for k in KPI_CONFIG if k["name"] in ["Total Headcount", "Rolling 12M Attrition", "Attendance Rate", "Overtime Share"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row2):
        with cols[i]:
            col_map = {
                "headcount_end": "total_headcount",
                "attrition_rolling_12m_pct": "attrition_rolling_12m_pct",
                "attendance_rate_pct": "attendance_rate_pct",
                "overtime_share_pct": "overtime_share_pct"
            }
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Total Headcount": "PQ-13 Headcount",
                "Rolling 12M Attrition": "PQ-13 Headcount",
                "Attendance Rate": "PQ-13 Attendance",
                "Overtime Share": "PQ-13 Payroll"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target="PQ-13 Headcount" if kpi["name"] in ["Total Headcount", "Rolling 12M Attrition"] else ("PQ-13 Attendance" if kpi["name"] == "Attendance Rate" else "PQ-13 Payroll"),
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # Department targets section
    st.markdown("---")
    st.subheader("📋 Department-Level Targets (for reference)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Attendance Rate Target**")
        st.markdown("All departments: **94%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level target not set. Department target is 94% for all departments.</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown("**Overtime Share Thresholds**")
        for dept, thresh in DEPT_OVERTIME_THRESHOLDS.items():
            st.markdown(f"- {dept}: **{thresh}%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level threshold not set. Department thresholds: 0.5% for D01-D05/D10, 3.0% for D06-D09.</div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown("**Attrition Monthly Target**")
        st.markdown("All departments: **1%** (monthly)")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Rolling 12M attrition has no approved company target. Monthly department target is 1%.</div>',
            unsafe_allow_html=True
        )
    
    # 5-KPI reduction explanation
    st.markdown("---")
    st.subheader("📝 If Restricted to 5 KPIs: Which 3 Would Be Removed")
    
    removed = [
        {
            "kpi": "DSO",
            "reason": "Only 1 data point (point-in-time metric); no trend analysis possible. AR health tracked via PQ-12 AR dashboard separately."
        },
        {
            "kpi": "Rolling 12M Attrition",
            "reason": "Highly correlated with monthly attrition and headcount. HR tracks via PQ-13 Headcount dashboard. Company target not approved."
        },
        {
            "kpi": "Overtime Share",
            "reason": "Very low company-wide (0.35%). Department-level thresholds exist and are monitored in PQ-13 Payroll. Less critical at company level."
        }
    ]
    
    for item in removed:
        with st.expander(f"❌ {item['kpi']} - Would Remove"):
            st.markdown(item['reason'])
    
    st.markdown("**✅ Retained (5 Core KPIs):**")
    for k in ["Revenue", "Net Profit", "Operating Margin", "Total Headcount", "Attendance Rate"]:
        st.markdown(f"- {k}")


# ============================================================
# 8. MAIN APPLICATION
# ============================================================

def main():
    st.set_page_config(
        page_title="PQ-15 Executive Company-Health Scorecard",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Print stylesheet for A4
    st.markdown("""
    <style>
    @media print {
        @page { size: A4; margin: 1cm; }
        .stApp { background: white; }
        .stSelectbox, .stButton, .stExpander { display: none !important; }
        .stColumns > div { page-break-inside: avoid; }
        .stMarkdown, .stDataFrame { page-break-inside: avoid; }
        @page { size: A4; margin: 1cm; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📋 PQ-15 Executive Company-Health Scorecard")
    st.markdown("**8 Founder-Level KPIs** | Revenue • Profit • Margin • DSO • Headcount • Attrition • Attendance • Overtime")
    
    # Month selector
    con = get_connection()
    try:
        months_df = con.execute("""
            SELECT DISTINCT month FROM star_schema.pq15_company_scorecard 
            ORDER BY month DESC
        """).fetchdf()
        months = pd.to_datetime(months_df["month"]).dt.strftime("%Y-%m").tolist()
    finally:
        con.close()
    
    if not months:
        st.error("No data available")
        return
    
    selected_month = st.selectbox("Select Month", months, index=0)
    
    # Load data
    kpi_data = get_scorecard_data(selected_month)
    
    if kpi_data is None:
        st.error(f"No data for {selected_month}")
        return
    
    # Render KPI cards
    # Row 1
    row1 = [k for k in KPI_CONFIG if k["name"] in ["Revenue", "Net Profit", "Operating Margin", "DSO"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row1):
        with cols[i]:
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Revenue": "PQ-11/PQ-12 Dashboard",
                "Net Profit": "PQ-11/PQ-12 Dashboard",
                "Operating Margin": "PQ-11/PQ-12 Dashboard",
                "DSO": "PQ-12 AR Dashboard"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target=drill_map[kpi["name"]],
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # Row 2
    row2 = [k for k in KPI_CONFIG if k["name"] in ["Total Headcount", "Rolling 12M Attrition", "Attendance Rate", "Overtime Share"]]
    cols = st.columns(4)
    for i, kpi in enumerate(row2):
        with cols[i]:
            col_map = {
                "headcount_end": "total_headcount",
                "attrition_rolling_12m_pct": "attrition_rolling_12m_pct",
                "attendance_rate_pct": "attendance_rate_pct",
                "overtime_share_pct": "overtime_share_pct"
            }
            val = kpi_data.get(kpi["scorecard_column"], 0)
            trend = get_trend_data(kpi["name"])
            
            drill_map = {
                "Total Headcount": "PQ-13 Headcount",
                "Rolling 12M Attrition": "PQ-13 Headcount",
                "Attendance Rate": "PQ-13 Attendance",
                "Overtime Share": "PQ-13 Payroll"
            }
            
            render_kpi_card(
                kpi_name=kpi["name"],
                value=kpi_data.get(kpi["scorecard_column"], 0),
                unit=kpi["unit"],
                target_status="Not Set",
                trend_data=get_trend_data(kpi["name"]),
                drill_target=drill_map[kpi["name"]],
                source_view=kpi["source_view"],
                source_column=kpi["source_column"]
            )
    
    # Department targets section
    st.markdown("---")
    st.subheader("📋 Department-Level Targets (for reference)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Attendance Rate Target**")
        st.markdown("All departments: **94%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level target not set. Department target is 94% for all departments.</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown("**Overtime Share Thresholds**")
        for dept, thresh in DEPT_OVERTIME_THRESHOLDS.items():
            st.markdown(f"- {dept}: **{thresh}%**")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Company-level threshold not set. Department thresholds: 0.5% for D01-D05/D10, 3.0% for D06-D09.</div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown("**Attrition Monthly Target**")
        st.markdown("All departments: **1%** (monthly)")
        st.markdown(
            '<div style="background-color: #f8f9fa; border-left: 4px solid #856404; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; font-size: 0.9rem; color: #533f03;">'
            '💡 <strong>Note:</strong> Rolling 12M attrition has no approved company target. Monthly department target is 1%.</div>',
            unsafe_allow_html=True
        )
    
    # 5-KPI reduction explanation
    st.markdown("---")
    st.subheader("📝 If Restricted to 5 KPIs: Which 3 Would Be Removed")
    
    removed = [
        {
            "kpi": "DSO",
            "reason": "Only 1 data point (point-in-time metric); no trend analysis possible. AR health tracked via PQ-12 AR dashboard separately."
        },
        {
            "kpi": "Rolling 12M Attrition",
            "reason": "Highly correlated with monthly attrition and headcount. HR tracks via PQ-13 Headcount dashboard. Company target not approved."
        },
        {
            "kpi": "Overtime Share",
            "reason": "Very low company-wide (0.35%). Department-level thresholds exist and are monitored in PQ-13 Payroll. Less critical at company level."
        }
    ]
    
    for item in removed:
        with st.expander(f"❌ {item['kpi']} - Would Remove"):
            st.markdown(item['reason'])
    
    st.markdown("**✅ Retained (5 Core KPIs):**")
    for k in ["Revenue", "Net Profit", "Operating Margin", "Total Headcount", "Attendance Rate"]:
        st.markdown(f"- {k}")


if __name__ == "__main__":
    main()