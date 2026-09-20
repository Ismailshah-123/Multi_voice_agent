
"""
services/action_handler.py

WHAT THIS FILE DOES:
When a live call is happening, Vapi sends a "function-call" webhook event
whenever the agent decides to trigger an action (e.g. the caller says
"book me for Tuesday at 3pm" and the LLM calls `book_appointment`).
webhook_routes.py receives that event and calls `execute_action()` here,
which routes to the right handler based on the action name and returns a
result Vapi speaks back to the caller.

This is intentionally a single dispatch table (not per-industry files)
because the same action name (e.g. "book_appointment") behaves the same
way structurally across industries — it just writes to this company's
calendar integration and logs a CallLog outcome. Industry-specific
behavior lives in the PROMPT, not in branching Python code.

Each handler is a stub with a clear TODO showing exactly which
integration service it should call — wire these up once Google
Calendar / WhatsApp / CRM integrations are connected for a company.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import logging

from app.services import rag_service
from app.services.integrations import google_service
from app.services.integration_token_service import (
    get_active_google_integration,
    get_valid_google_access_token,
)
from app.models.integration import Integration, IntegrationProvider
from app.models.lead import Lead, LeadStatus
from app.models.booking import Booking, BookingStatus
from app.models.customer_profile import CustomerProfile

logger = logging.getLogger(__name__)


def _default_end_time(start_iso: str) -> str:
    """If the caller/LLM didn't specify an end time, default to 30 minutes after start."""
    try:
        start_dt = datetime.fromisoformat(start_iso)
    except ValueError:
        return start_iso
    return (start_dt + timedelta(minutes=30)).isoformat()


def _upsert_lead(
    db: Session,
    company_id: uuid.UUID,
    vapi_call_id: str | None,
    name: str | None,
    phone: str | None,
    email: str | None,
    notes: str | None,
    status: LeadStatus,
) -> Lead | None:
    """
    Creates or updates a Lead row tagged with this call's vapi_call_id.
    post_call_workflow.py looks leads up by vapi_call_id once the call
    ends to send WhatsApp confirmations and finalize the record. If we
    have no call_id (e.g. called outside a live call, such as a test),
    we still create the lead, just without call-linking.
    """
    if not vapi_call_id:
        lead = Lead(
            company_id=company_id,
            name=name,
            phone=phone,
            email=email,
            notes=notes,
            status=status,
        )
        db.add(lead)
        db.commit()
        return lead

    lead = (
        db.query(Lead)
        .filter(
            Lead.company_id == company_id,
            Lead.notes.like(f"%{vapi_call_id}%"),
        )
        .first()
    )

    call_tag = f"[call:{vapi_call_id}]"
    tagged_notes = f"{notes or ''} {call_tag}".strip()

    if lead:
        lead.name = name or lead.name
        lead.phone = phone or lead.phone
        lead.email = email or lead.email
        lead.notes = tagged_notes
        lead.status = status
    else:
        lead = Lead(
            company_id=company_id,
            name=name,
            phone=phone,
            email=email,
            notes=tagged_notes,
            status=status,
        )
        db.add(lead)

    db.commit()
    db.refresh(lead)
    return lead


