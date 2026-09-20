"""
pages/4_Billing.py

WHAT THIS FILE DOES:
Shows the 3 pricing tiers ($30/$60/$90) pulled live from the backend's
/billing/plans endpoint, and lets the user click Upgrade to launch a
real Stripe Checkout session, or open the Stripe Billing Portal to
manage an existing subscription.
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

st.title("💳 Billing")

try:
    plans = api.list_plans()
except api.ApiError as e:
    st.error(str(e))
    st.stop()

st.subheader("Choose your plan")
cols = st.columns(len(plans))

for col, (plan_key, plan_info) in zip(cols, plans.items()):
    with col:
        with st.container(border=True):
            st.markdown(f"### {plan_key.capitalize()}")
            st.markdown(f"## {plan_info['display_price']}")
            st.write(f"Up to **{plan_info.get('max_agents', '—')}** agents")
            st.write(f"**{plan_info.get('monthly_minutes_limit', '—')}** minutes/month")

            if plan_key != "free":
                if st.button(f"Upgrade to {plan_key.capitalize()}", type="primary", key=f"upgrade_{plan_key}", use_container_width=True):
                    try:
                        result = api.create_checkout(
                            company_id=company_id,
                            plan=plan_key,
                            success_url="http://localhost:8501/Billing?status=success",
                            cancel_url="http://localhost:8501/Billing?status=cancelled",
                        )
                        st.markdown(f"[Complete checkout →]({result['checkout_url']})")
                    except api.ApiError as e:
                        st.error(str(e))

st.divider()
st.subheader("Manage existing subscription")
if st.button("Open Billing Portal"):
    try:
        result = api.create_portal(company_id, return_url="http://localhost:8501/Billing")
        st.markdown(f"[Open Stripe Billing Portal →]({result['portal_url']})")
    except api.ApiError as e:
        st.error(str(e))

st.divider()
st.subheader("Invoice History")
try:
    invoices = api.list_invoices(company_id)
except api.ApiError as e:
    st.error(str(e))
    invoices = []

if not invoices:
    st.caption("No invoices yet — they'll appear here after your first payment.")
else:
    for inv in invoices:
        col1, col2, col3 = st.columns([2, 2, 1])
        col1.write(f"{inv['plan'].capitalize()} Plan")
        col2.write(f"${inv['amount']:,.2f} {inv['currency'].upper()} — {inv['created_at'][:10]}")
        if col3.button("Download PDF", key=f"inv_{inv['id']}"):
            try:
                pdf_bytes = api.download_invoice_pdf(inv["id"])
                st.download_button("Save Receipt", pdf_bytes, file_name=f"invoice_{inv['id'][:8]}.pdf", mime="application/pdf", key=f"dl_{inv['id']}")
            except api.ApiError as e:
                st.error(str(e))
