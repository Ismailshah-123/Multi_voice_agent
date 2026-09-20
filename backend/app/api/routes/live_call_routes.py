"""
api/routes/live_call_routes.py

WHAT THIS FILE DOES:
Exposes currently in-progress calls (populated by webhook_routes.py's
status-update and transcript handlers) so the dashboard's Live Calls
page can poll this and show conversations as they happen — near
real-time, via polling every few seconds rather than a websocket, which
keeps this simple and works cleanly with Streamlit.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.live_call import LiveCall
from app.api.routes.company_routes import _get_owned_company_or_404

router = APIRouter(prefix="/api/v1/live-calls", tags=["live-calls"])


@router.get("")
def list_live_calls(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    live_calls = db.query(LiveCall).filter(LiveCall.company_id == company_id).all()
    return [
        {
            "id": lc.id,
            "agent_id": lc.agent_id,
            "vapi_call_id": lc.vapi_call_id,
            "caller_number": lc.caller_number,
            "status": lc.status,
            "live_transcript": lc.live_transcript,
            "frustration_flagged": lc.frustration_flagged == "true",
            "listen_url": lc.listen_url,
            "started_at": lc.started_at,
        }
        for lc in live_calls
    ]
