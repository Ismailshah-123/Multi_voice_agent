"""
utils/page_layout.py

One shared header, section title, spacer and empty state so every page looks and spaces the same.

    render_page_header("Dashboard", "Manage your companies and AI agents.")
"""

import re
import streamlit as st

SPACING = {
    "section": "<div style='height: 28px;'></div>",
    "small": "<div style='height: 12px;'></div>",
    "large": "<div style='height: 44px;'></div>",
}


def render_page_header(title: str, subtitle: str = ""):
    title = re.sub(r"^[^\w]+", "", title)  # drop leading emoji for a cleaner, more professional header
    sub = f'<div style="font-size:15px;color:#5A6B85;margin-top:6px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="padding-bottom:18px;margin-bottom:26px;border-bottom:1px solid #DDE5F0;">
            <div style="font-family:'Manrope',sans-serif;font-size:30px;font-weight:800;letter-spacing:-.015em;color:#0B2545;">{title}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str):
    st.markdown(
        f"""<div style="font-family:'Manrope',sans-serif;font-size:19px;font-weight:600;
                    color:#0B2545;margin-top:8px;margin-bottom:12px;">{title}</div>""",
        unsafe_allow_html=True,
    )


def spacer(size: str = "section"):
    st.markdown(SPACING.get(size, SPACING["section"]), unsafe_allow_html=True)


def render_empty_state(icon: str, message: str, action_hint: str = ""):
    hint = f'<div style="font-size:13px;color:#5A6B85;">{action_hint}</div>' if action_hint else ""
    st.markdown(
        f"""
        <div style="text-align:center;padding:44px 20px;border:1px solid #DDE5F0;
                    border-radius:14px;background:#FFFFFF;">
            <div style="width:44px;height:44px;margin:0 auto 14px;border-radius:50%;background:#EAF1FF;
                        line-height:44px;font-size:20px;">{icon}</div>
            <div style="font-size:15px;color:#0B2545;font-weight:600;margin-bottom:6px;">{message}</div>
            {hint}
        </div>
        """,
        unsafe_allow_html=True,
    )
