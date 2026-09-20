"""
models/unanswered_question.py

WHAT THIS FILE DOES:
Defines `UnansweredQuestion` — this is what turns the RAG confidence
system from a defensive safety net into a genuine business insight
tool. Every time the agent has to fall back to "I don't have that
information" (either because nothing was retrieved, or because the
confidence check rejected a weak match), the question gets logged here
instead of just silently disappearing.

The business owner can then see, on their dashboard, the EXACT real
customer questions their knowledge base failed to answer — telling
them precisely what documents to add next. This closes the loop: RAG
doesn't just answer from what you uploaded, it tells you what you're
missing.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class UnansweredQuestion(Base):
    __tablename__ = "unanswered_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    question = Column(Text, nullable=False)
    occurrence_count = Column(Integer, default=1)
    resolved = Column(Boolean, default=False)

    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))