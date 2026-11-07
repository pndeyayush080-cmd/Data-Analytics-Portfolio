"""
PQ-14 AI Signals Dashboard

Streamlit dashboard showing:
- Anomalies by type and money at risk
- Forecast vs actual with confidence bands
- Attrition risk summary
- Forecast error analysis

Data sources:
- star_schema.pq14_anomalies_by_risk
- star_schema.pq14_future_forecasts
- star_schema.pq14_forecast_backtest_headcount
- star_schema.pq14_forecast_backtest_attrition
- star_schema.pq14_forecast_error
- star_schema.pq14_attrition_risk_summary
- star_schema.pq14_attrition_risk_detail

All AI outputs clearly labelled: "AI-generated, for human review"
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
    page_title="PQ-14 AI Signals Dashboard",
    page_icon="🤖",
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
    if not df.empty and "forecast_month" in df.columns:
        df["forecast_month"] = pd.to_datetime(df["forecast_month"])
    if not df.empty and "period" in df.columns:
        df["period"] = pd.to_datetime(df["period"])
    if not df.empty and "as_of_date" in df.columns:
        df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


def fetch_data(con, query, params=None):
    """Execute query with optional parameters and format date columns."""
    if params is None:
        return format_month_column(con.execute(query).fetchdf())
    return format_month_column(con.execute(query, params).fetchdf())


def render_ai_badge():
    st.markdown(
        '<span style="background-color: #fff3cd; color: #856404; padding: 0.25rem 0.5rem; '
        'border-radius: 0.25rem; font-size: 0.85rem; font-weight: bold;">'
        '🤖 AI-generated, for human review</span>',
        unsafe_allow_html=True
    )


def render_chart_note(note):
    """Render a plain-language explanatory note below a chart."""
    st.markdown(
        f'<div style="background-color: #f8f9fa; border-left: 4px solid #856404; '
        'padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 0.25rem; '
        'font-size: 0.9rem; color: #533f03;">'
        f'💡 <strong>Note:</strong> {note}</div>',
        unsafe_allow_html=True
    )


# ============================================================
# 4. ANOMALIES ANALYSIS
# ============================================================

def render_anomalies(con):
    st.header("🚨 Anomalies by Type & Money at Risk")
    render_ai_badge()
    render_chart_note(
        "Anomalies are detected by Isolation Forest models on attendance and payroll features. "
        "All shown anomalies are flagged (flagged=Y). Money at risk is quantified for payroll anomalies; "
        "attendance anomalies (NO_ATTENDANCE, LONG_UNPAID_ABSENCE, FREQUENT_LATE) have no monetary exposure."
    )
    
    # Summary table
    summary = fetch_data(con, """
        SELECT 
            reason_code AS "Reason Code",
            anomaly_count AS "Count",
            total_money_at_risk AS "Total Money at Risk (₹)",
            avg_money_at_risk AS "Avg Money at Risk (₹)",
            max_money_at_risk AS "Max Money at Risk (₹)",
            no_monetary_exposure_count AS "No Monetary Exposure"
        FROM star_schema.pq14_anomalies_by_risk
        ORDER BY "Total Money at Risk (₹)" DESC NULLS LAST
    """)
    
    if show_empty_message(summary, "No anomaly data available."):
        return
    
    # KPI cards
    total_anomalies = summary["Count"].sum()
    total_money = summary["Total Money at Risk (₹)"].sum()
    no_money = summary["No Monetary Exposure"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Anomalies", f"{total_anomalies:,}")
    col2.metric("Total Money at Risk", f"₹{total_money:,.0f}")
    col3.metric("No Monetary Exposure", f"{no_money:,}")
    
    st.dataframe(summary, use_container_width=True)
    
    # Bar chart - Money at Risk
    fig = px.bar(
        summary,
        x="Reason Code",
        y="Total Money at Risk (₹)",
        color="Reason Code",
        title="Money at Risk by Anomaly Type",
        text_auto=True
    )
    fig.update_layout(showlegend=False, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    render_chart_note(
        "Bars show total money at risk per anomaly type. "
        "Payroll anomalies (STATISTICAL_OUTLIER, PATTERN_SHIFT, GROSS_ABOVE_NORM, etc.) have quantified money at risk. "
        "Attendance anomalies show zero because they have no direct monetary exposure."
    )
    
    # Count chart
    fig2 = px.bar(
        summary,
        x="Reason Code",
        y="Count",
        color="Reason Code",
        title="Anomaly Count by Type",
        text_auto=True
    )
    fig2.update_layout(showlegend=False, xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)
    render_chart_note(
        "Bars show the number of anomaly events per type. STATISTICAL_OUTLIER and PATTERN_SHIFT are the most frequent types."
    )
    
    # Detail table
    st.subheader("Anomaly Detail (Top 50 by Money at Risk)")
    render_ai_badge()
    detail = fetch_data(con, """
        SELECT 
            result_id AS "Result ID",
            source_dataset AS "Source",
            record_id AS "Record ID",
            employee_id AS "Employee",
            period AS "Period",
            reason_code AS "Reason Code",
            reason_text AS "Description",
            money_at_risk AS "Money at Risk (₹)",
            anomaly_score AS "Score",
            model_version AS "Model"
        FROM star_schema.pq14_anomaly_detail
        ORDER BY money_at_risk DESC NULLS LAST, anomaly_score DESC
        LIMIT 50
    """)
    st.dataframe(detail, use_container_width=True)


# ============================================================
# 5. FORECAST VS ACTUAL
# ============================================================

def render_forecasts(con):
    st.header("📈 Forecasts vs Actuals with Confidence Bands")
    render_ai_badge()
    render_chart_note(
        "Forecasts are generated using statistical methods trained on data through September 2026. "
        "Headcount uses linear trend (36 months) + half-strength seasonality. "
        "Attrition rate uses same-month average of last 3 years. "
        "Confidence bands show 80% prediction intervals. Forecasts are NOT guaranteed outcomes."
    )
    
    # Metric selector
    metrics = fetch_data(con, "SELECT DISTINCT metric FROM star_schema.pq14_future_forecasts")["metric"].tolist()
    selected_metric = st.selectbox("Select Metric", metrics)
    
    # Department selector
    depts = fetch_data(con, "SELECT DISTINCT department_id FROM star_schema.pq14_future_forecasts WHERE metric = ?", [selected_metric])["department_id"].tolist()
    selected_depts = st.multiselect("Departments", depts, default=depts[:3])
    
    if not selected_depts:
        st.warning("Select at least one department.")
        return
    
    # Fetch forecasts
    placeholders = ",".join(["?"] * len(selected_depts))
    forecast_query = f"""
        SELECT 
            department_id,
            forecast_month,
            forecast_value,
            lower_80,
            upper_80,
            method,
            trained_through,
            forecast_note
        FROM star_schema.pq14_future_forecasts
        WHERE metric = ? AND department_id IN ({",".join(["?"] * len(selected_depts))})
        ORDER BY department_id, forecast_month
    """
    params = [selected_metric] + selected_depts
    forecasts = fetch_data(con, forecast_query, params)
    
    if show_empty_message(forecasts, "No forecast data available."):
        return
    
    # Fetch actuals for comparison (historical)
    actuals = fetch_data(con, """
        SELECT 
            department_id,
            month_start_date AS month,
            headcount_end AS actual_value
        FROM raw.fact_headcount_monthly
        WHERE department_id IN ({})
        ORDER BY department_id, month_start_date
    """.format(",".join(["?"] * len(selected_depts))), selected_depts)
    
    if selected_metric == "attrition_rate_monthly_pct":
        actuals = fetch_data(con, """
            SELECT 
                department_id,
                month_start_date AS month,
                attrition_rate_monthly_pct AS actual_value
            FROM raw.fact_headcount_monthly
            WHERE department_id IN ({}) AND headcount_start > 0
            ORDER BY department_id, month_start_date
        """.format(",".join(["?"] * len(selected_depts))), selected_depts)
    
    # Plot
    fig = go.Figure()
    
    # Add actuals
    for dept in selected_depts:
        dept_actuals = actuals[actuals["department_id"] == dept]
        if not dept_actuals.empty:
            fig.add_trace(go.Scatter(
                x=dept_actuals["month"],
                y=dept_actuals["actual_value"],
                mode="lines+markers",
                name=f"{dept} Actual",
                line=dict(width=2)
            ))
    
    # Add forecasts with confidence bands
    for dept in selected_depts:
        dept_fc = forecasts[forecasts["department_id"] == dept]
        if dept_fc.empty:
            continue
        
        fig.add_trace(go.Scatter(
            x=dept_fc["forecast_month"],
            y=dept_fc["upper_80"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=dept_fc["forecast_month"],
            y=dept_fc["lower_80"],
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(0,100,80,0.2)",
            line=dict(width=0),
            name=f"{dept} 80% CI",
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=dept_fc["forecast_month"],
            y=dept_fc["forecast_value"],
            mode="lines+markers",
            name=f"{dept} Forecast",
            line=dict(dash="dash", width=2),
            marker=dict(symbol="diamond")
        ))
    
    fig.update_layout(
        title=f"{selected_metric.replace('_', ' ').title()} - Forecast vs Actual",
        xaxis_title="Month",
        yaxis_title=selected_metric.replace('_', ' ').title(),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Solid lines = actual historical values. Dashed lines with diamond markers = AI forecasts. "
        "Shaded regions = 80% confidence intervals (prediction intervals). "
        "Forecasts are statistical projections, NOT guaranteed outcomes. "
        "Headcount uses linear trend + seasonality; Attrition uses 3-year same-month average."
    )
    
    # Show forecast table
    st.subheader("Forecast Details")
    render_ai_badge()
    st.dataframe(forecasts[["department_id", "forecast_month", "forecast_value", "lower_80", "upper_80", "method", "trained_through"]], use_container_width=True)


# ============================================================
# 6. FORECAST ERROR ANALYSIS
# ============================================================

def render_forecast_error(con):
    st.header("📊 Forecast Error Analysis (Backtest)")
    render_ai_badge()
    render_chart_note(
        "Backtest methodology: Forecasting methods are applied to historical data to simulate "
        "predictions that would have been made at each point in time. Errors are computed against "
        "actual observed values. "
        "- MAPE: Mean Absolute Percentage Error. "
        "- MAE: Mean Absolute Error. "
        "- RMSE: Root Mean Square Error. "
        "Lower values indicate better forecast accuracy."
    )
    
    error_table = fetch_data(con, "SELECT * FROM star_schema.pq14_forecast_error ORDER BY metric, department_id")
    
    if show_empty_message(error_table, "No forecast error data available. Backtest may have insufficient historical data."):
        return
    
    st.dataframe(error_table, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Table shows forecast accuracy metrics by metric and department. "
        "MAPE = Mean Absolute Percentage Error (%). "
        "MAE = Mean Absolute Error (same units as metric). "
        "RMSE = Root Mean Square Error. "
        "Lower values = better accuracy. "
        "Backtest uses linear trend (headcount) and 3-year average (attrition) on historical data."
    )
    
    # MAPE chart
    fig = px.bar(
        error_table,
        x="department_id",
        y="mape_pct",
        color="metric",
        title="MAPE by Department and Metric",
        text_auto=".2f",
        barmode="group"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Bars show MAPE (%) by department. "
        "Lower bars = more accurate forecasts. "
        "Headcount forecasts typically have lower MAPE than attrition rate forecasts."
    )
    
    # MAE chart
    fig2 = px.bar(
        error_table,
        x="department_id",
        y="mae",
        color="metric",
        title="MAE by Department and Metric",
        text_auto=".2f",
        barmode="group"
    )
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Bars show MAE in original units (headcount or percentage points). "
        "MAE penalizes large errors more than MAPE for high-volume departments."
    )
    
    # Detail backtest charts
    st.subheader("Backtest Detail: Headcount")
    bt_headcount = fetch_data(con, "SELECT * FROM star_schema.pq14_forecast_backtest_headcount ORDER BY department_id, month")
    if not bt_headcount.empty:
        depts = bt_headcount["department_id"].unique().tolist()
        selected = st.selectbox("Department", depts, key="bt_headcount_dept")
        dept_data = bt_headcount[bt_headcount["department_id"] == selected]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dept_data["month"], y=dept_data["actual_value"], mode="lines+markers", name="Actual"))
        fig.add_trace(go.Scatter(x=dept_data["month"], y=dept_data["predicted_value"], mode="lines+markers", name="Predicted", line=dict(dash="dash")))
        fig.update_layout(title=f"Headcount Backtest: {selected}", xaxis_title="Month", yaxis_title="Headcount")
        st.plotly_chart(fig, use_container_width=True)
        render_ai_badge()
        render_chart_note(
            "Solid line = actual headcount. Dashed line = linear trend forecast from 36-month rolling window. "
            "Each prediction uses only data available up to that month (no look-ahead bias)."
        )
    
    st.subheader("Backtest Detail: Attrition Rate")
    bt_attrition = fetch_data(con, "SELECT * FROM star_schema.pq14_forecast_backtest_attrition ORDER BY department_id, month")
    if not bt_attrition.empty:
        depts = bt_attrition["department_id"].unique().tolist()
        selected = st.selectbox("Department", depts, key="bt_attrition_dept")
        dept_data = bt_attrition[bt_attrition["department_id"] == selected]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dept_data["month"], y=dept_data["actual_value"], mode="lines+markers", name="Actual"))
        fig.add_trace(go.Scatter(x=dept_data["month"], y=dept_data["predicted_value"], mode="lines+markers", name="Predicted", line=dict(dash="dash")))
        fig.update_layout(title=f"Attrition Rate Backtest: {selected}", xaxis_title="Month", yaxis_title="Attrition Rate (%)")
        st.plotly_chart(fig, use_container_width=True)
        render_ai_badge()
        render_chart_note(
            "Solid line = actual monthly attrition rate. Dashed line = 3-year same-month average forecast. "
            "Each prediction uses only prior years' same-month data (no look-ahead). "
            "Months with fewer than 3 prior years use only available years."
        )


# ============================================================
# 7. ATTRITION RISK
# ============================================================

def render_attrition_risk(con):
    st.header("⚠️ Attrition Risk Summary")
    render_ai_badge()
    render_chart_note(
        "This model predicts 12-month attrition risk using logistic regression (attrition-logreg-baseline-0.1) "
        "trained on data through September 2026. "
        "Risk Bands: High = top 10% risk scores, Medium = next 20%, Low = remaining 70%. "
        "IMPORTANT: This is a support signal for HR, never a decision. Do not use for individual employment actions."
    )
    
    summary = fetch_data(con, """
        SELECT 
            department_id AS "Department",
            department_name AS "Department Name",
            risk_band AS "Risk Band",
            employee_count AS "Employees",
            avg_risk_score AS "Avg Risk Score",
            top_reasons_1 AS "Top Reason 1",
            top_reasons_2 AS "Top Reason 2",
            as_of_date AS "As Of Date",
            ai_label AS "AI Label",
            model_version AS "Model",
            model_note AS "Model Note"
        FROM star_schema.pq14_attrition_risk_summary
        ORDER BY department_id, 
            CASE risk_band WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 END
    """)
    
    if show_empty_message(summary, "No attrition risk data available."):
        return
    
    # KPI cards
    latest_date = summary["As Of Date"].iloc[0] if not summary.empty else "N/A"
    total_employees = summary["Employees"].sum()
    high_risk = summary[summary["Risk Band"] == "High"]["Employees"].sum()
    medium_risk = summary[summary["Risk Band"] == "Medium"]["Employees"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("As Of", str(latest_date))
    col2.metric("Total Scored", f"{total_employees:,}")
    col3.metric("High Risk", f"{high_risk:,}", delta=f"{high_risk/total_employees*100:.1f}%")
    col4.metric("Medium Risk", f"{medium_risk:,}", delta=f"{medium_risk/total_employees*100:.1f}%")
    
    # Risk band distribution
    risk_dist = summary.groupby("Risk Band")["Employees"].sum().reset_index()
    fig = px.pie(risk_dist, values="Employees", names="Risk Band", title="Risk Band Distribution",
                 color="Risk Band", color_discrete_map={"High": "#dc3545", "Medium": "#ffc107", "Low": "#28a745"})
    st.plotly_chart(fig, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Pie chart shows proportion of employees in each risk band. "
        "High = top 10% of risk scores, Medium = next 20%, Low = remaining 70%. "
        "Based on logistic regression model (attrition-logreg-baseline-0.1)."
    )
    
    # Department risk heatmap
    st.subheader("Department Risk Heatmap")
    pivot = summary.pivot_table(values="Employees", index="Department", columns="Risk Band", fill_value=0)
    fig = px.imshow(pivot.values, x=pivot.columns, y=pivot.index, 
                    color_continuous_scale="Reds", aspect="auto",
                    labels=dict(x="Risk Band", y="Department", color="Employees"))
    fig.update_layout(title="Employees by Department and Risk Band")
    st.plotly_chart(fig, use_container_width=True)
    render_ai_badge()
    render_chart_note(
        "Heatmap shows employee counts per department and risk band. "
        "Darker red = more employees in that risk band. "
        "Use to identify departments with concentrated high-risk employees."
    )
    
    # Detail table
    st.subheader("Department Risk Detail")
    render_ai_badge()
    st.dataframe(summary, use_container_width=True)
    render_chart_note(
        "Table shows employee counts and average risk scores by department and risk band. "
        "Top Reason 1/2 show the most common risk drivers per department-band combination."
    )
    
    # Drill-down
    st.subheader("Employee-Level Detail (Top 50 Highest Risk)")
    render_ai_badge()
    detail = fetch_data(con, """
        SELECT 
            prediction_id AS "Prediction ID",
            employee_id AS "Employee",
            department_name AS "Department",
            as_of_date AS "As Of Date",
            risk_score_12m AS "Risk Score",
            risk_band AS "Risk Band",
            top_reason_1 AS "Top Reason 1",
            top_reason_2 AS "Top Reason 2",
            top_reason_3 AS "Top Reason 3",
            ai_label AS "AI Label",
            model_version AS "Model",
            model_note AS "Model Note"
        FROM star_schema.pq14_attrition_risk_detail
        ORDER BY risk_score_12m DESC
        LIMIT 50
    """)
    st.dataframe(detail, use_container_width=True)
    render_chart_note(
        "Table shows top 50 highest-risk employees. "
        "Risk Score = predicted probability of leaving within 12 months. "
        "Top Reasons = model's top explanatory features. "
        "AI Label and Model Note remind users this is a support signal, not a decision."
    )


# ============================================================
# 8. MAIN APPLICATION
# ============================================================

def main():
    st.title("🤖 PQ-14 AI Signals Dashboard")
    st.markdown("**AI-Generated Workforce Intelligence** | Anomalies • Forecasts • Attrition Risk")
    
    # Sidebar
    st.sidebar.header("🔍 Dashboard Sections")
    
    try:
        con = get_connection()
        
        section = st.sidebar.radio(
            "Navigate",
            ["🚨 Anomalies", "📈 Forecasts", "📊 Forecast Error", "⚠️ Attrition Risk"],
            index=0
        )
        
        if section == "🚨 Anomalies":
            render_anomalies(con)
        elif section == "📈 Forecasts":
            render_forecasts(con)
        elif section == "📊 Forecast Error":
            render_forecast_error(con)
        elif section == "⚠️ Attrition Risk":
            render_attrition_risk(con)
        
    except Exception as exc:
        st.error(f"Dashboard error: {exc}")
    finally:
        try:
            con.close()
        except:
            pass


if __name__ == "__main__":
    main()