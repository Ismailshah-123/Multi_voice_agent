"""
pages/2_Create_Agent.py

WHAT THIS FILE DOES:
This is the "Create your AI Employee in 60 seconds" screen — the core
product experience. The user picks an industry, names the agent, adds
any custom instructions, and hits Deploy. Everything else (the prompt,
the greeting, the available actions) is generated automatically by the
backend from the industry template.
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login, require_company, INDUSTRIES, ACTIONS_BY_INDUSTRY
from utils.theme import inject_theme

st.set_page_config(layout="wide")
inject_theme()

require_login()
require_company()

st.title("🤖 Create Agent")
st.caption("Fill this out once — your AI employee handles the rest.")

company_id = st.session_state["active_company_id"]

with st.form("create_agent_form"):
    name = st.text_input("Agent Name", placeholder="Bella Pizza Order Assistant")
    industry_options = [key for key, _ in INDUSTRIES] + ["custom"]
    industry_key = st.selectbox(
        "Industry",
        options=industry_options,
        format_func=lambda k: "✨ Custom / Other business type (AI-generated)" if k == "custom" else dict(INDUSTRIES)[k],
    )

    business_description = None
    if industry_key == "custom":
        st.info("Describe your business in plain English — Groq will generate a tailored agent prompt and actions automatically. This works for ANY business type, not just the presets above.")
        business_description = st.text_area(
            "Describe your business",
            placeholder="e.g. We're a mobile dog grooming service. We travel to customers' homes, book appointments by the hour, and charge based on dog size.",
            height=100,
        )
    else:
        default_actions = ACTIONS_BY_INDUSTRY.get(industry_key, [])
        st.write("**Actions this agent can perform:**")
        st.caption(", ".join(a.replace("_", " ").title() for a in default_actions) or "None configured for this industry yet.")

    language = st.selectbox("Language", options=["en", "ur", "ar", "es", "fr", "de", "hi"], format_func=lambda l: {
        "en": "English", "ur": "Urdu", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German", "hi": "Hindi",
    }.get(l, l))

    custom_instructions = st.text_area(
        "Anything specific this agent should know or do? (optional)",
        placeholder="e.g. We're closed on Mondays. Always mention our 10% first-order discount.",
    )

    submitted = st.form_submit_button("🚀 Deploy Agent", type="primary", use_container_width=True)

    if submitted:
        if not name:
            st.error("Agent name is required.")
        elif industry_key == "custom" and not business_description:
            st.error("Please describe your business so the AI can generate the right agent.")
        else:
            spinner_text = "Generating a custom prompt with Groq and deploying..." if industry_key == "custom" else "Building your agent's prompt and deploying to the voice engine..."
            with st.spinner(spinner_text):
                try:
                    agent = api.create_agent(
                        company_id=company_id,
                        name=name,
                        industry_key=industry_key,
                        language=language,
                        custom_instructions=custom_instructions,
                        enabled_actions=None,
                        business_description=business_description,
                    )
                    st.success(f"🎉 '{agent['name']}' is live!")
                    if agent.get("phone_number"):
                        st.info(f"Phone number: {agent['phone_number']}")
                    else:
                        st.info("Your agent is deployed. Provision a phone number from the Dashboard when you're ready to go live with calls.")
                except api.ApiError as e:
                    st.error(f"Deployment failed: {e}")
