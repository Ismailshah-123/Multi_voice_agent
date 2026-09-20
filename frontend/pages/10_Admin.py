"""
pages/10_Admin.py

WHAT THIS FILE DOES:
Platform-owner-only view across ALL companies on the platform — total
signups, total calls, plan breakdown, per-company activity. Shows a
clear "access denied" message for any user who isn't marked
is_superadmin (checked server-side too — this page hiding is just UX,
the real enforcement is the 403 from the backend).
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login
from utils.theme import inject_theme, section_header, kpi_card

st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
inject_theme()
require_login()

user = st.session_state.get("user", {})
if not user.get("is_superadmin"):
    st.warning("This page is only available to the platform administrator.")
    st.stop()

st.markdown(section_header("🛠️ Platform Admin"), unsafe_allow_html=True)
st.caption("A bird's-eye view across every business using the platform.")

try:
    overview = api.admin_overview()
except api.ApiError as e:
    st.error(str(e))
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(kpi_card("Total Companies", str(overview["total_companies"])), unsafe_allow_html=True)
with col2:
    st.markdown(kpi_card("Total Agents Deployed", str(overview["total_agents"])), unsafe_allow_html=True)
with col3:
    st.markdown(kpi_card("Total Calls Handled", str(overview["total_calls"])), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Plan Breakdown")
for p in overview["plan_breakdown"]:
    st.write(f"**{p['plan']}**: {p['count']} companies")

st.divider()
st.subheader("All Companies")
try:
    companies = api.admin_list_companies()
    for c in companies:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.markdown(f"**{c['name']}** ({c['industry']})")
            col1.caption(c["owner_email"])
            col2.write(f"Plan: {c['plan_tier']} | Agents: {c['agent_count']} | Calls: {c['call_count']}")
            col2.caption(f"Minutes used: {c['monthly_minutes_used']}")
            col3.caption(str(c["created_at"])[:10])
except api.ApiError as e:
    st.error(str(e))
