"""
services/preview_chat_service.py

WHAT THIS FILE DOES:
Lets a business owner test how their agent actually talks BEFORE going
live with real phone calls — using the exact same system prompt that
was deployed to Vapi, but as a free text chat via Groq directly. This
costs zero Vapi minutes (text chat, not voice) and zero extra cost
beyond Groq's free tier, so owners can iterate on their agent's
behavior/tone freely before spending real call credit.

NOTE: this tests CONVERSATION QUALITY (does it sound right, does it ask
the right questions, does it stay in character) but does NOT trigger
real tool actions (booking, RAG lookups) — those only fire through
Vapi's actual function-calling during a real voice call. This is
intentional: it's a fast, free way to sanity-check the agent's prompt
and tone, not a full simulation of a live call.
"""

from groq import Groq
from app.core.config import settings

CHAT_MODEL = "llama-3.3-70b-versatile"


def send_preview_message(system_prompt: str, conversation_history: list[dict], new_message: str) -> str:
    """
    conversation_history: list of {"role": "user"|"assistant", "content": str}
    Returns the agent's reply as plain text.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set — required to test the agent.")

    client = Groq(api_key=settings.GROQ_API_KEY)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": new_message})

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    )
    return response.choices[0].message.content
