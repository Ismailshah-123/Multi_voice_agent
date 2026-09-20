"""
models/integration.py

WHAT THIS FILE DOES:
Defines the `Integration` table — stores per-company OAuth connections to
Gmail, Outlook, Google/Microsoft Calendar, and WhatsApp Business. When a
business owner clicks "Connect Google Calendar" in the dashboard, the
OAuth flow (services/integrations/google_service.py) stores the
access/refresh tokens here, scoped to their company_id. Agent actions
(e.g. "book_appointment") then look up the company's active integration
to actually create the calendar event or send the WhatsApp confirmation.

SECURITY NOTE: access_token and refresh_token should be encrypted at rest
in a real production deployment (e.g. using Fernet symmetric encryption
before saving, decrypt on read). A helper for this belongs in
core/security.py — added as `encrypt_token` / `decrypt_token` once you
wire real OAuth. Left as plain columns here to keep the schema readable;
do not ship to production without encrypting these two fields.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class IntegrationProvider(str, enum.Enum):
    google_calendar = "google_calendar"
    gmail = "gmail"
    outlook = "outlook"
    outlook_calendar = "outlook_calendar"
    whatsapp = "whatsapp"


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    provider = Column(SAEnum(IntegrationProvider), nullable=False)
    access_token = Column(String, nullable=True)     # encrypt before storing in production
    refresh_token = Column(String, nullable=True)     # encrypt before storing in production
    token_expires_at = Column(DateTime, nullable=True)

    external_account_email = Column(String, nullable=True)   # which Gmail/Outlook account is connected
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="integrations")
