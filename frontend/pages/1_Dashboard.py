"""
pages/1_Dashboard.py

WHAT THIS FILE DOES:
The main dashboard. Lets the user create a Company (their business /
tenant) and select which one is "active" (stored in session_state as
active_company_id, used by every other page). Also lists all agents
under the active company with their live status.
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login, INDUSTRIES
from utils.theme import inject_theme, pulse_dot
from utils.vapi_widget import render_vapi_call_widget
from utils.enterprise_widgets import render_animated_kpi_row

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
inject_theme()

require_login()
st.title("📊 Dashboard")

# ---- Create Company ----
with st.expander("➕ Create a new company", expanded=False):
    with st.form("create_company_form"):
        name = st.text_input("Company Name", placeholder="Bella Pizza")
        industry = st.selectbox(
            "Industry",
            options=[key for key, _ in INDUSTRIES],
            format_func=lambda k: dict(INDUSTRIES)[k]
        )
        website = st.text_input("Website (optional)")
        timezone = st.text_input("Timezone", value="UTC")
        submitted = st.form_submit_button("Create Company", type="primary")

        if submitted:
            if not name:
                st.error("Company name is required.")
            else:
                try:
                    company = api.create_company(name, industry, website, timezone)
                    st.session_state["active_company_id"] = company["id"]
                    st.success(
                        f"Created '{company['name']}'. It's now your active company."
                    )
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))

# ---- Company selector ----
try:
    companies = api.list_companies()
except api.ApiError as e:
    st.error(str(e))
    st.stop()

if not companies:
    st.info(
        "You don't have any companies yet. Create one above to get started."
    )
    st.stop()

company_options = {
    c["id"]: f"{c['name']} ({dict(INDUSTRIES).get(c['industry'], c['industry'])})"
    for c in companies
}

active_id = st.session_state.get(
    "active_company_id",
    companies[0]["id"]
)

selected_id = st.selectbox(
    "Active company",
    options=list(company_options.keys()),
    format_func=lambda cid: company_options[cid],
    index=(
        list(company_options.keys()).index(active_id)
        if active_id in company_options
        else 0
    ),
)

st.session_state["active_company_id"] = selected_id

active_company = next(
    c for c in companies if c["id"] == selected_id
)

# ---- Human handoff / escalation number ----
with st.expander("📞 Human Handoff Settings"):
    st.caption(
        "If set, every agent can transfer callers to this number when it "
        "can't help or the caller seems frustrated. Redeploy agents after changing this."
    )

    current_number = active_company.get("escalation_phone_number") or ""

    new_number = st.text_input(
        "Escalation phone number",
        value=current_number,
        placeholder="+15551234567"
    )

    if st.button("Save Escalation Number", type="primary"):
        try:
            api.set_escalation_number(selected_id, new_number)
            st.success(
                "Saved. Redeploy your agents for this to take effect on new calls."
            )
        except api.ApiError as e:
            st.error(str(e))

# ---- Onboarding checklist ----
try:
    onboarding = api.get_onboarding_status(selected_id)

    if not onboarding["is_fully_onboarded"]:
        with st.container(border=True):
            st.markdown(
                f"**🚀 Getting started "
                f"({onboarding['completed']}/{onboarding['total']})**"
            )

            st.progress(
                onboarding["completed"] / onboarding["total"]
            )

            for step in onboarding["steps"]:
                icon = "✅" if step["done"] else "⬜"
                st.caption(f"{icon} {step['label']}")

except api.ApiError:
    pass

minutes_pct = (
    round(
        (
            active_company["monthly_minutes_used"]
            / active_company["monthly_minutes_limit"]
        ) * 100,
        0
    )
    if active_company["monthly_minutes_limit"]
    else 0
)

render_animated_kpi_row([
    {
        "label": "Minutes Used",
        "value": active_company["monthly_minutes_used"],
        "sub": f"of {active_company['monthly_minutes_limit']} this month",
        "color": "#0EA5E9"
    },
    {
        "label": "Usage",
        "value": minutes_pct,
        "suffix": "%",
        "sub": "of monthly plan limit",
        "color": "#1D4ED8"
    },
], height=140)

badge_col1, badge_col2, badge_col3 = st.columns(3)

badge_col1.markdown(
    f"**Plan:** {active_company['plan_tier'].capitalize()}"
)

badge_col2.markdown(
    f"**Industry:** "
    f"{dict(INDUSTRIES).get(active_company['industry'], active_company['industry'])}"
)

badge_col3.markdown(
    f"**Timezone:** {active_company['timezone']}"
)

st.divider()
st.subheader(f"Agents for {active_company['name']}")

try:
    agents = api.list_agents(selected_id)
except api.ApiError as e:
    st.error(str(e))
    agents = []

if not agents:
    st.info(
        "No agents yet. Go to **Create Agent** in the sidebar "
        "to deploy your first AI employee."
    )
else:
    for agent in agents:
        status_color = {
            "deployed": None,
            "deploying": "🟡",
            "failed": "🔴",
            "paused": "⚪",
            "draft": "⚪"
        }.get(agent["status"], "⚪")

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])

            if agent["status"] == "deployed":
                c1.markdown(
                    f"{pulse_dot()} **{agent['name']}**",
                    unsafe_allow_html=True
                )
            else:
                c1.markdown(
                    f"**{status_color} {agent['name']}**"
                )

            c1.caption(
                dict(INDUSTRIES).get(
                    agent["industry_key"],
                    agent["industry_key"]
                )
            )

            c2.write(
                f"Phone: {agent.get('phone_number') or 'Not provisioned'}"
            )

            c2.caption(
                f"Status: {agent['status']}"
            )

            if c3.button(
                "Delete",
                key=f"del_{agent['id']}"
            ):
                try:
                    api.delete_agent(agent["id"])
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))

            with st.expander(
                "💬 Test this agent (free, no call minutes used)"
            ):
                tab_text, tab_voice = st.tabs(
                    ["Text Chat (free)", "🎙️ Real Voice Call"]
                )

                with tab_text:
                    chat_key = f"chat_history_{agent['id']}"

                    if chat_key not in st.session_state:
                        st.session_state[chat_key] = []

                    for turn in st.session_state[chat_key]:
                        with st.chat_message(turn["role"]):
                            st.write(turn["content"])

                    user_msg = st.chat_input(
                        "Type what a caller might say...",
                        key=f"input_{agent['id']}"
                    )

                    if user_msg:
                        st.session_state[chat_key].append({
                            "role": "user",
                            "content": user_msg
                        })

                        try:
                            result = api.preview_chat(
                                agent["id"],
                                user_msg,
                                st.session_state[chat_key][:-1]
                            )

                            st.session_state[chat_key].append({
                                "role": "assistant",
                                "content": result["reply"]
                            })

                        except api.ApiError as e:
                            st.error(str(e))

                        st.rerun()

                with tab_voice:
                    st.caption(
                        "Uses real Vapi call minutes — talk to your actual "
                        "deployed agent through your browser microphone."
                    )

                    render_vapi_call_widget(agent["id"])

            with st.expander("🧪 A/B Testing"):
                try:
                    variants = api.list_variants(agent["id"])

                    for v in variants:
                        col1, col2 = st.columns([4, 1])

                        if v["calls_count"] is None:
                            col1.write(
                                f"**{v['variant_label']}** (baseline)"
                            )
                        else:
                            col1.write(
                                f"**{v['variant_label']}** — "
                                f"{v['calls_count']} calls, "
                                f"{v['conversion_rate']}% conversion rate"
                            )

                            if v["id"] != "original":
                                if col2.button(
                                    "Delete",
                                    key=f"del_variant_{v['id']}"
                                ):
                                    try:
                                        api.delete_variant(
                                            agent["id"],
                                            v["id"]
                                        )

                                        st.success(
                                            f"Variant '{v['variant_label']}' deleted."
                                        )

                                        st.rerun()

                                    except api.ApiError as e:
                                        st.error(str(e))

                except api.ApiError as e:
                    st.error(str(e))

            st.divider()

            with st.form(
                f"variant_form_{agent['id']}",
                clear_on_submit=True
            ):
                variant_label = st.text_input(
                    "Variant label",
                    value="B",
                    key=f"vlabel_{agent['id']}"
                )

                variant_prompt = st.text_area(
                    "Modified system prompt",
                    value=agent.get("system_prompt", ""),
                    height=100,
                    key=f"vprompt_{agent['id']}"
                )

                if st.form_submit_button("Deploy Variant", type="primary"):
                    try:
                        result = api.create_variant(
                            agent["id"],
                            variant_label,
                            variant_prompt
                        )

                        st.success(
                            f"Variant '{result['variant_label']}' deployed."
                        )

                        st.rerun()

                    except api.ApiError as e:
                        st.error(str(e))