"""
models/do_not_call.py

WHAT THIS FILE DOES:
Defines `DoNotCallEntry` — a per-company do-not-call list. This is not
optional polish, it's a real compliance requirement: outbound
cold-calling without opt-out handling is a legal liability in most
jurisdictions (TCPA in the US and equivalents elsewhere). Any phone
number on this list gets automatically skipped before a campaign ever
dials it, and a number lands here either added manually by the
business owner or automatically when a caller asks to stop being
contacted during a call.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class DoNotCallEntry(Base):
    __tablename__ = "do_not_call_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    phone = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))