"""
services/integrations/microsoft_service.py

WHAT THIS FILE DOES:
Handles Microsoft OAuth (Outlook Mail + Outlook/Microsoft 365 Calendar)
using MSAL, and calls the Microsoft Graph API to create calendar events
and send mail once a company connects their account.

SETUP REQUIRED before this works:
  1. Register an app in Azure Portal -> App registrations.
  2. Add MICROSOFT_REDIRECT_URI as a redirect URI (Web platform).
  3. Add API permissions: Calendars.ReadWrite, Mail.Send (delegated).
  4. Put client ID/secret in .env.
  5. For production use outside your org, the app must go through
     Microsoft's publisher verification / admin consent depending on
     the permissions requested.
"""

import msal
import httpx
from app.core.config import settings

SCOPES = ["Calendars.ReadWrite", "Mail.Send", "User.Read"]
AUTHORITY = "https://login.microsoftonline.com/common"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        authority=AUTHORITY,
    )


def get_authorization_url(state: str) -> str:
    app = _msal_app()
    return app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        state=state,
    )


def exchange_code_for_tokens(code: str) -> dict:
    app = _msal_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    )
    if "access_token" not in result:
        raise RuntimeError(f"Microsoft OAuth failed: {result.get('error_description')}")
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
    }


def create_calendar_event(access_token: str, subject: str, start_iso: str, end_iso: str, timezone: str = "UTC", attendee_email: str | None = None) -> dict:
    """Creates an Outlook Calendar event via Microsoft Graph. Used by action_handler."""
    body = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    if attendee_email:
        body["attendees"] = [{"emailAddress": {"address": attendee_email}, "type": "required"}]

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{GRAPH_BASE}/me/events",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=body,
        )
    response.raise_for_status()
    return response.json()


def send_mail(access_token: str, to_email: str, subject: str, body_text: str) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        }
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{GRAPH_BASE}/me/sendMail",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
