"""
models/user.py

WHAT THIS FILE DOES:
Defines the `User` table — a person who signs up to the platform to
create and manage AI voice agents for their business. One User can own
one or more Companies (in case someone manages multiple businesses under
one login). Passwords are stored hashed, never in plain text.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # nullable: OAuth-only users have no password
    full_name = Column(String, nullable=True)

    # OAuth provider info (Google/Microsoft login), null for email/password users
    oauth_provider = Column(String, nullable=True)   # "google" | "microsoft" | None
    oauth_id = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superadmin = Column(Boolean, default=False)  # platform-owner access to the Admin panel across all companies

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    companies = relationship("Company", back_populates="owner", cascade="all, delete-orphan")
