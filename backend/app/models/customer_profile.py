"""
models/customer_profile.py

WHAT THIS FILE DOES:
Defines the `CustomerProfile` table — this is the "AI Memory" feature
from the original product spec: remember patient name, previous visit,
booking history, etc. One row per (company, phone number). Updated
automatically by post_call_workflow.py after every call, and looked up
by action_handler.py's get_caller_history action so the agent can
recognize a returning caller and personalize the conversation
("Welcome back, Sarah! Same order as last time?").
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    visit_count = Column(Integer, default=0)
    last_summary = Column(Text, nullable=True)   # short human-readable summary of the most recent interaction

    # STRUCTURED memory — extracted facts the agent can actually reason
    # over, not just read as a paragraph. Populated by
    # services/memory_extraction_service.py after each call. Shape is
    # intentionally free-form JSON since different industries capture
    # different things (dietary restrictions for a restaurant, preferred
    # appointment times for a clinic, budget range for real estate) —
    # e.g. {"preferred_time": "mornings", "dietary_restrictions": ["vegetarian"], "notes": "prefers window seating"}
    structured_facts = Column(JSON, default=dict)

    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
