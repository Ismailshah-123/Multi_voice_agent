"""
services/knowledge_gap_service.py

WHAT THIS FILE DOES:
Logs every question the RAG pipeline couldn't confidently answer. Uses
EMBEDDING-based semantic similarity (same free local model and same
cosine-similarity approach already used by rag_service.py's semantic
cache) to group near-duplicate questions together — "how much is
whitening" and "what's the cost of whitening" correctly group as the
same underlying gap, even though they share very few exact words.

NOTE: an earlier version of this file used character-level string
matching (difflib.SequenceMatcher), which was tested and found to
badly under-group real paraphrases (e.g. scored those two questions as
only 56% similar despite being the same question). Switched to
embedding similarity for accuracy, consistent with how the rest of the
RAG pipeline already works.
"""

import logging
import math
from sqlalchemy.orm import Session

from app.models.unanswered_question import UnansweredQuestion
from app.services.embedding_service import embed_query

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.88  # cosine similarity, 0-1 scale - tuned for embedding vectors, not character overlap


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def log_unanswered_question(db: Session, company_id, question: str) -> None:
    """
    Records a question the agent couldn't confidently answer. If a
    semantically similar unresolved question already exists for this
    company, bumps its occurrence count instead of creating a
    near-duplicate row. Best-effort: any failure here (including
    embedding failures) is logged and swallowed - this is a business
    insight feature, never something that should be able to affect the
    actual call.
    """
    try:
        new_vector = embed_query(question)

        existing_gaps = (
            db.query(UnansweredQuestion)
            .filter(UnansweredQuestion.company_id == company_id, UnansweredQuestion.resolved == False)  # noqa: E712
            .all()
        )

        for gap in existing_gaps:
            gap_vector = embed_query(gap.question)
            if _cosine_similarity(new_vector, gap_vector) >= SIMILARITY_THRESHOLD:
                gap.occurrence_count = (gap.occurrence_count or 1) + 1
                db.commit()
                return

        new_gap = UnansweredQuestion(company_id=company_id, question=question, occurrence_count=1)
        db.add(new_gap)
        db.commit()
    except Exception:
        logger.exception("Failed to log knowledge gap for company_id=%s — continuing without it.", company_id)
        db.rollback()