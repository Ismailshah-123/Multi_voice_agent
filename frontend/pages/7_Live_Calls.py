"""
pages/7_Live_Calls.py

WHAT THIS FILE DOES:
Shows calls that are CURRENTLY in progress with a real phone-call-style
interface — a ringing/connected visual state, the streaming transcript,
and a "Listen Live" button that connects to Vapi's real audio websocket
so you can actually hear the call happening. Populated by Vapi's
status-update and transcript webhooks (webhook_routes.py) into the
LiveCall table. Uses polling (refresh every few seconds) for the
transcript/status; audio listening itself is a direct browser websocket
connection, not polled.
"""

import time
import streamlit as st
from utils import api_client as api
from utils.session import require_login, require_company
from utils.theme import inject_theme, section_header
from utils.live_listen_widget import render_listen_live_widget

st.set_page_config(page_title="Live Calls", page_icon="🔴", layout="wide")
inject_theme()
require_login()
require_company()

company_id = st.session_state["active_company_id"]

CALL_CARD_CSS = """
<style>
.call-phone-card {
    background: #FFFFFF;
    border: 1px solid rgba(11, 37, 69, 0.25);
    border-radius: 18px;
    padding: 20px;
    margin-bottom: 14px;
}
.call-ring-icon {
    display: inline-block; width: 46px; height: 46px; border-radius: 50%;
    background: linear-gradient(135deg, #1D4ED8, #1E40AF);
    text-align: center; line-height: 46px; font-size: 20px;
    animation: ring-pulse 1.4s infinite;
}
@keyframes ring-pulse {
    0% { box-shadow: 0 0 0 0 rgba(29, 78, 216, 0.6); }
    70% { box-shadow: 0 0 0 14px rgba(29, 78, 216, 0); }
    100% { box-shadow: 0 0 0 0 rgba(29, 78, 216, 0); }
}
.call-connected-icon {
    display: inline-block; width: 46px; height: 46px; border-radius: 50%;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    text-align: center; line-height: 46px; font-size: 20px;
}
.call-number { font-size: 17px; font-weight: 700; color: #0B2545; }
.call-status-text { font-size: 12px; color: #5A6B85; text-transform: uppercase; letter-spacing: 1px; }
.frustration-alert {
    background: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.4);
    border-radius: 10px; padding: 8px 12px; margin-top: 10px; color: #fca5a5; font-size: 13px;
}
</style>
"""
st.markdown(CALL_CARD_CSS, unsafe_allow_html=True)

st.markdown(section_header("🔴 Live Calls"), unsafe_allow_html=True)
st.caption("Watch conversations happen in real time — see the status, read the live transcript, or listen in.")

auto_refresh = st.checkbox("Auto-refresh every 3 seconds", value=True)

try:
    live_calls = api.list_live_calls(company_id)
except api.ApiError as e:
    st.error(str(e))
    live_calls = []

if not live_calls:
    st.info("No calls in progress right now. This page updates automatically the moment a call comes in.")
else:
    for call in live_calls:
        is_ringing = call["status"] == "ringing"
        icon_class = "call-ring-icon" if is_ringing else "call-connected-icon"
        icon_emoji = "📞" if is_ringing else "🎙️"
        status_text = "Ringing..." if is_ringing else "Connected — live"

        st.markdown(f"""
        <div class="call-phone-card">
            <div style="display:flex; align-items:center; gap:14px;">
                <div class="{icon_class}">{icon_emoji}</div>
                <div>
                    <div class="call-number">{call.get("caller_number") or "Unknown number"}</div>
                    <div class="call-status-text">{status_text}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if call.get("frustration_flagged"):
            st.markdown('<div class="frustration-alert">🚨 Possible caller frustration detected in this conversation</div>', unsafe_allow_html=True)

        transcript = (call.get("live_transcript") or "").strip()
        if transcript:
            with st.expander("View live transcript", expanded=False):
                st.text_area("Transcript", transcript, height=160, key=f"transcript_{call['id']}", disabled=True, label_visibility="collapsed")
        else:
            st.caption("Waiting for the conversation to begin...")

        if call.get("listen_url"):
            with st.expander("🔊 Listen Live (uses real-time audio — see notes below)"):
                st.caption("Connects directly to the live call audio. If pitch/quality sounds off, this may need a sample-rate adjustment for your setup — see utils/live_listen_widget.py.")
                render_listen_live_widget(call["listen_url"])
        else:
            st.caption("Live audio not available yet for this call.")

        st.markdown("</div>", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(3)
    st.rerun()
