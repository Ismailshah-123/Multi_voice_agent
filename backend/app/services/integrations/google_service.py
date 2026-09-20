"""
services/integrations/google_service.py

WHAT THIS FILE DOES:
Handles the Google OAuth flow (Gmail + Google Calendar) and the actual
API calls once connected: creating calendar events (used by
action_handler._book_appointment), and sending emails via Gmail.

SETUP REQUIRED before this works:
  1. Create a project in Google Cloud Console.
  2. Enable the Gmail API and Google Calendar API.
  3. Create OAuth 2.0 credentials (Web application type).
  4. Add GOOGLE_REDIRECT_URI (from .env) as an authorized redirect URI.
  5. Put the client ID/secret in your .env file.
  6. Submit for OAuth consent screen verification before going to
     production with real users outside your test user list — Google
     requires this for sensitive scopes like gmail.send and calendar.

This file gives you the working code shape; the actual credentials must
be supplied by you via .env before any of this runs successfully.
"""

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
from app.core.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def get_authorization_url(state: str) -> str:
    """Step 1 of OAuth: returns the URL to redirect the business owner to."""
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",       # required to get a refresh_token
        include_granted_scopes="true",
        prompt="consent",
        state=state,                  # pass company_id here so the callback knows who's connecting
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> dict:
    """Step 2 of OAuth: exchanges the auth code from the callback for tokens."""
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry,
    }


def refresh_access_token(refresh_token: str) -> dict:
    """
    Google access tokens expire after ~1 hour. Call this to get a fresh
    one using the stored refresh_token (which does not expire unless
    revoked). Used by action_handler before every calendar API call to
    avoid failing mid-call on an expired token.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(GoogleAuthRequest())
    return {"access_token": creds.token, "expiry": creds.expiry}


def delete_calendar_event(access_token: str, event_id: str) -> None:
    """Deletes a specific Google Calendar event by ID. Used by action_handler for real cancellation."""
    creds = Credentials(
        token=access_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    service = build("calendar", "v3", credentials=creds)
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def send_mail(access_token: str, to_email: str, subject: str, body_text: str) -> dict:
    """
    Sends an email via Gmail API, using the SAME access token already
    obtained for Calendar access — the OAuth consent screen (see SCOPES
    above) already requests gmail.send, so no separate connection step
    is needed. This is what post_call_workflow.py calls to send booking/
    order confirmations by email after a call ends.
    """
    import base64
    from email.mime.text import MIMEText

    creds = Credentials(token=access_token, token_uri="https://oauth2.googleapis.com/token")
    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(body_text)
    message["to"] = to_email
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def create_calendar_event(access_token: str, refresh_token: str, summary: str, start_iso: str, end_iso: str, attendee_email: str | None = None) -> dict:
    """Creates a Google Calendar event. Used by action_handler for book_appointment."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    service = build("calendar", "v3", credentials=creds)

    event_body = {
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]

    return service.events().insert(calendarId="primary", body=event_body).execute()


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=settings.GOOGLE_REDIRECT_URI)
