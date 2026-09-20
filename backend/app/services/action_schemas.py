"""
services/action_schemas.py

WHAT THIS FILE DOES:
Defines the JSON-schema "tools" that get attached to a Vapi assistant so
the LLM actually knows it CAN call book_appointment, take_order, etc,
and what parameters to collect from the caller before calling it.

IMPORTANT: Vapi's tool-parameter validator rejects a "description" key
anywhere inside the parameters schema (on individual properties, or on
the schema object itself) — it returns "description should not exist".
The human-readable description belongs ONLY at the top level of each
tool (the "description" field passed alongside "parameters" in
build_vapi_tools below, which becomes function.description) — never
inside the parameters/properties themselves. This file intentionally
has ZERO "description" keys inside any _SCHEMA dict below.
"""

_BOOKING_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {"type": "string"},
        "start_datetime": {"type": "string"},
        "end_datetime": {"type": "string"},
        "reason": {"type": "string"},
        "contact_email": {"type": "string"},
    },
    "required": ["customer_name", "start_datetime"],
}

_CANCEL_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {"type": "string"},
        "original_datetime": {"type": "string"},
    },
    "required": ["customer_name"],
}

_ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "string"}},
        "customer_name": {"type": "string"},
        "delivery_or_pickup": {"type": "string", "enum": ["delivery", "pickup"]},
    },
    "required": ["items"],
}

_FAQ_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
    },
    "required": ["question"],
}

_LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {"type": "string"},
        "contact_email": {"type": "string"},
        "contact_phone": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["customer_name"],
}

_HISTORY_LOOKUP_SCHEMA = {
    "type": "object",
    "properties": {},
}

# action name -> (description shown to the LLM, parameter schema)
# NOTE: "description" here is the TOOL-level description (goes into
# function.description) — this is fine and required. It is NOT inside
# the parameters schema, so it does not trigger Vapi's validation error.
ACTION_SCHEMAS: dict[str, dict] = {
    "get_caller_history": {
        "description": "Call this AT THE START of the conversation, before your first substantive response, to check if this caller has contacted us before. Use the result to personalize your greeting for returning callers.",
        "parameters": _HISTORY_LOOKUP_SCHEMA,
    },
    "book_appointment": {"description": "Book an appointment or reservation for the caller.", "parameters": _BOOKING_SCHEMA},
    "reschedule_appointment": {"description": "Reschedule an existing appointment to a new time.", "parameters": _BOOKING_SCHEMA},
    "schedule_visit": {"description": "Schedule a property visit.", "parameters": _BOOKING_SCHEMA},
    "schedule_meeting": {"description": "Schedule a consultation meeting.", "parameters": _BOOKING_SCHEMA},
    "schedule_interview": {"description": "Schedule a candidate interview.", "parameters": _BOOKING_SCHEMA},
    "book_room": {"description": "Book a hotel room.", "parameters": _BOOKING_SCHEMA},
    "book_personal_trainer": {"description": "Book a personal training session.", "parameters": _BOOKING_SCHEMA},
    "reserve_table": {"description": "Reserve a table at the restaurant.", "parameters": _BOOKING_SCHEMA},
    "book_followup_call": {"description": "Schedule a follow-up sales call.", "parameters": _BOOKING_SCHEMA},

    "cancel_appointment": {"description": "Cancel an existing appointment.", "parameters": _CANCEL_SCHEMA},
    "cancel_order": {"description": "Cancel an existing order.", "parameters": _CANCEL_SCHEMA},

    "take_order": {"description": "Record a food order from the caller.", "parameters": _ORDER_SCHEMA},

    "track_order": {"description": "Look up the status of an existing order.", "parameters": _CANCEL_SCHEMA},
    "track_delivery": {"description": "Look up delivery status.", "parameters": _CANCEL_SCHEMA},

    "create_crm_lead": {"description": "Log this caller as a new sales lead.", "parameters": _LEAD_SCHEMA},
    "qualify_lead": {"description": "Log this caller as a qualified sales lead.", "parameters": _LEAD_SCHEMA},

    "menu_faq": {"description": "Answer a menu-related question from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "insurance_faq": {"description": "Answer an insurance-related question from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "legal_faq": {"description": "Answer a general legal-process question from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "mortgage_faq": {"description": "Answer a general mortgage question from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "pricing_faq": {"description": "Answer a pricing question from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "tooth_pain_guide": {"description": "Give general first-response guidance for tooth pain from the knowledge base.", "parameters": _FAQ_SCHEMA},
    "emergency_routing": {"description": "Detect and route a medical/dental emergency.", "parameters": _FAQ_SCHEMA},
}


def infer_schema_for_action(action_name: str) -> dict:
    """
    Fallback for action names that AREN'T in ACTION_SCHEMAS — this
    happens for custom/AI-generated agents where Groq invents action
    names on the fly for a business type outside the presets. Guesses
    the right shape from keywords in the name.
    """
    name_lower = action_name.lower()
    if any(k in name_lower for k in ["book", "schedule", "reserve", "appointment"]):
        return {"description": action_name.replace("_", " ").capitalize() + ".", "parameters": _BOOKING_SCHEMA}
    if any(k in name_lower for k in ["cancel", "track", "status"]):
        return {"description": action_name.replace("_", " ").capitalize() + ".", "parameters": _CANCEL_SCHEMA}
    if any(k in name_lower for k in ["order", "purchase", "buy"]):
        return {"description": action_name.replace("_", " ").capitalize() + ".", "parameters": _ORDER_SCHEMA}
    if any(k in name_lower for k in ["lead", "contact", "qualify", "collect"]):
        return {"description": action_name.replace("_", " ").capitalize() + ".", "parameters": _LEAD_SCHEMA}
    return {"description": action_name.replace("_", " ").capitalize() + ".", "parameters": _FAQ_SCHEMA}


def build_transfer_tool(escalation_phone_number: str) -> dict:
    """
    HUMAN HANDOFF. Uses Vapi's NATIVE "transferCall" tool type — Vapi
    handles the actual call transfer itself, no webhook round-trip
    needed. Only added to an agent's tools if the company has set an
    escalation_phone_number.
    """
    return {
        "type": "transferCall",
        "destinations": [{"type": "number", "number": escalation_phone_number}],
        "function": {
            "name": "transfer_to_human",
            "description": (
                "Transfer this call to a human team member. Use this if you cannot help the caller, "
                "if they explicitly ask to speak to a person, or if they seem frustrated or upset after "
                "you've tried to help. Always let the caller know you're transferring them before doing so."
            ),
        },
    }


def build_vapi_tools(enabled_actions: list[str], server_url: str, escalation_phone_number: str | None = None) -> list[dict]:
    """
    Converts this agent's enabled_actions into Vapi's tool-definition
    format, each pointing at our webhook endpoint. Actions not found in
    ACTION_SCHEMAS get a sensible inferred schema instead of being
    skipped, so custom agents are fully functional too.
    """
    tools = []
    for action_name in enabled_actions:
        schema = ACTION_SCHEMAS.get(action_name) or infer_schema_for_action(action_name)
        tools.append({
            "type": "function",
            "function": {
                "name": action_name,
                "description": schema["description"],
                "parameters": schema["parameters"],
            },
            "server": {"url": server_url},
        })

    if escalation_phone_number:
        tools.append(build_transfer_tool(escalation_phone_number))

    return tools