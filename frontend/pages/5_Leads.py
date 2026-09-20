
"""
pages/5_Leads.py

WHAT THIS FILE DOES:
Shows the built-in CRM — every Lead captured automatically during calls
(bookings, orders, qualified sales leads) via the post-call automation
workflow. No manual data entry; this fills up automatically as agents
handle calls.
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login, require_company
from utils.theme import inject_theme

st.set_page_config(layout="wide")
inject_theme()

require_login()
require_company()

company_id = st.session_state["active_company_id"]

st.title("👥 Leads / CRM")
st.caption(
    "Automatically captured from every call — bookings, orders, and qualified leads."
)

if st.button("📥 Export Leads to CSV"):
    try:
        csv_bytes = api.export_leads_csv(company_id)
        st.download_button(
            "Download CSV",
            csv_bytes,
            file_name="leads_export.csv",
            mime="text/csv"
        )
    except api.ApiError as e:
        st.error(str(e))

try:
    leads = api.list_leads(company_id) if hasattr(api, "list_leads") else []
except Exception:
    leads = []

if not leads:
    st.info(
        "No leads yet. They'll appear here automatically once your agent starts handling calls."
    )
else:
    status_colors = {
        "new": "🔵",
        "contacted": "🟡",
        "qualified": "🟢",
        "booked": "✅",
        "lost": "⚪"
    }

    for lead in leads:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 2, 2])

            c1.markdown(
                f"**{status_colors.get(lead['status'], '⚪')} "
                f"{lead.get('name') or 'Unknown'}**"
            )
            c1.caption(f"Source: {lead.get('source', 'voice_call')}")

            c2.write(lead.get("phone") or "No phone")
            c2.caption(lead.get("email") or "No email")

            c3.write(f"Status: {lead['status']}")
            c3.caption(str(lead.get("created_at", "")))

            if lead.get("notes"):
                st.caption(f"📝 {lead['notes']}")

