"""
services/reranker_service.py

WHAT THIS FILE DOES:
Adds a second, more precise scoring pass on top of hybrid search
results using a free, local cross-encoder model.

IMPORTANT FIX: the entire rerank attempt (both model loading AND the
actual model.predict() call) is now wrapped in try/except. Previously
only model loading was protected — but on some torch/transformers
version combinations, the crash happens later, inside predict() itself
(a known "Cannot copy out of meta tensor" issue with certain
transformers versions). That crash was unhandled and took down the
entire request with a 500 error. Now ANY failure in reranking falls
back gracefully to the hybrid-search order instead — reranking is a
quality improvement, not a hard dependency, and should never be able to
break a live call or a knowledge base query.
"""

import logging
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None
_reranker_broken = False  # once we see it fail, stop retrying every call - just use hybrid order


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME)
    return _model


def rerank(question: str, candidates: list[dict], top_k: int = 4) -> list[dict]:
    """
    Takes the candidate chunks from hybrid search and re-sorts them by
    true relevance to `question`. Returns the top_k best.

    Falls back to the original hybrid-search order (unchanged) if
    ANYTHING goes wrong — model download failure, no network, or a
    torch/transformers version incompatibility on this machine. Once a
    failure is seen, skips retrying the model for the rest of this
    process's lifetime, so a broken environment doesn't add repeated
    delay to every single query.
    """
    global _reranker_broken

    if not candidates:
        return []

    if _reranker_broken:
        return candidates[:top_k]

    try:
        model = _get_model()
        pairs = [[question, c["text"]] for c in candidates if c.get("text")]
        if not pairs:
            return candidates[:top_k]

        scores = model.predict(pairs)

        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for candidate, score in scored[:top_k]:
            enriched = dict(candidate)
            enriched["rerank_score"] = round(float(score), 4)
            results.append(enriched)
        return results

    except Exception:
        logger.exception(
            "Cross-encoder reranking failed (likely a torch/transformers version "
            "issue on this machine) - falling back to hybrid search order for the "
            "rest of this session. Results will still be relevant, just not "
            "re-ranked for maximum precision."
        )
        _reranker_broken = True
        return candidates[:top_k]