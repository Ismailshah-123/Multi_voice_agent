"""
models/company_member.py

WHAT THIS FILE DOES:
Defines `CompanyMember` — lets more than one User manage the same
Company (team access), instead of only the original creator (Company.
owner_id) being able to do anything. A row here grants a User access to
a Company with a role. The original creator still exists as
Company.owner_id (kept for backward compatibility and "who pays the
bill" clarity), but company_routes.py's ownership check now accepts
EITHER being the owner OR having an active CompanyMember row.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class MemberRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"     # can manage agents, billing, integrations
    staff = "staff"      # can view dashboard, leads, call logs — not billing/settings


class CompanyMember(Base):
    __tablename__ = "company_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(SAEnum(MemberRole), default=MemberRole.staff)

    invited_email = Column(String, nullable=True)  # kept for reference even if the user later changes their email
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
