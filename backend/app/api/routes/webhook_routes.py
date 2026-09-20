"""
api/routes/webhook_routes.py

WHAT THIS FILE DOES:
Receives incoming webhooks from Vapi. Event types handled:

1. "status-update" — fired when a call's status changes (ringing,
   in-progress, ended). Creates/updates a LiveCall row, which is what
   powers the "Live Calls" dashboard page — watch a call happen instead
   of only seeing it after it's over.

2. "transcript" — fired repeatedly DURING a call as speech is
   transcribed. Appends each chunk to the LiveCall's live_transcript, so
   the dashboard can show a near-real-time transcript as the
   conversation happens.

3. "function-call" — fired mid-call when the agent decides to trigger an
   action (book_appointment, take_order, etc). Dispatches to
   services/action_handler.py, returns the result so Vapi speaks it back
   to the caller in real time.

4. "end-of-call-report" — fired when a call ends, containing the full
   transcript, summary, and duration. Saved as a CallLog row (permanent
   history + analytics), and the matching LiveCall row is cleaned up
   since the call is no longer "live."

No auth on this endpoint (webhooks can't send a user JWT) — instead, we
verify the `x-vapi-secret` header against VAPI_WEBHOOK_SECRET (set below
and configured on the assistant's server URL in Vapi). Requests with a
missing or wrong secret are rejected with 401 before any processing.
"""

import hmac
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.models.agent import Agent
from app.models.call_log import CallLog
from app.models.live_call import LiveCall, LiveCallStatus
from app.services.action_handler import execute_action

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _verify_vapi_signature(request: Request) -> None:
    """
    Rejects the request if VAPI_WEBHOOK_SECRET is configured but the
    incoming request's x-vapi-secret header doesn't match. If no secret
    is configured yet (e.g. still in early local testing), verification
    is skipped — but this means the endpoint is unprotected, so set this
    before going live.
    """
    if not settings.VAPI_WEBHOOK_SECRET:
        if settings.ENVIRONMENT.lower() == "production":
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook secret is not configured.")
        return
    incoming_secret = request.headers.get("x-vapi-secret")
    if not hmac.compare_digest(incoming_secret or "", settings.VAPI_WEBHOOK_SECRET):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature.")


@router.post("/vapi")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    _verify_vapi_signature(request)
    payload = await request.json()
    message = payload.get("message", {})
    message_type = message.get("type")

    if message_type == "status-update":
        return _handle_status_update(db, message)

    if message_type == "transcript":
        return _handle_transcript_chunk(db, message)

    if message_type == "function-call":
        return _handle_function_call(db, message)

    if message_type == "end-of-call-report":
        return _handle_end_of_call(db, message)

    # Unknown event types are acknowledged but ignored, so Vapi doesn't retry forever.
    return {"received": True}


def _handle_status_update(db: Session, message: dict) -> dict:
    call = message.get("call", {})
    assistant_id = call.get("assistantId")
    call_id = call.get("id")
    vapi_status = message.get("status") or call.get("status")

    agent = db.query(Agent).filter(Agent.vapi_assistant_id == assistant_id).first()
    if not agent or not call_id:
        return {"received": True}

    live_call = db.query(LiveCall).filter(LiveCall.vapi_call_id == call_id).first()

    if vapi_status == "ended":
        # Call is over — remove it from the "live" view. The permanent
        # record gets saved separately by _handle_end_of_call.
        if live_call:
            db.delete(live_call)
            db.commit()
        return {"received": True}

    status_map = {"ringing": LiveCallStatus.ringing, "in-progress": LiveCallStatus.in_progress}
    mapped_status = status_map.get(vapi_status, LiveCallStatus.ringing)

    if live_call:
        live_call.status = mapped_status
    else:
        live_call = LiveCall(
            company_id=agent.company_id, agent_id=agent.id, vapi_call_id=call_id,
            caller_number=call.get("customer", {}).get("number"), status=mapped_status, live_transcript="",
        )
        db.add(live_call)

    # Fetch the live audio listen URL once, when the call connects — this
    # is what powers "Listen Live" in the dashboard. Vapi returns this via
    # the call's `monitor` object; not all call types include it, so this
    # is wrapped defensively and never blocks status processing if it fails.
    if mapped_status == LiveCallStatus.in_progress and not live_call.listen_url:
        try:
            from app.services import vapi_service
            call_details = vapi_service.get_call(call_id)
            monitor = call_details.get("monitor", {})
            if monitor.get("listenUrl"):
                live_call.listen_url = monitor["listenUrl"]
        except Exception:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Could not fetch listenUrl for call %s — Listen Live will be unavailable for this call.", call_id)

    db.commit()
    return {"received": True}


