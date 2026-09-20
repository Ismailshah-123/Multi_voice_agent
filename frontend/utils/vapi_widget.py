"""
utils/vapi_widget.py

WHAT THIS FILE DOES:
Embeds the real Vapi voice-call widget by loading it in an iframe
pointed at a REAL backend URL (utils.api_client.BACKEND_URL +
/vapi-widget/page/{agent_id}), instead of injecting HTML directly via
Streamlit's `components.html()`.

WHY: components.html() renders content in a SANDBOXED iframe with a
`null` origin (it uses `srcdoc`, not a real URL). Vapi's web calls run
through Daily.co's WebRTC layer, which requires postMessage
communication between frames — and that handshake silently fails
against a null origin, which is exactly why the call previously got
stuck at "Connecting..." forever with no visible error. Loading the
widget from a real `src=` URL (http://localhost:8000/... locally, or
your public ngrok/deployed URL in production) gives it a proper origin
Daily.co can actually talk to.
"""

import streamlit as st
import streamlit.components.v1 as components
from utils import api_client as api


def render_vapi_call_widget(agent_id: str, height: int = 300):
    """
    Renders the voice call widget via a real iframe src=, not injected
    HTML. Still checks config first (through the authenticated JSON
    endpoint) so we can show a clear message if Vapi isn't configured,
    before ever loading the iframe.
    """
    try:
        config = api._request("GET", f"/api/v1/vapi-widget/config/{agent_id}")
    except api.ApiError as e:
        st.error(f"Couldn't load call widget: {e}")
        return

    if not config.get("configured"):
        st.warning(
            "Live voice call isn't ready yet. Make sure VAPI_PUBLIC_KEY is set in your backend's .env "
            "and this agent has been successfully deployed to Vapi."
        )
        return

    widget_page_url = f"{api.BACKEND_URL}/api/v1/vapi-widget/page/{agent_id}"
    components.iframe(src=widget_page_url, height=height, scrolling=False)