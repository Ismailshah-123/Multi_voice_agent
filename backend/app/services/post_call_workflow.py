"""
services/post_call_workflow.py

WHAT THIS FILE DOES:
This is the "Transcript -> Summary -> CRM Update -> Send WhatsApp
Confirmation" automation from the product spec. It runs automatically
once a call ends (triggered from webhook_routes._handle_end_of_call,
right after the CallLog is saved). It does three things:

  1. Finds any Lead created DURING the call (tagged with this
     vapi_call_id by action_handler.py's booking/order/CRM actions) and
     links it to the finished CallLog for a complete record.
  2. Sends a WhatsApp confirmation to the caller if we captured a phone
     number and WhatsApp is configured — e.g. "Thanks for your order,
     confirmed for pickup."
  3. Logs a clear summary of what happened, so even without WhatsApp
     configured, the Lead + CallLog together give the business owner a
     complete picture in the dashboard.

Every step is wrapped so a failure in step 2 (e.g. WhatsApp not
configured yet) never breaks step 1 or crashes the webhook — the call
already ended, this is best-effort automation on top of it.
"""

import logging
import uuid
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.call_log import CallLog
from app.models.customer_profile import CustomerProfile
from app.core.config import settings

logger = logging.getLogger(__name__)


def run(db: Session, call_log: CallLog, company_name: str) -> None:
    """
    Entry point called right after a CallLog is saved in
    webhook_routes._handle_end_of_call. company_name is passed in for the
    WhatsApp message text rather than re-querying, since the caller
    already has the Company loaded via agent.company.
    """
    lead = _find_and_link_lead(db, call_log)
    _update_customer_profile(db, call_log, lead)
    _send_whatsapp_confirmation(lead, call_log, company_name)
    _send_email_confirmation(db, call_log, lead, company_name)


def _update_customer_profile(db: Session, call_log: CallLog, lead) -> None:
    """
    REPEAT-CALLER MEMORY: after every call, upsert this caller's
    CustomerProfile — increment their visit count and store a short
    summary of what happened. The NEXT time this phone number calls,
    action_handler._get_caller_history will find this and let the agent
    personalize its greeting.
    """
    phone = (lead.phone if lead else None) or call_log.caller_number
    if not phone:
        return

    company_id = None
    if call_log.agent and call_log.agent.company_id:
        company_id = call_log.agent.company_id
    if not company_id:
        return

    profile = db.query(CustomerProfile).filter(
        CustomerProfile.company_id == company_id, CustomerProfile.phone == phone
    ).first()

    summary = (call_log.summary or "").strip()
    if not summary and lead and lead.notes:
        summary = lead.notes.split("[call:")[0].strip()

    if profile:
        profile.visit_count = (profile.visit_count or 0) + 1
        if lead and lead.name:
            profile.name = lead.name
        if summary:
            profile.last_summary = summary[:500]
    else:
        profile = CustomerProfile(
            company_id=company_id, phone=phone,
            name=lead.name if lead else None,
            visit_count=1,
            last_summary=summary[:500] if summary else None,
        )
        db.add(profile)

    # Extract and merge structured facts (preferences, restrictions, etc.)
    # from the transcript — this is what lets the NEXT call's agent
    # actually reason over what it knows, not just read a summary.
    from app.services.memory_extraction_service import extract_facts, merge_facts
    new_facts = extract_facts(call_log.transcript or "")
    if new_facts:
        profile.structured_facts = merge_facts(profile.structured_facts, new_facts)

    db.commit()


def _find_and_link_lead(db: Session, call_log: CallLog) -> Lead | None:
    if not call_log.vapi_call_id:
        return None

    lead = (
        db.query(Lead)
        .filter(Lead.notes.like(f"%[call:{call_log.vapi_call_id}]%"))
        .first()
    )
    if lead:
        lead.call_log_id = call_log.id
        if not lead.phone and call_log.caller_number:
            lead.phone = call_log.caller_number
        db.commit()
        logger.info("Linked lead %s to call_log %s", lead.id, call_log.id)
    return lead


def _send_whatsapp_confirmation(lead: Lead | None, call_log: CallLog, company_name: str) -> None:
    phone = (lead.phone if lead else None) or call_log.caller_number
    if not phone:
        return  # nothing to message

    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.info("WhatsApp not configured — skipping confirmation message for %s", phone)
        return

    try:
        from app.services.integrations import whatsapp_service

        message = _build_confirmation_message(lead, company_name)
        whatsapp_service.send_text_message(phone, message)
        logger.info("Sent WhatsApp confirmation to %s", phone)
    except Exception:
        # Best-effort: a WhatsApp failure (e.g. outside the 24h window,
        # requiring a template) should never break call processing.
        logger.exception("Failed to send WhatsApp confirmation to %s", phone)


def _send_email_confirmation(db: Session, call_log: CallLog, lead: Lead | None, company_name: str) -> None:
    """
    Sends a real email confirmation via Gmail, using the company's
    connected Google account (same OAuth connection used for Calendar —
    no separate "connect email" step needed, since gmail.send was
    already part of the consent scope). Skips gracefully if no email
    address was captured during the call, or if Google isn't connected.
    """
    email = lead.email if lead else None
    if not email:
        return

    company_id = call_log.agent.company_id if call_log.agent else None
    if not company_id:
        return

    from app.services.integration_token_service import get_active_google_integration, get_valid_google_access_token
    from app.services.integrations import google_service

    integration = get_active_google_integration(db, company_id)
    if not integration:
        logger.info("Google not connected — skipping email confirmation for %s", email)
        return

    try:
        access_token = get_valid_google_access_token(db, integration)
        subject = f"Your confirmation from {company_name}"
        body = _build_confirmation_message(lead, company_name)
        google_service.send_mail(access_token, email, subject, body)
        logger.info("Sent email confirmation to %s", email)
    except Exception:
        # Best-effort: an email failure should never break call processing.
        logger.exception("Failed to send email confirmation to %s", email)


def _build_confirmation_message(lead: Lead | None, company_name: str) -> str:
    if lead and lead.notes and "Booking" in (lead.notes or ""):
        return f"Hi {lead.name or ''}, thanks for calling {company_name}! Your booking is confirmed. Reply here if you need to make any changes."
    if lead and lead.notes and "Order" in (lead.notes or ""):
        return f"Hi {lead.name or ''}, thanks for your order with {company_name}! We've got it and it's being prepared."
    return f"Thanks for calling {company_name}! Let us know if you have any other questions."
