"""
api/routes/integration_routes.py

WHAT THIS FILE DOES:
Handles the "Connect Google Calendar" / "Connect Outlook" buttons in the
dashboard's Settings/Integrations page. Two-step OAuth flow per provider:

  GET  /connect/{provider}   -> returns the URL to redirect the user to
  GET  /google/callback      -> Google redirects here after consent
  GET  /microsoft/callback   -> Microsoft redirects here after consent

The `state` parameter carries the company_id through the OAuth round
trip so the callback knows which company to attach the resulting tokens
to. In production, sign/encrypt `state` (e.g. a short-lived JWT) rather
than passing a raw UUID, to prevent tampering.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.integration import Integration, IntegrationProvider
from app.api.routes.company_routes import _get_owned_company_or_404
from app.services.integrations import google_service, microsoft_service

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


@router.get("/connect/google")
def connect_google(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    url = google_service.get_authorization_url(state=str(company_id))
    return {"authorization_url": url}


@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    company_id = uuid.UUID(state)
    tokens = google_service.exchange_code_for_tokens(code)

    integration = Integration(
        company_id=company_id,
        provider=IntegrationProvider.google_calendar,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_expires_at=tokens.get("expiry"),
    )
    db.add(integration)
    db.commit()
    return {"status": "connected", "provider": "google_calendar"}


@router.get("/connect/microsoft")
def connect_microsoft(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    url = microsoft_service.get_authorization_url(state=str(company_id))
    return {"authorization_url": url}


@router.get("/microsoft/callback")
def microsoft_callback(code: str, state: str, db: Session = Depends(get_db)):
    company_id = uuid.UUID(state)
    tokens = microsoft_service.exchange_code_for_tokens(code)

    integration = Integration(
        company_id=company_id,
        provider=IntegrationProvider.outlook_calendar,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
    )
    db.add(integration)
    db.commit()
    return {"status": "connected", "provider": "outlook_calendar"}


@router.get("")
def list_integrations(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    integrations = db.query(Integration).filter(Integration.company_id == company_id).all()
    return [
        {"provider": i.provider, "is_active": i.is_active, "connected_account": i.external_account_email}
        for i in integrations
    ]


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")
    _get_owned_company_or_404(db, integration.company_id, current_user.id)
    db.delete(integration)
    db.commit()
