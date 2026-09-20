"""
models/agent.py

WHAT THIS FILE DOES:
Defines the `Agent` table — this is the core object of the whole
platform. One row = one deployed AI voice agent (a clinic receptionist,
a restaurant order-taker, a cold-calling agent, etc). It stores:

  - Which company it belongs to
  - Which industry template it was built from (for default prompt/actions)
  - The FINAL generated system prompt (template + company details merged)
  - Voice settings (provider, voice id, language)
  - The Vapi assistant ID once deployed (so we can update/delete it later)
  - Phone number if provisioned
  - Status (draft -> deployed -> paused)

This is intentionally generic/config-driven: there is NO separate table
or code path per industry. The "clinic-ness" or "restaurant-ness" of an
agent lives entirely in its `system_prompt` text and `enabled_actions`
JSON list, both generated from the IndustryTemplate at creation time.
That's what makes this ONE platform instead of N separate apps.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class AgentStatus(str, enum.Enum):
    draft = "draft"
    deploying = "deploying"
    deployed = "deployed"
    paused = "paused"
    failed = "failed"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    name = Column(String, nullable=False)                 # e.g. "Bella Pizza Order Assistant"
    industry_key = Column(String, nullable=False)          # e.g. "restaurant" -> IndustryTemplate.key
    greeting = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)            # final generated prompt sent to the LLM
    fallback_message = Column(Text, default="I'm sorry, I didn't understand that. Could you repeat it?")

    # Voice config
    voice_provider = Column(String, default="vapi")
    voice_id = Column(String, nullable=True)                # e.g. an 11labs/PlayHT voice id
    language = Column(String, default="en")

    # Enabled actions for this agent, e.g. ["book_appointment", "cancel_appointment"]
    enabled_actions = Column(JSON, default=list)

    # Deployment info
    status = Column(SAEnum(AgentStatus), default=AgentStatus.draft)
    vapi_assistant_id = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    widget_embed_id = Column(String, nullable=True)         # for web widget deployments

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="agents")
    call_logs = relationship("CallLog", back_populates="agent", cascade="all, delete-orphan")
