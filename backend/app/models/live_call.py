"""
models/live_call.py

WHAT THIS FILE DOES:
Defines the `LiveCall` table — tracks calls that are CURRENTLY in
progress, with the transcript building up in near-real-time as Vapi
sends partial transcript webhook events during the call. This is what
powers the "Live Calls" dashboard page: instead of only seeing a call
after it's over (CallLog), you can watch it happen.

Rows are created when a call starts, updated on every transcript chunk
Vapi sends, and marked "completed" (or deleted) once the call ends and
the final CallLog is saved — this table only needs to hold calls that
are actively happening, not permanent history.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class LiveCallStatus(str, enum.Enum):
    ringing = "ringing"
    in_progress = "in_progress"
    completed = "completed"


class LiveCall(Base):
    __tablename__ = "live_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)

    vapi_call_id = Column(String, unique=True, nullable=False, index=True)
    caller_number = Column(String, nullable=True)
    status = Column(SAEnum(LiveCallStatus), default=LiveCallStatus.ringing)

    live_transcript = Column(Text, default="")  # grows as transcript chunks arrive
    frustration_flagged = Column(String, default="false")  # "true"/"false" — simple flag for the Live Calls dashboard to highlight
    listen_url = Column(String, nullable=True)  # Vapi's live audio websocket (wss://) for real-time listening in the dashboard

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