def execute_action(
    db: Session,
    company_id: uuid.UUID,
    action_name: str,
    parameters: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    Central dispatch: routes an incoming Vapi function-call to the right
    handler. Returns a dict that gets sent back to Vapi as the function
    result (Vapi's LLM will speak this back to the caller naturally).

    `vapi_call_id` tags any Lead created during this call so
    post_call_workflow.py can find it once the call ends and send
    confirmations (WhatsApp) / finish the CRM record.

    `caller_phone` is the caller's number as reported by Vapi — used by
    get_caller_history (repeat-caller memory) and cancellation (looking
    up this customer's most recent active booking).

    Falls back to `_infer_handler` for action names not in the static
    ACTION_HANDLERS table — this happens for custom/AI-generated agents
    where Groq invented an action name for a business type outside the
    11 presets.
    """
    handler = ACTION_HANDLERS.get(action_name) or _infer_handler(action_name)
    return handler(
        db,
        company_id,
        parameters,
        vapi_call_id,
        caller_phone,
    )


def _infer_handler(action_name: str):
    """Same keyword-based guessing as action_schemas.infer_schema_for_action, kept in sync intentionally."""
    name_lower = action_name.lower()

    if any(k in name_lower for k in ["book", "schedule", "reserve", "appointment"]):
        return _book_appointment

    if any(k in name_lower for k in ["cancel", "track", "status"]):
        return _cancel_appointment

    if any(k in name_lower for k in ["order", "purchase", "buy"]):
        return _take_order

    if any(k in name_lower for k in ["lead", "contact", "qualify", "collect"]):
        return _create_crm_lead

    return _generic_faq


def _book_appointment(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    Creates a REAL Google Calendar event if the company has connected
    Google Calendar, and — critically — saves the returned event ID on a
    Booking row. That event ID is what makes cancellation possible later:
    Google Calendar has no "cancel by name" API, so without storing this
    at creation time, cancellation could never reliably work.
    """
    integration = get_active_google_integration(db, company_id)

    customer_name = params.get("customer_name", "Customer")
    start_iso = params.get("start_datetime")
    end_iso = params.get("end_datetime") or (
        _default_end_time(start_iso) if start_iso else None
    )
    reason = params.get("reason", "Appointment")
    attendee_email = params.get("contact_email")

    _upsert_lead(
        db,
        company_id,
        vapi_call_id,
        name=customer_name,
        phone=caller_phone,
        email=attendee_email,
        notes=f"Booking: {reason} at {start_iso}",
        status=LeadStatus.booked,
    )

    booking = Booking(
        company_id=company_id,
        customer_name=customer_name,
        customer_phone=caller_phone,
        start_datetime=start_iso,
        reason=reason,
        vapi_call_id=vapi_call_id,
        status=BookingStatus.confirmed,
    )

    db.add(booking)
    db.commit()

    if not integration or not start_iso:
        return {
            "result": (
                f"I've noted the request for {customer_name}. "
                "Since I couldn't confirm the calendar slot automatically, "
                "our team will call to confirm the exact time."
            )
        }

    try:
        access_token = get_valid_google_access_token(
            db,
            integration,
        )

        event = google_service.create_calendar_event(
            access_token=access_token,
            refresh_token=integration.refresh_token,
            summary=f"{reason} — {customer_name}",
            start_iso=start_iso,
            end_iso=end_iso,
            attendee_email=attendee_email,
        )

        booking.google_event_id = event.get("id")
        db.commit()

        return {
            "result": (
                f"You're booked, {customer_name}. "
                f"I've added it to the calendar for {start_iso}."
            )
        }

    except Exception:
        logger.exception(
            "Google Calendar booking failed for company_id=%s",
            company_id,
        )

        return {
            "result": (
                f"I've recorded the request for {customer_name} at {start_iso}, "
                "but I wasn't able to confirm it on the calendar automatically "
                "— someone will follow up to confirm."
            )
        }


def _cancel_appointment(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    Finds this customer's most recent CONFIRMED booking (by phone number
    if available, otherwise by name) and actually deletes the real
    Google Calendar event — not a soft "we'll confirm" message. Falls
    back gracefully if no matching booking is found or no calendar is
    connected, so the call never breaks.
    """
    customer_name = params.get("customer_name")

    query = db.query(Booking).filter(
        Booking.company_id == company_id,
        Booking.status == BookingStatus.confirmed,
    )

    if caller_phone:
        query = query.filter(
            Booking.customer_phone == caller_phone
        )
    elif customer_name:
        query = query.filter(
            Booking.customer_name.ilike(f"%{customer_name}%")
        )
    else:
        return {
            "result": (
                "Could you confirm the name on the booking so I can find it?"
            )
        }

    booking = query.order_by(
        Booking.created_at.desc()
    ).first()

    if not booking:
        return {
            "result": (
                f"I couldn't find an upcoming booking for "
                f"{customer_name or 'that number'}. "
                "Could you double check the name or date?"
            )
        }

    booking.status = BookingStatus.cancelled
    db.commit()

    if booking.google_event_id:
        integration = get_active_google_integration(
            db,
            company_id,
        )

        if integration:
            try:
                access_token = get_valid_google_access_token(
                    db,
                    integration,
                )

                google_service.delete_calendar_event(
                    access_token,
                    booking.google_event_id,
                )

                return {
                    "result": (
                        f"Done — I've cancelled "
                        f"{booking.customer_name}'s booking "
                        f"for {booking.start_datetime}."
                    )
                }

            except Exception:
                logger.exception(
                    "Failed to delete calendar event %s for company_id=%s",
                    booking.google_event_id,
                    company_id,
                )

                return {
                    "result": (
                        f"I've marked {booking.customer_name}'s booking "
                        "as cancelled in our system — it may take a moment "
                        "to update on the calendar."
                    )
                }

    return {
        "result": (
            f"I've cancelled the booking on file for "
            f"{booking.customer_name}."
        )
    }


def _take_order(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    items = params.get("items", [])
    customer_name = params.get("customer_name", "Customer")
    delivery_or_pickup = params.get(
        "delivery_or_pickup",
        "pickup",
    )

    from app.models.order import Order, OrderStatus

    order = Order(
        company_id=company_id,
        customer_name=customer_name,
        customer_phone=caller_phone,
        items=items,
        delivery_or_pickup=delivery_or_pickup,
        vapi_call_id=vapi_call_id,
        status=OrderStatus.placed,
    )

    db.add(order)
    db.commit()

    _upsert_lead(
        db,
        company_id,
        vapi_call_id,
        name=customer_name,
        phone=caller_phone,
        email=None,
        notes=(
            f"Order: "
            f"{', '.join(items) if items else 'items received'} "
            f"({delivery_or_pickup})"
        ),
        status=LeadStatus.booked,
    )

    return {
        "result": (
            f"Order confirmed: "
            f"{', '.join(items) if items else 'items received'}. "
            "Thank you!"
        )
    }


def _cancel_order(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    Finds this customer's most recent PLACED order (by phone if
    available, otherwise by name) and actually cancels it — not a
    soft "we'll confirm" message. Same real-cancellation pattern
    already proven for appointment bookings via the Booking model.
    """
    from app.models.order import Order, OrderStatus

    customer_name = params.get("customer_name")

    query = db.query(Order).filter(
        Order.company_id == company_id,
        Order.status == OrderStatus.placed,
    )

    if caller_phone:
        query = query.filter(
            Order.customer_phone == caller_phone
        )
    elif customer_name:
        query = query.filter(
            Order.customer_name.ilike(f"%{customer_name}%")
        )
    else:
        return {
            "result": (
                "Could you confirm the name on the order "
                "so I can find it?"
            )
        }

    order = query.order_by(
        Order.created_at.desc()
    ).first()

    if not order:
        return {
            "result": (
                f"I couldn't find a recent order for "
                f"{customer_name or 'that number'}. "
                "Could you double check the name?"
            )
        }

    order.status = OrderStatus.cancelled
    db.commit()

    return {
        "result": (
            f"Done — I've cancelled the order for "
            f"{order.customer_name}."
        )
    }


def _create_crm_lead(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    _upsert_lead(
        db,
        company_id,
        vapi_call_id,
        name=params.get("customer_name"),
        phone=params.get("contact_phone") or caller_phone,
        email=params.get("contact_email"),
        notes=params.get("notes"),
        status=LeadStatus.qualified,
    )

    return {
        "result": (
            "Got it, I've logged your details and someone will follow up."
        )
    }


def _track_order(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    # TODO: query the company's order system / e-commerce platform API
    return {
        "result": (
            "Let me check that order status for you — "
            "it's currently being processed."
        )
    }


def _generic_faq(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    Answers from this company's uploaded knowledge base via RAG (hybrid
    search + cross-encoder rerank + semantic cache). Falls back
    gracefully if nothing is uploaded yet or no relevant chunks are found.
    """
    question = (
        params.get("question")
        or params.get("query")
        or ""
    )

    if not question:
        return {
            "result": (
                "Could you tell me a bit more about what you'd like to know?"
            )
        }

    answer = rag_service.answer_from_knowledge_base(
        company_id,
        question,
    )

    return {"result": answer}


def _get_caller_history(
    db: Session,
    company_id: uuid.UUID,
    params: dict,
    vapi_call_id: str | None = None,
    caller_phone: str | None = None,
) -> dict:
    """
    REPEAT-CALLER MEMORY. The agent calls this early in a conversation
    (its tool description tells the LLM to use it when a call starts) to
    check if this phone number has called before. Returns a short
    natural-language summary the agent can use to personalize the
    greeting — "Welcome back, Sarah! Last time you ordered a Margherita
    pizza." First-time callers get a clear "no history" signal instead.
    """
    if not caller_phone:
        return {
            "result": (
                "This appears to be a new caller with no phone number "
                "on record."
            )
        }

    profile = (
        db.query(CustomerProfile)
        .filter(
            CustomerProfile.company_id == company_id,
            CustomerProfile.phone == caller_phone,
        )
        .first()
    )

    if not profile or profile.visit_count == 0:
        return {
            "result": (
                "This is a new caller — no previous history. "
                "Greet them normally, no need to mention repeat-visit context."
            )
        }

    name_part = (
        f"Their name is {profile.name}. "
        if profile.name
        else ""
    )

    summary_part = (
        f"Last interaction: {profile.last_summary}. "
        if profile.last_summary
        else ""
    )

    facts_part = ""

    if profile.structured_facts:
        fact_strings = [
            f"{k.replace('_', ' ')}: {v}"
            for k, v in profile.structured_facts.items()
            if v
        ]

        if fact_strings:
            facts_part = (
                "Known preferences/notes — "
                f"{'; '.join(fact_strings)}. "
            )

    return {
        "result": (
            f"This is a RETURNING caller "
            f"(visit #{profile.visit_count + 1}). "
            f"{name_part}"
            f"{summary_part}"
            f"{facts_part}"
            "You can greet them warmly by name and use these details "
            "naturally if relevant — do not read them out as a list."
        )
    }


# Dispatch table: action name (as defined in industry_templates.py
# default_actions) -> handler function
ACTION_HANDLERS = {
    "get_caller_history": _get_caller_history,
    "book_appointment": _book_appointment,
    "cancel_appointment": _cancel_appointment,
    "reschedule_appointment": _book_appointment,
    "take_order": _take_order,
    "reserve_table": _book_appointment,
    "cancel_order": _cancel_order,
    "track_order": _track_order,
    "track_delivery": _track_order,
    "create_crm_lead": _create_crm_lead,
    "qualify_lead": _create_crm_lead,
    "book_followup_call": _book_appointment,
    "schedule_visit": _book_appointment,
    "schedule_meeting": _book_appointment,
    "schedule_interview": _book_appointment,
    "book_room": _book_appointment,
    "book_personal_trainer": _book_appointment,

    # FAQ / info-lookup style actions all default to the RAG lookup stub
    "menu_faq": _generic_faq,
    "insurance_faq": _generic_faq,
    "legal_faq": _generic_faq,
    "mortgage_faq": _generic_faq,
    "pricing_faq": _generic_faq,
    "tooth_pain_guide": _generic_faq,
    "emergency_routing": _generic_faq,
}

