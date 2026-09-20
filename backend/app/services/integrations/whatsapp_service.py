"""
services/integrations/whatsapp_service.py

WHAT THIS FILE DOES:
Sends WhatsApp messages via the WhatsApp Business Cloud API (Meta) —
used to send booking confirmations, order confirmations, and reminders
after a call ends (part of the post-call Workflow Automation:
Transcript -> Summary -> CRM Update -> Email -> Schedule -> Send
WhatsApp confirmation).

SETUP REQUIRED before this works:
  1. Create a Meta Developer app with the WhatsApp product added.
  2. Get a permanent access token (System User token, not the 24h test
     token) and a verified phone number ID.
  3. Put WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env.
  4. For sending outside the 24-hour customer service window, you must
     use pre-approved Message Templates (Meta requirement) — plain text
     only works within 24h of the customer's last message to you.
"""

import httpx
from app.core.config import settings

GRAPH_BASE = "https://graph.facebook.com/v21.0"


def send_text_message(to_phone_number: str, message: str) -> dict:
    """
    Sends a free-form text message. Only works within the 24-hour
    customer service window (WhatsApp policy). For confirmations sent
    outside that window, use send_template_message instead.
    """
    url = f"{GRAPH_BASE}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "text",
        "text": {"body": message},
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
            json=payload,
        )
    response.raise_for_status()
    return response.json()


def send_template_message(to_phone_number: str, template_name: str, language_code: str = "en_US", parameters: list[str] | None = None) -> dict:
    """
    Sends a pre-approved Message Template — required for the first
    outbound message or anything sent >24h after the customer last
    messaged. Template must already be approved in Meta Business Manager.
    """
    components = []
    if parameters:
        components = [{
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in parameters],
        }]

    url = f"{GRAPH_BASE}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
            json=payload,
        )
    response.raise_for_status()
    return response.json()
