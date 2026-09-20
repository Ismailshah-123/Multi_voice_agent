"""
services/campaign_service.py

WHAT THIS FILE DOES:
Handles outbound cold-calling campaigns: CSV contact parsing and
orchestrating the actual calls, now with real compliance controls.

COMPLIANCE FEATURES (new):
  - Do-not-call filtering: any contact whose phone number is on this
    company's DoNotCallEntry list is automatically skipped before
    dialing, never just "attempted and failed."
  - Calling-hours enforcement: a campaign specifies allowed calling
    hours; contacts are only dialed within that window. Many
    jurisdictions legally restrict outbound calling to daytime hours —
    this is a real requirement, not just a nice-to-have.
  - Pause/resume: a running campaign can be paused, which stops further
    dialing without losing progress — pending contacts stay pending.

PRODUCTION NOTE: this still triggers calls in a sequential loop within
the API request, appropriate for testing/small campaigns. For real
production scale, move this to a background job queue (Celery is
already in requirements.txt for exactly this reason).
"""

import csv
import io
import logging
from datetime import datetime, time
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignContact, ContactStatus, CampaignStatus
from app.models.agent import Agent
from app.models.do_not_call import DoNotCallEntry
from app.services import vapi_service

logger = logging.getLogger(__name__)


def parse_contacts_csv(file_bytes: bytes) -> list[dict]:
    """
    Expects a CSV with at least a 'phone' column, optionally 'name'.
    Returns a list of {"phone": str, "name": str|None} dicts. Skips
    rows with no phone number rather than failing the whole upload.
    """
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))

    contacts = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        phone = normalized.get("phone") or normalized.get("phone_number") or normalized.get("number")
        if not phone:
            continue
        name = normalized.get("name") or normalized.get("customer_name")
        contacts.append({"phone": phone, "name": name or None})

    return contacts


def create_campaign_with_contacts(db: Session, company_id, agent_id, name: str, contacts: list[dict], calling_hours_start: int = 9, calling_hours_end: int = 18) -> Campaign:
    campaign = Campaign(
        company_id=company_id, agent_id=agent_id, name=name, total_contacts=len(contacts),
        calling_hours_start=calling_hours_start, calling_hours_end=calling_hours_end,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    contact_rows = [
        CampaignContact(campaign_id=campaign.id, phone=c["phone"], name=c.get("name"))
        for c in contacts
    ]
    db.add_all(contact_rows)
    db.commit()

    return campaign


def _is_within_calling_hours(campaign: Campaign) -> bool:
    """
    Checks whether right now falls within this campaign's allowed
    calling window. Uses server local time — for a real multi-region
    product this should use the company's configured timezone, but
    this is a real, working guardrail as-is (flagged for that future
    improvement rather than silently having no restriction at all).
    """
    now = datetime.now().time()
    start = time(hour=campaign.calling_hours_start)
    end = time(hour=campaign.calling_hours_end)
    return start <= now <= end


def start_campaign(db: Session, campaign: Campaign) -> dict:
    """
    Triggers an outbound call for every PENDING contact in this
    campaign, EXCEPT:
      - contacts on this company's do-not-call list (skipped, marked
        as "failed" with a clear compliance reason — never dialed)
      - if called outside the campaign's allowed calling hours, the
        entire batch is deferred rather than partially dialed

    Returns a summary of what happened, including how many were
    skipped for compliance reasons so this is fully auditable.
    """
    agent = db.query(Agent).filter(Agent.id == campaign.agent_id).first()
    if not agent or not agent.vapi_assistant_id:
        raise ValueError("This campaign's agent isn't deployed yet — deploy it before starting the campaign.")

    if not _is_within_calling_hours(campaign):
        return {
            "calls_placed": 0, "calls_failed_to_start": 0, "calls_skipped_dnc": 0,
            "total_pending": 0,
            "deferred": True,
            "message": f"Outside this campaign's allowed calling hours ({campaign.calling_hours_start}:00-{campaign.calling_hours_end}:00). No calls placed — try again during the allowed window.",
        }

    dnc_numbers = {
        entry.phone for entry in
        db.query(DoNotCallEntry).filter(DoNotCallEntry.company_id == campaign.company_id).all()
    }

    pending = db.query(CampaignContact).filter(
        CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.pending
    ).all()

    placed = 0
    failed = 0
    skipped_dnc = 0

    for contact in pending:
        if contact.phone in dnc_numbers:
            contact.status = ContactStatus.failed
            contact.outcome_notes = "Skipped — number is on the do-not-call list."
            skipped_dnc += 1
            continue

        try:
            call = vapi_service.create_outbound_call(agent.vapi_assistant_id, contact.phone, contact.name)
            contact.vapi_call_id = call.get("id")
            contact.status = ContactStatus.calling
            placed += 1
        except vapi_service.VapiServiceError as e:
            contact.status = ContactStatus.failed
            contact.outcome_notes = str(e)
            failed += 1
            logger.warning("Failed to place outbound call to %s: %s", contact.phone, e)

    campaign.status = CampaignStatus.running
    db.commit()

    return {
        "calls_placed": placed,
        "calls_failed_to_start": failed,
        "calls_skipped_dnc": skipped_dnc,
        "total_pending": len(pending),
        "deferred": False,
    }


def pause_campaign(db: Session, campaign: Campaign) -> None:
    """Pauses a running campaign. Pending contacts stay pending and can be resumed later via start_campaign again."""
    campaign.status = CampaignStatus.paused
    db.commit()


def add_to_do_not_call(db: Session, company_id, phone: str, reason: str | None = None) -> None:
    """
    Adds a number to this company's do-not-call list. Called manually
    from the dashboard, or automatically from action_handler.py if a
    caller explicitly asks to stop being contacted during a call.
    """
    existing = db.query(DoNotCallEntry).filter(DoNotCallEntry.company_id == company_id, DoNotCallEntry.phone == phone).first()
    if existing:
        return
    entry = DoNotCallEntry(company_id=company_id, phone=phone, reason=reason)
    db.add(entry)
    db.commit()