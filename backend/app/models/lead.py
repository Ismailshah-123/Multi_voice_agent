"""
models/lead.py

WHAT THIS FILE DOES:
Defines the `Lead` table — a lightweight built-in CRM so every business
on the platform gets lead tracking out of the box, even before they
connect HubSpot/Salesforce. Populated automatically by
services/post_call_workflow.py whenever a call results in a booking,
order, or qualified sales lead. This is what the "CRM Update" step in
the post-call automation actually writes to.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    booked = "booked"
    lost = "lost"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=True)

    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    source = Column(String, default="voice_call")   # "voice_call" | "manual" | "web_widget"
    notes = Column(Text, nullable=True)
    status = Column(SAEnum(LeadStatus), default=LeadStatus.new)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")
