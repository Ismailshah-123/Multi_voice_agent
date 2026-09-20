"""
models/booking.py

WHAT THIS FILE DOES:
Defines the `Booking` table. This is what makes cancellation REAL instead
of a soft "someone will confirm" message: when _book_appointment creates
a Google Calendar event, it saves the event's ID here. When
_cancel_appointment runs later, it looks up the most recent active
Booking for that customer and deletes the ACTUAL calendar event by ID —
Google Calendar has no "cancel by name" API, so storing the event_id at
creation time is the only reliable way to cancel the right event later.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class BookingStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)
    start_datetime = Column(String, nullable=True)  # stored as ISO string, matches what the LLM provides
    reason = Column(String, nullable=True)

    google_event_id = Column(String, nullable=True)   # the actual Google Calendar event ID, needed to cancel
    status = Column(SAEnum(BookingStatus), default=BookingStatus.confirmed)

    vapi_call_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
