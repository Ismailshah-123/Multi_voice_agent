"""
pages/9_Team.py

WHAT THIS FILE DOES:
Lets a company owner invite other platform users (by email) to help
manage the company — view the dashboard, agents, leads, call logs. The
invited person must already have a platform account (sign up first).
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login, require_company
from utils.theme import inject_theme, section_header

st.set_page_config(page_title="Team", page_icon="👥", layout="wide")
inject_theme()
require_login()
require_company()

company_id = st.session_state["active_company_id"]

st.markdown(section_header("👥 Team"), unsafe_allow_html=True)
st.caption("Invite teammates to help manage this company. They need a platform account already — they can sign up first, then you invite them by email.")

with st.form("invite_form"):
    email = st.text_input("Teammate's email")
    role = st.selectbox("Role", options=["staff", "admin"], format_func=lambda r: {"staff": "Staff (view only)", "admin": "Admin (full access)"}[r])
    submitted = st.form_submit_button("Send Invite", type="primary")
    if submitted:
        if not email:
            st.error("Enter an email address.")
        else:
            try:
                result = api.invite_member(company_id, email, role)
                st.success(f"{result['email']} added as {result['role']}.")
                st.rerun()
            except api.ApiError as e:
                st.error(str(e))

st.divider()
st.subheader("Current Team")
try:
    members = api.list_members(company_id)
    for m in members:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{m.get('full_name') or m['email']}** — {m['email']}")
        col2.write(m["role"].capitalize() if isinstance(m["role"], str) else m["role"])
except api.ApiError as e:
    st.error(str(e))
