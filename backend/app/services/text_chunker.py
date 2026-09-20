"""
services/text_chunker.py

WHAT THIS FILE DOES:
Splits raw extracted text into overlapping chunks small enough to embed
and retrieve accurately. A whole PDF as one embedding is useless for
retrieval (too broad, dilutes similarity search) — chunking is what
makes RAG actually find the specific paragraph that answers a question.

Uses a simple, dependency-free sliding-window chunker on words rather
than tokens, which is good enough for this use case and avoids pulling
in a tokenizer dependency. Overlap between chunks prevents an answer
from being split across a chunk boundary and lost.
"""


def chunk_text(text: str, chunk_size: int = 220, overlap: int = 40) -> list[str]:
    """
    chunk_size / overlap are in words, not characters or tokens.
    ~220 words is roughly 250-300 tokens, a good size for retrieval
    precision without losing surrounding context.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        if end >= len(words):
            break
        start = end - overlap  # step back by `overlap` words so context isn't lost at the boundary

    return chunks
