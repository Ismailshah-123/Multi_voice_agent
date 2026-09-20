"""
services/rag_generation_service.py

WHAT THIS FILE DOES:
This is the fix for RAG returning raw pasted document text instead of a
real answer. Proper RAG is "Retrieval-Augmented GENERATION" — retrieve
relevant chunks (rag_service.query already does this well), then GENERATE
a clean, natural, concise answer from them using an LLM. The previous
version skipped the generation step entirely and just concatenated raw
chunk text — which is why answers looked like a pasted half-page of a
PDF instead of a real response.

This uses Groq (same free model already running live calls) to turn
retrieved chunks into a proper, concise, natural-sounding answer to the
caller's specific question.
"""

import logging
from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

GENERATION_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_PROMPT = """You are answering a customer's question using ONLY the provided context from a \
business's internal documents. Give a natural, concise, conversational answer — the way a helpful \
human receptionist would say it out loud on the phone, NOT a copy-pasted excerpt. Keep it to 1-3 \
sentences unless the question genuinely requires more detail (like listing multiple prices). If the \
context doesn't actually contain the answer, say so honestly rather than making something up — \
suggest the caller can be connected to someone who can help further."""


def generate_answer(question: str, context_chunks: list[str]) -> str:
    """
    Turns retrieved document chunks into a real, natural-sounding
    answer to `question`. Falls back to a short excerpt (not the full
    800-char paste) if Groq is unavailable, so this never breaks a live
    call even if generation fails.
    """
    if not context_chunks:
        return "I don't have that information available right now, but I can have someone follow up with you."

    context = "\n\n".join(context_chunks)

    if not settings.GROQ_API_KEY:
        # Graceful degrade: short excerpt instead of raw dump, and instead
        # of silently returning nothing.
        return context_chunks[0][:200]

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nCustomer's question: {question}"},
            ],
            temperature=0.3,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("RAG answer generation failed — falling back to a short excerpt.")
        return context_chunks[0][:200]