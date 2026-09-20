"""
api/routes/demo_routes.py

WHAT THIS FILE DOES:
Public, UNAUTHENTICATED endpoint that lets a visitor on the landing page
try a live sample agent conversation before ever signing up — this is
the single strongest sales tool a self-serve SaaS can have: let the
prospect experience the product in 10 seconds instead of reading about
it. Uses the same free Groq text-chat mechanism as the authenticated
preview-chat endpoint (agent_routes.py), just with a fixed demo
persona instead of a real deployed agent, and no company/auth required.

Rate-limiting note: this endpoint has no auth, so it's a potential
target for abuse (someone scripting excessive free Groq calls through
your key). For production, put a simple rate limit in front of this
route (e.g. via a reverse proxy, or slowapi) before launching publicly —
flagged here rather than silently left as a risk.
"""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# Per-IP limit so nobody can burn your Groq quota through this public endpoint.
# Behind a proxy (Render, nginx) run uvicorn with --proxy-headers so client.host is the real visitor IP.
_HITS: dict[str, deque] = defaultdict(deque)
_LIMIT, _WINDOW = 10, 60  # 10 messages / minute / IP


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if len(_HITS) > 5000:
        for k in [k for k, q in _HITS.items() if not q or now - q[-1] > _WINDOW]:
            del _HITS[k]
    q = _HITS[ip]
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= _LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many demo messages. Please wait a minute and try again.")
    q.append(now)

DEMO_SYSTEM_PROMPT = """You are Bella, the AI voice assistant for "Bella's Pizza & Pasta", a busy Italian \
restaurant, in a live product demo. Stay fully in character as a warm, efficient restaurant phone assistant. \
You can: take food orders (ask for items and confirm them back), answer menu questions (the menu includes \
Margherita Pizza $14, Pepperoni Pizza $16, Spaghetti Carbonara $15, Caesar Salad $9, Tiramisu $8), reserve \
tables, and share that hours are 11am-10pm daily. Keep responses natural, brief, and conversational — the way \
a real phone call sounds, not a chatbot. If asked what this demo is, briefly mention this is a live example of \
an AI Voice Agent Platform where any business can deploy an agent like this in minutes, then continue in \
character."""


@router.post("/chat")
def demo_chat(payload: dict, request: Request):
    """
    Public demo chat — no auth, no company required. Body:
    {"message": str, "history": [{"role": "user"|"assistant", "content": str}]}
    """
    from app.services.preview_chat_service import send_preview_message

    _rate_limit(request)
    message = str(payload.get("message", "")).strip()
    raw_history = payload.get("history", [])
    raw_history = raw_history if isinstance(raw_history, list) else []
    history = [
        {"role": h["role"] if h.get("role") in ("user", "assistant") else "user", "content": str(h.get("content", ""))[:500]}
        for h in raw_history[-10:] if isinstance(h, dict)
    ]  # capped + sanitised to keep demo calls cheap and safe

    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message is required.")
    if len(message) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message too long for the demo.")

    try:
        reply = send_preview_message(DEMO_SYSTEM_PROMPT, history, message)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return {"reply": reply}
