"""
models/company.py

WHAT THIS FILE DOES:
Defines the `Company` table — this is the TENANT in your multi-tenant
architecture. Every clinic, restaurant, hotel, etc. that signs up is a
Company row. Every Agent, KnowledgeBase document, and CallLog belongs to
exactly one Company. This is what keeps customer data isolated: when you
query knowledge base chunks or call logs, you ALWAYS filter by
company_id — this is what "no mixing between customers" means in
practice.

Also stores the Stripe subscription info for billing and the plan tier,
since limits (max agents, max minutes/month) are enforced per company.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class PlanTier(str, enum.Enum):
    free = "free"
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    industry = Column(String, nullable=False)  # matches an IndustryTemplate.key, e.g. "clinic"
    website = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
    default_language = Column(String, default="en")

    # Billing
    plan_tier = Column(SAEnum(PlanTier), default=PlanTier.free)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    monthly_minutes_used = Column(Integer, default=0)
    monthly_minutes_limit = Column(Integer, default=60)  # free tier default

    # Phone number to transfer callers to when the agent can't help or the
    # caller asks for a human. If set, every deployed agent automatically
    # gets a transfer tool pointing here (see action_schemas.py).
    escalation_phone_number = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="companies")
    agents = relationship("Agent", back_populates="company", cascade="all, delete-orphan")
    knowledge_base_items = relationship("KnowledgeBaseItem", back_populates="company", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="company", cascade="all, delete-orphan")
