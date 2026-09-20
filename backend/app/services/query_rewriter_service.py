"""
services/query_rewriter_service.py

WHAT THIS FILE DOES:
This is what makes RAG work correctly across a REAL multi-turn phone
conversation, not just single isolated questions. Without this, a
follow-up like "what about for kids?" gets searched literally — and
finds nothing useful, because the knowledge base doesn't contain the
words "what about for kids." It needs to be understood as "what is the
pediatric checkup service and pricing?" using the conversation so far.

Uses Groq (free, same model already running calls) to rewrite the
caller's latest question into a standalone, retrieval-optimized query
BEFORE it hits the hybrid search pipeline. This runs as a fast, cheap
pre-step — one short Groq call, then the existing hybrid search +
rerank + cache pipeline runs exactly as before on the rewritten query.

Falls back to the original, un-rewritten question if anything fails —
this is a quality improvement, never a hard dependency that could break
a live call.
"""

import logging
from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

REWRITE_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_PROMPT = """You rewrite a customer's latest question into a standalone, clear search query, \
using the conversation so far for context. The rewritten query will be used to search a business's \
documents — it should contain the actual topic being asked about, not vague pronouns or references. \
If the question is already standalone and clear, return it unchanged. Respond with ONLY the rewritten \
query text, nothing else — no explanation, no quotes."""


def rewrite_query(question: str, conversation_context: str = "") -> str:
    """
    Rewrites `question` into a standalone search query using
    `conversation_context` (recent transcript text) if provided.
    Returns the original question unchanged if there's no context to
    use, if Groq isn't configured, or if the rewrite call fails for
    any reason.
    """
    if not conversation_context.strip() or not settings.GROQ_API_KEY:
        return question

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=REWRITE_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Conversation so far:\n{conversation_context[-1500:]}\n\nLatest question: {question}",
                },
            ],
            temperature=0.1,
            max_tokens=60,
        )
        rewritten = response.choices[0].message.content.strip()
        return rewritten if rewritten else question
    except Exception:
        logger.exception("Query rewriting failed — using original question instead.")
        return question