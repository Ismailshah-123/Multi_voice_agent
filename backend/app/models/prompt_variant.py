"""
models/prompt_variant.py

WHAT THIS FILE DOES:
Defines `PromptVariant` — lets a business run TWO versions of the same
agent's prompt simultaneously (each deployed as its own separate Vapi
assistant with its own phone number), and compare which one performs
better. Stats (calls_count, conversions_count) are updated automatically
by webhook_routes.py whenever a call to either variant's assistant ends
— matched by vapi_assistant_id, same pattern used for regular Agents.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class PromptVariant(Base):
    __tablename__ = "prompt_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)

    variant_label = Column(String, nullable=False)   # "A" or "B", or any short label
    system_prompt = Column(Text, nullable=False)
    vapi_assistant_id = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    calls_count = Column(Integer, default=0)
    conversions_count = Column(Integer, default=0)   # calls with a "booked"/"order_placed" outcome

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def conversion_rate(self) -> float:
        if not self.calls_count:
            return 0.0
        return round((self.conversions_count / self.calls_count) * 100, 1)
