"""
services/vapi_service.py

WHAT THIS FILE DOES:
Wraps every call to the Vapi API (https://api.vapi.ai) in one place:
create an assistant, update it, delete it, and provision a phone number.
This is the ONLY file that talks to Vapi directly — agent_routes.py
calls these functions instead of building HTTP requests inline. Keeping
third-party API calls isolated in a service module means: if you ever
swap Vapi for a different voice provider, you only rewrite this file.

All functions raise `VapiServiceError` on failure with the response body
attached, so calling code gets a clear, loggable error instead of a raw
httpx exception.
"""

import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class VapiServiceError(Exception):
    """Raised when a Vapi API call fails. Carries the response body for debugging."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.VAPI_API_KEY}",
        "Content-Type": "application/json",
    }


def create_assistant(
    name: str,
    system_prompt: str,
    first_message: str,
    voice_id: str | None = None,
    language: str = "en",
    model_provider: str = "groq",
    model_name: str = "llama-3.3-70b-versatile",
    tools: list[dict] | None = None,
) -> dict:
    """
    Creates a new Vapi assistant. Returns the full Vapi assistant object
    (includes the assistant `id` you must store on the Agent row).

    `tools` (from services/action_schemas.build_vapi_tools) is what makes
    the assistant able to actually DO things — book appointments, take
    orders, answer FAQs from the knowledge base — instead of just
    talking. Without tools, the agent can only have a conversation; it
    can never trigger our backend.
    """
    payload = {
        "name": name,
        "firstMessage": first_message,
        "model": {
            "provider": model_provider,
            "model": model_name,
            "messages": [{"role": "system", "content": system_prompt}],
            "tools": tools or [],
        },
        "voice": {
            "provider": "11labs",
            "voiceId": voice_id or "21m00Tcm4TlvDq8ikWAM",  # sensible default voice
        },
        "transcriber": {
            "provider": "deepgram",
            "language": language,
        },
    }
    if settings.VAPI_WEBHOOK_SECRET:
        # Tells Vapi to include this secret as the x-vapi-secret header on
        # every webhook it sends for this assistant — webhook_routes.py
        # verifies it matches before processing anything.
        payload["server"] = {"secret": settings.VAPI_WEBHOOK_SECRET}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.VAPI_BASE_URL}/assistant",
            headers=_headers(),
            json=payload,
        )
    if response.status_code >= 400:
        logger.error("Vapi create_assistant failed [%s]: %s", response.status_code, response.text)
        raise VapiServiceError(
            "Failed to create Vapi assistant",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()


def update_assistant(assistant_id: str, **fields) -> dict:
    """Partial update of an existing assistant (e.g. after prompt or voice changes)."""
    with httpx.Client(timeout=30.0) as client:
        response = client.patch(
            f"{settings.VAPI_BASE_URL}/assistant/{assistant_id}",
            headers=_headers(),
            json=fields,
        )
    if response.status_code >= 400:
        raise VapiServiceError(
            "Failed to update Vapi assistant",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()


def delete_assistant(assistant_id: str) -> None:
    with httpx.Client(timeout=30.0) as client:
        response = client.delete(
            f"{settings.VAPI_BASE_URL}/assistant/{assistant_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        raise VapiServiceError(
            "Failed to delete Vapi assistant",
            status_code=response.status_code,
            response_body=response.text,
        )


def provision_phone_number(assistant_id: str, area_code: str | None = None) -> dict:
    """
    Buys/attaches a phone number to an assistant via Vapi (which proxies
    Twilio under the hood). Returns the phone number object including
    `number`.
    """
    payload = {"assistantId": assistant_id}
    if area_code:
        payload["areaCode"] = area_code

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.VAPI_BASE_URL}/phone-number",
            headers=_headers(),
            json=payload,
        )
    if response.status_code >= 400:
        raise VapiServiceError(
            "Failed to provision phone number",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()


def create_outbound_call(assistant_id: str, phone_number: str, customer_name: str | None = None) -> dict:
    """
    Triggers a REAL outbound call — the agent calls OUT to phone_number
    instead of waiting for an inbound call. This is what powers cold-
    calling campaigns (services/campaign_service.py). Vapi requires a
    phone number ID (from a number you've provisioned) to place the
    call FROM — pass VAPI_OUTBOUND_PHONE_NUMBER_ID via settings, or this
    will fail with a clear error telling you to provision one first.
    """
    if not settings.VAPI_OUTBOUND_PHONE_NUMBER_ID:
        raise VapiServiceError(
            "No outbound phone number configured. Provision a phone number in "
            "your Vapi dashboard and set VAPI_OUTBOUND_PHONE_NUMBER_ID in .env."
        )

    payload = {
        "assistantId": assistant_id,
        "phoneNumberId": settings.VAPI_OUTBOUND_PHONE_NUMBER_ID,
        "customer": {"number": phone_number},
    }
    if customer_name:
        payload["customer"]["name"] = customer_name

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.VAPI_BASE_URL}/call",
            headers=_headers(),
            json=payload,
        )
    if response.status_code >= 400:
        raise VapiServiceError(
            "Failed to place outbound call",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()


def get_call(call_id: str) -> dict:
    """Fetches call details/transcript from Vapi (used as a fallback if a webhook is missed)."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{settings.VAPI_BASE_URL}/call/{call_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        raise VapiServiceError(
            "Failed to fetch call",
            status_code=response.status_code,
            response_body=response.text,
        )
    return response.json()
