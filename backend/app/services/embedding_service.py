"""
services/embedding_service.py

WHAT THIS FILE DOES:
Converts text chunks into vector embeddings so they can be stored in
Qdrant and searched by semantic similarity.

Uses a LOCAL, FREE embedding model (BAAI/bge-small-en-v1.5) via
sentence-transformers — runs entirely on your own machine/server, no API
key, no per-call cost, no OpenAI dependency. This is a real,
industry-used model (BGE models are a standard benchmark-leading choice
for retrieval, not a toy) — the accuracy tradeoff vs OpenAI's
text-embedding-3-small is small, and for a voice agent answering from a
menu/FAQ/policy document, it's more than accurate enough.

The model downloads once (~130MB) the first time this runs, then is
cached locally (~/.cache/huggingface) — after that, zero network calls,
zero cost, works offline.

If you ever want to swap in a different embedding provider (OpenAI,
Cohere, a bigger local model), this is the ONLY file that needs to
change — rag_service.py only calls embed_texts/embed_query.
"""

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384  # bge-small's native output size

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # First call downloads the model (~130MB) and caches it locally.
        # Every call after that (including across restarts) loads from
        # local disk cache — no network, no cost, no API key needed.
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embeds a batch of text chunks. Returns a list of vectors in the same
    order as the input texts. bge models recommend no special prefix for
    the documents being indexed (only queries get a prefix — see
    embed_query below), so chunks are embedded as-is.
    """
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    """
    Embeds a single query string. BGE models are trained to expect a
    specific instruction prefix on QUERIES (not on the documents being
    searched) for best retrieval accuracy — this is a documented BGE
    convention, not an arbitrary choice.
    """
    model = _get_model()
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    vector = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return vector.tolist()
