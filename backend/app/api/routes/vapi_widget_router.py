"""
api/routes/vapi_widget_router.py

WHAT THIS FILE DOES:
Two endpoints for the browser voice-call widget:

1. GET /config/{agent_id} — JSON config (public key + assistant ID),
   authenticated, used internally.

2. GET /page/{agent_id} — THIS IS THE FIX. Returns a full, real HTML
   PAGE (not a JSON blob) containing the Vapi widget. Loaded by the
   frontend via a real iframe `src=` URL instead of Streamlit's
   `components.html()`.

WHY THIS MATTERS: Vapi's web calls run through Daily.co's WebRTC layer,
which communicates via postMessage between frames. Streamlit's
`components.html()` renders content inside a SANDBOXED iframe using
`srcdoc`, which has a `null` origin — Daily.co's postMessage handshake
silently fails against a null origin, which is exactly why the call got
stuck at "Connecting..." forever with no visible error. Serving this
page from a real backend URL (http://localhost:8000/... or your public
ngrok URL) gives it a real origin, which is the same fix used
successfully in an earlier project for the identical Daily.co
null-origin issue.

NOTE ON AUTH: this /page endpoint intentionally does NOT require a JWT.
An iframe's `src=` is a plain browser navigation — it cannot attach a
custom Authorization header the way a fetch() call can. This is safe
because the only things exposed here (Vapi's PUBLIC key and the
assistant ID) are, by Vapi's own design, meant to be embedded
client-side in a browser — never the private key.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.api.routes.agent_routes import _get_owned_agent_or_404

router = APIRouter(prefix="/api/v1/vapi-widget", tags=["vapi-widget"])


@router.get("/config/{agent_id}")
def get_widget_config(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authenticated JSON config lookup — used internally, ownership-checked."""
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)
    return {
        "public_key": settings.VAPI_PUBLIC_KEY,
        "assistant_id": agent.vapi_assistant_id,
        "agent_name": agent.name,
        "configured": bool(settings.VAPI_PUBLIC_KEY and agent.vapi_assistant_id),
    }


@router.get("/page/{agent_id}", response_class=HTMLResponse)
def serve_widget_page(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Serves the actual widget as a full HTML page with a real origin.
    No auth (see module docstring) — only exposes the Vapi public key
    and assistant ID, which are safe to expose client-side by design.
    Looked up directly (not via the owned-agent helper, since there's
    no authenticated user here) but only returns non-sensitive fields.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent or not agent.vapi_assistant_id or not settings.VAPI_PUBLIC_KEY:
        return HTMLResponse(
            "<html><body style='background:#0b0a1a;color:#f87171;font-family:sans-serif;"
            "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'>"
            "<div>Voice call isn't configured yet for this agent.</div>"
            "</body></html>",
            status_code=404,
        )

    public_key = settings.VAPI_PUBLIC_KEY
    assistant_id = agent.vapi_assistant_id
    agent_name = agent.name

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; background:#0b0a1a; font-family:sans-serif;">
        <div style="padding: 20px; color: #a89cd6; font-size: 14px;">
            Click the button below to start a live call with {agent_name}.
        </div>

        <script>
            (function (d, t) {{
                var g = d.createElement(t), s = d.getElementsByTagName(t)[0];
                g.src = "https://cdn.jsdelivr.net/gh/VapiAI/html-script-tag@latest/dist/assets/index.js";
                g.defer = true;
                g.async = true;
                s.parentNode.insertBefore(g, s);

                g.onload = function () {{
                    window.vapiSDK.run({{
                        apiKey: "{public_key}",
                        assistant: "{assistant_id}",
                        config: {{
                            position: "bottom-right",
                            offset: "10px",
                            width: "50px",
                            height: "50px",
                            idle: {{
                                color: "rgb(124, 58, 237)",
                                type: "pill",
                                title: "Talk to {agent_name}",
                                subtitle: "Click to start a call",
                                icon: "https://unpkg.com/lucide-static@0.321.0/icons/phone.svg",
                            }},
                            loading: {{
                                color: "rgb(59, 130, 246)",
                                type: "pill",
                                title: "Connecting...",
                                subtitle: "Please wait",
                                icon: "https://unpkg.com/lucide-static@0.321.0/icons/loader-2.svg",
                            }},
                            active: {{
                                color: "rgb(219, 39, 119)",
                                type: "pill",
                                title: "Call in progress",
                                subtitle: "Click to end",
                                icon: "https://unpkg.com/lucide-static@0.321.0/icons/phone-off.svg",
                            }},
                        }}
                    }});
                }};
            }})(document, "script");
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)