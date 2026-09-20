"""
services/integration_token_service.py

WHAT THIS FILE DOES:
A single shared place to get a valid (non-expired) Google access token
for a company's connected integration, refreshing it if needed and
persisting the refreshed token back to the database. Both
action_handler.py (calendar booking) and post_call_workflow.py (email
confirmations) call this instead of each having their own copy of the
refresh logic — one integration, one token, reused for both Calendar
and Gmail since they share the same OAuth connection (see SCOPES in
google_service.py).
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.models.integration import Integration, IntegrationProvider
from app.services.integrations import google_service


def get_active_google_integration(db: Session, company_id) -> Integration | None:
    return (
        db.query(Integration)
        .filter(
            Integration.company_id == company_id,
            Integration.provider == IntegrationProvider.google_calendar,
            Integration.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_valid_google_access_token(db: Session, integration: Integration) -> str:
    """
    Returns a usable access token, refreshing it first if expired or
    about to expire within 2 minutes. Persists the refreshed token back
    to the DB so we don't refresh on every single call.
    """
    now = datetime.now(timezone.utc)
    expires_at = integration.token_expires_at
    is_expired = expires_at is not None and expires_at.replace(tzinfo=timezone.utc) <= now + timedelta(minutes=2)

    if is_expired or not integration.access_token:
        refreshed = google_service.refresh_access_token(integration.refresh_token)
        integration.access_token = refreshed["access_token"]
        integration.token_expires_at = refreshed.get("expiry")
        db.commit()

    return integration.access_token
