"""
services/ai_prompt_generator.py

WHAT THIS FILE DOES:
This is what makes the platform truly support ANY business, not just
the 11 preset industries. Instead of picking from a fixed dropdown, the
business owner describes their business in plain English (e.g. "We're a
mobile dog grooming service, we come to people's homes, book by the
hour"), and this file calls Groq's chat API to generate a tailored
system prompt, greeting, and suggested actions — the same "AI Prompt
Builder" concept from the original product spec, just implemented for
real.

This is the difference between "a platform with 11 industries" and "a
platform that can become ANY industry" — which is what actually makes
it sellable as a general-purpose SaaS instead of a vertical tool.

Uses Groq (not OpenAI) for this generation step specifically because
it's free/cheap and it's the same model family already running the
live calls — consistent voice and behavior between prompt generation
and the actual agent.
"""

import json
import logging
from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

GENERATOR_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_INSTRUCTIONS = """You are an expert AI voice agent prompt engineer. Given a business \
description, generate a complete voice agent configuration as JSON. Respond with ONLY valid JSON, \
no markdown fences, no preamble, matching this exact schema:

{
  "system_prompt": "A complete system prompt for the voice AI, written in second person ('You are the AI assistant for {company_name}...'), covering: how to greet callers, what tasks it should help with, what tone to use, and any important limitations (e.g. never give legal/medical advice if relevant). 150-250 words.",
  "greeting": "A short, natural first sentence the agent says when answering, mentioning the company name.",
  "suggested_actions": ["action_name_1", "action_name_2", "..."],
  "suggested_kb_categories": ["category_1", "category_2", "..."]
}

Action names must be short snake_case identifiers describing a concrete task (e.g. book_appointment, \
take_order, check_availability, answer_pricing_question, collect_contact_info). Suggest 3-6 actions \
that make sense for this specific business. Suggested KB categories are types of documents this \
business should upload (e.g. price_list, service_area, policies)."""


def generate_agent_config(company_name: str, business_description: str) -> dict:
    """
    Calls Groq to generate a full agent configuration for a business type
    that doesn't fit any preset industry template. Returns a dict with
    system_prompt, greeting, suggested_actions, suggested_kb_categories.

    Raises RuntimeError if GROQ_API_KEY isn't configured or the model
    doesn't return valid JSON — callers should catch this and fall back
    to a generic template rather than deploying a broken agent.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set — required to generate a custom agent prompt.")

    client = Groq(api_key=settings.GROQ_API_KEY)

    user_message = (
        f"Business name: {company_name}\n"
        f"Business description: {business_description}\n\n"
        "Generate the voice agent configuration JSON now."
    )

    response = client.chat.completions.create(
        model=GENERATOR_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Groq returned invalid JSON for prompt generation: %s", raw)
        raise RuntimeError(f"AI prompt generation returned invalid JSON: {e}")

    required_keys = {"system_prompt", "greeting", "suggested_actions", "suggested_kb_categories"}
    missing = required_keys - config.keys()
    if missing:
        raise RuntimeError(f"AI-generated config is missing required fields: {missing}")

    return config
