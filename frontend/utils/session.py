"""
utils/session.py

WHAT THIS FILE DOES:
Small shared helpers used by every page: checking whether the user is
logged in (redirecting to the login page if not), and the static list of
industries shown in dropdowns (mirrors the keys seeded in the backend's
industry_templates.py — keep these in sync if you add a new industry).
"""

import streamlit as st

INDUSTRIES = [
    ("clinic", "Clinic / Medical Practice"),
    ("restaurant", "Restaurant"),
    ("dental_clinic", "Dental Clinic"),
    ("hotel", "Hotel"),
    ("real_estate", "Real Estate"),
    ("gym", "Gym / Fitness Center"),
    ("salon", "Salon / Spa"),
    ("law_firm", "Law Firm"),
    ("ecommerce", "E-commerce"),
    ("hr", "HR / Recruiting"),
    ("cold_caller", "Cold Calling / Outbound Sales"),
]

ACTIONS_BY_INDUSTRY = {
    "clinic": ["book_appointment", "cancel_appointment", "reschedule_appointment", "emergency_routing", "insurance_faq"],
    "restaurant": ["take_order", "reserve_table", "cancel_order", "track_delivery", "menu_faq"],
    "dental_clinic": ["book_appointment", "emergency_routing", "insurance_faq", "tooth_pain_guide"],
    "hotel": ["book_room", "cancel_appointment", "pricing_faq"],
    "real_estate": ["schedule_visit", "mortgage_faq"],
    "gym": ["book_personal_trainer", "pricing_faq"],
    "salon": ["book_appointment", "pricing_faq"],
    "law_firm": ["schedule_meeting", "create_crm_lead", "legal_faq"],
    "ecommerce": ["track_order", "cancel_order", "pricing_faq"],
    "hr": ["schedule_interview", "create_crm_lead"],
    "cold_caller": ["qualify_lead", "book_followup_call", "create_crm_lead"],
}


def require_login():
    """Call at the top of every protected page. Redirects to login if not authenticated."""
    if "access_token" not in st.session_state:
        st.warning("Please log in to continue.")
        st.stop()


def require_company():
    """Call on pages that need an active company selected."""
    if "active_company_id" not in st.session_state:
        st.warning("Select or create a company first from the Dashboard.")
        st.stop()


def industry_label(key: str) -> str:
    return dict(INDUSTRIES).get(key, key)
