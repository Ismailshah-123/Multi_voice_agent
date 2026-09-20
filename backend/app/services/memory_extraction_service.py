"""
services/memory_extraction_service.py

WHAT THIS FILE DOES:
This is what makes customer memory actually STRUCTURED instead of just a
paragraph the next agent has to re-read and hope it parses correctly.
After a call ends, this calls Groq to read the transcript and extract
concrete facts as JSON — preferred appointment times, dietary
restrictions, budget range, past order items, whatever's relevant to
that conversation. These facts get merged into the customer's
CustomerProfile.structured_facts and handed directly to the agent on
their NEXT call via action_handler._get_caller_history, so the agent can
actually reason over them ("their notes say they're vegetarian, don't
recommend the chicken dish") instead of just reading back a summary.

Free — uses the same Groq model already running the live calls, just a
second short call after the conversation ends.
"""

import json
import logging
from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_INSTRUCTIONS = """You extract useful customer facts from a call transcript for a business's \
CRM memory. Read the transcript and return ONLY a JSON object of concrete, reusable facts about this \
customer — things worth remembering for their NEXT call. Examples of good facts: preferred appointment \
times, dietary restrictions or allergies, favorite products/services, budget range, special requests, \
communication preferences. Do NOT include one-time transactional details like a specific date for a \
one-off booking unless it reveals a pattern (e.g. "always books Friday evenings" is useful, "booked for \
March 3rd" is not). If nothing durable/reusable was mentioned, return an empty JSON object {}. \
Respond with ONLY the JSON object, no markdown fences, no explanation."""


def extract_facts(transcript: str) -> dict:
    """
    Returns a dict of extracted facts, or {} if extraction fails or
    finds nothing durable. Never raises — a failure here should never
    break call processing, since this runs inside the best-effort
    post-call workflow.
    """
    if not transcript or not transcript.strip():
        return {}
    if not settings.GROQ_API_KEY:
        return {}

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": f"Transcript:\n{transcript[:4000]}"},  # cap length, transcripts can be long
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        facts = json.loads(raw)
        return facts if isinstance(facts, dict) else {}
    except Exception:
        logger.exception("Memory fact extraction failed — continuing without structured facts.")
        return {}


def merge_facts(existing: dict | None, new_facts: dict) -> dict:
    """
    Merges newly extracted facts into the existing profile, with new
    facts overwriting old ones for the same key (most recent call wins
    for anything that changed) while preserving keys not mentioned in
    this call.
    """
    merged = dict(existing or {})
    merged.update({k: v for k, v in new_facts.items() if v})
    return merged
