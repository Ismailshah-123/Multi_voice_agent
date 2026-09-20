"""
models/order.py

WHAT THIS FILE DOES:
Defines `Order` — this is what makes order cancellation REAL instead of
a soft "we've noted your cancellation" message. Previously, "cancel_order"
was mapped to the same handler as appointment cancellation, which
searches the Booking table — orders were never actually stored anywhere
structured, so there was nothing real to find and cancel.

Now _take_order saves a real Order row (items, status), and
_cancel_order looks up the customer's most recent PLACED order and
marks it cancelled — the same pattern already proven for appointments
via the Booking model.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class OrderStatus(str, enum.Enum):
    placed = "placed"
    cancelled = "cancelled"
    completed = "completed"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)
    items = Column(JSON, default=list)
    delivery_or_pickup = Column(String, default="pickup")
    status = Column(SAEnum(OrderStatus), default=OrderStatus.placed)

    vapi_call_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))