"""
pages/6_Analytics.py

WHAT THIS FILE DOES:
The "ultra level" KPI dashboard — animated gradient KPI cards (calls,
avg duration, leads, conversion rate, minutes used) plus two real
Plotly charts: a calls-per-day trend line and a call-outcomes breakdown.
All numbers come from the real /analytics/summary backend endpoint,
which aggregates actual CallLog and Lead rows — nothing here is fake
placeholder data.
"""

import streamlit as st
import plotly.graph_objects as go
from utils import api_client as api
from utils.session import require_login, require_company
from utils.theme import inject_theme, section_header
from utils.enterprise_widgets import render_animated_kpi_row, render_radial_gauge

st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")
inject_theme()
require_login()
require_company()

company_id = st.session_state["active_company_id"]

st.markdown(section_header("📈 Analytics"), unsafe_allow_html=True)
st.caption("Real-time performance across every call your AI agents handle.")

days = st.select_slider("Time range", options=[7, 14, 30, 90], value=30, format_func=lambda d: f"Last {d} days")

try:
    data = api.get_analytics_summary(company_id, days=days)
except api.ApiError as e:
    st.error(str(e))
    st.stop()

# ---- Animated KPI row with sparklines ----
calls_by_day = data.get("calls_by_day", [])
sparkline_values = [d["calls"] for d in calls_by_day] if calls_by_day else []
minutes_pct = round((data["minutes_used"] / data["minutes_limit"]) * 100, 0) if data["minutes_limit"] else 0

render_animated_kpi_row([
    {"label": "Total Calls", "value": data["total_calls"], "sub": f"Last {days} days", "color": "#1D4ED8", "sparkline": sparkline_values},
    {"label": "Avg Duration", "value": round(data["avg_duration_seconds"] / 60, 1), "suffix": " min", "sub": f"{data['avg_duration_seconds']}s avg", "color": "#0EA5E9"},
    {"label": "Leads Captured", "value": data["total_leads"], "sub": "Bookings + orders + inquiries", "color": "#60A5FA"},
    {"label": "Conversion Rate", "value": data["conversion_rate_percent"], "suffix": "%", "sub": f"{data['booked_leads']} booked", "color": "#16A34A"},
])

st.markdown("<br>", unsafe_allow_html=True)

# ---- Radial gauge + charts ----
col_gauge, col_left, col_right = st.columns([1, 2, 1.3])

with col_gauge:
    st.markdown(section_header("Plan Usage"), unsafe_allow_html=True)
    render_radial_gauge("Minutes Used", min(minutes_pct, 100), color="#1D4ED8" if minutes_pct < 80 else "#f87171")

with col_left:
    st.markdown(section_header("Calls Over Time"), unsafe_allow_html=True)
    calls_by_day = data.get("calls_by_day", [])
    if calls_by_day:
        dates = [d["date"] for d in calls_by_day]
        counts = [d["calls"] for d in calls_by_day]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=counts, mode="lines+markers", fill="tozeroy",
            line=dict(color="#1D4ED8", width=3),
            marker=dict(size=7, color="#60A5FA"),
            fillcolor="rgba(29, 78, 216, 0.15)",
        ))
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#3B4B66"), margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(11,37,69,0.08)"),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No calls yet in this time range. Once your agent starts handling calls, the trend will appear here.")

with col_right:
    st.markdown(section_header("Call Outcomes"), unsafe_allow_html=True)
    outcomes = data.get("outcomes", [])
    if outcomes:
        labels = [o["outcome"] for o in outcomes]
        values = [o["count"] for o in outcomes]
        fig2 = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.55,
            marker=dict(colors=["#1D4ED8", "#60A5FA", "#0EA5E9", "#facc15", "#16A34A"]),
        )])
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#3B4B66"),
            margin=dict(l=10, r=10, t=10, b=10), height=320, showlegend=True,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No outcome data yet.")