def _handle_transcript_chunk(db: Session, message: dict) -> dict:
    call = message.get("call", {})
    call_id = call.get("id")
    role = message.get("role", "unknown")
    text = message.get("transcript", "")
    transcript_type = message.get("transcriptType", "final")

    # Only append FINAL transcript chunks — Vapi also sends "partial"
    # chunks that get corrected/replaced as speech recognition refines,
    # appending those would produce garbled duplicate text.
    if transcript_type != "final" or not text or not call_id:
        return {"received": True}

    live_call = db.query(LiveCall).filter(LiveCall.vapi_call_id == call_id).first()
    if not live_call:
        return {"received": True}

    speaker_label = "Caller" if role == "user" else "Agent"
    live_call.live_transcript = (live_call.live_transcript or "") + f"\n{speaker_label}: {text}"
    live_call.status = LiveCallStatus.in_progress

    if role == "user":
        from app.services.sentiment_service import is_frustrated, is_opt_out_request
        if is_frustrated(text):
            live_call.frustration_flagged = "true"
 
        if is_opt_out_request(text) and live_call.caller_number:
            from app.services.campaign_service import add_to_do_not_call
            add_to_do_not_call(
                db, live_call.company_id, live_call.caller_number,
                reason=f"Caller requested no further contact during call on {live_call.started_at}",
            )


def _handle_function_call(db: Session, message: dict) -> dict:
    call = message.get("call", {})
    assistant_id = call.get("assistantId")
    call_id = call.get("id")
    caller_phone = call.get("customer", {}).get("number")
    function_call = message.get("functionCall", {})
    action_name = function_call.get("name")
    parameters = function_call.get("parameters", {})

    agent = db.query(Agent).filter(Agent.vapi_assistant_id == assistant_id).first()
    if not agent:
        return {"result": "Sorry, something went wrong on our end."}

    result = execute_action(db, agent.company_id, action_name, parameters, vapi_call_id=call_id, caller_phone=caller_phone)
    return result


def _handle_end_of_call(db: Session, message: dict) -> dict:
    call = message.get("call", {})
    assistant_id = call.get("assistantId")

    # Check A/B test variants FIRST — variant assistants aren't tied to a
    # real Agent row, so the agent lookup below would incorrectly treat
    # them as "unknown call" and exit before ever recording their stats.
    from app.models.prompt_variant import PromptVariant
    variant = db.query(PromptVariant).filter(PromptVariant.vapi_assistant_id == assistant_id).first()
    if variant:
        variant.calls_count = (variant.calls_count or 0) + 1
        summary_lower = (message.get("summary") or "").lower()
        if any(k in summary_lower for k in ["booked", "order", "scheduled", "confirmed", "reserved"]):
            variant.conversions_count = (variant.conversions_count or 0) + 1
        db.commit()
        return {"received": True}

    agent = db.query(Agent).filter(Agent.vapi_assistant_id == assistant_id).first()
    if not agent:
        return {"received": True}

    started_at_raw = call.get("startedAt")
    ended_at_raw = call.get("endedAt")

    log = CallLog(
        agent_id=agent.id,
        vapi_call_id=call.get("id"),
        caller_number=call.get("customer", {}).get("number"),
        channel="phone" if call.get("type") == "inboundPhoneCall" else "web_widget",
        started_at=_parse_iso(started_at_raw),
        ended_at=_parse_iso(ended_at_raw),
        duration_seconds=message.get("durationSeconds"),
        transcript=message.get("transcript"),
        summary=message.get("summary"),
        recording_url=message.get("recordingUrl"),
        cost=message.get("cost"),
    )
    db.add(log)

    # If this call was part of an outbound campaign, update the contact's
    # status and roll it into the campaign's completed count.
    from app.models.campaign import CampaignContact, ContactStatus, Campaign
    contact = db.query(CampaignContact).filter(CampaignContact.vapi_call_id == call.get("id")).first()
    if contact:
        contact.status = ContactStatus.completed if (message.get("durationSeconds") or 0) > 5 else ContactStatus.no_answer
        contact.outcome_notes = message.get("summary")
        campaign = db.query(Campaign).filter(Campaign.id == contact.campaign_id).first()
        if campaign:
            campaign.calls_completed = (campaign.calls_completed or 0) + 1

    # Safety net: remove the LiveCall row if it's still around (normally
    # cleaned up by the "ended" status-update, but webhooks can arrive
    # out of order or get missed).
    live_call = db.query(LiveCall).filter(LiveCall.vapi_call_id == call.get("id")).first()
    if live_call:
        db.delete(live_call)

    # Keep the company's monthly usage counter updated for billing/limits enforcement
    minutes_used = int((message.get("durationSeconds") or 0) / 60)
    if minutes_used:
        agent.company.monthly_minutes_used = (agent.company.monthly_minutes_used or 0) + minutes_used

    db.commit()

    from app.services import post_call_workflow
    try:
        post_call_workflow.run(db, log, company_name=agent.company.name)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Post-call workflow failed for call_log %s", log.id)

    return {"received": True}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
