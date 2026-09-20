"""
models/campaign.py

WHAT THIS FILE DOES:
Defines `Campaign` and `CampaignContact` — outbound cold-calling.

UPDATED: added calling_hours_start / calling_hours_end for compliance
— many jurisdictions legally restrict outbound calling to daytime
hours, and campaign_service.py now enforces this before ever dialing.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"


class ContactStatus(str, enum.Enum):
    pending = "pending"
    calling = "calling"
    completed = "completed"
    failed = "failed"
    no_answer = "no_answer"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)

    name = Column(String, nullable=False)
    status = Column(SAEnum(CampaignStatus), default=CampaignStatus.draft)
    total_contacts = Column(Integer, default=0)
    calls_completed = Column(Integer, default=0)

    calling_hours_start = Column(Integer, default=9)
    calling_hours_end = Column(Integer, default=18)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    contacts = relationship("CampaignContact", back_populates="campaign", cascade="all, delete-orphan")


class CampaignContact(Base):
    __tablename__ = "campaign_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)

    name = Column(String, nullable=True)
    phone = Column(String, nullable=False)
    status = Column(SAEnum(ContactStatus), default=ContactStatus.pending)
    vapi_call_id = Column(String, nullable=True)
    outcome_notes = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="contacts")