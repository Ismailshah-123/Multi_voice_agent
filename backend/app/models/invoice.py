"""
models/invoice.py

WHAT THIS FILE DOES:
Defines `Invoice` — one row per successful Stripe payment. Populated by
billing_routes.py's checkout.session.completed webhook handler. Used by
services/invoice_pdf_service.py to generate a downloadable PDF receipt
for each payment.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    plan = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    stripe_session_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
