"""
models/call_log.py

WHAT THIS FILE DOES:
Defines the `CallLog` table. Every time an agent handles a call (phone or
web widget), Vapi sends a webhook when the call ends
(api/routes/webhook_routes.py handles this). We store the transcript,
summary, duration, and any structured outcome (e.g. "order_placed",
"appointment_booked") here. This powers the Analytics dashboard (calls
today, missed calls, avg duration, appointments booked, revenue, etc.)
and gives each business owner a searchable call history.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Float, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)

    vapi_call_id = Column(String, unique=True, nullable=True)
    caller_number = Column(String, nullable=True)
    channel = Column(String, default="phone")   # "phone" | "web_widget"

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)     # "positive" | "neutral" | "negative"

    outcome = Column(String, nullable=True)         # "order_placed" | "appointment_booked" | "no_action" | "escalated"
    outcome_data = Column(JSON, nullable=True)       # structured data captured from the call, e.g. order items
    was_successful = Column(Boolean, default=True)

    recording_url = Column(String, nullable=True)
    cost = Column(Float, nullable=True)              # Vapi call cost, for margin tracking

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="call_logs")
