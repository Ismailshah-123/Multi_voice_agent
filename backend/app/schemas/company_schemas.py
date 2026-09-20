"""
schemas/company_schemas.py

WHAT THIS FILE DOES:
Request/response models for creating and viewing a Company (tenant).
A user creates a Company first ("Bella Pizza"), then creates Agents under
that company. This mirrors the real product flow: Login -> Create
Company -> Create Agent -> Select Industry -> Fill Details -> Deploy.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.company import PlanTier


class CompanyCreateRequest(BaseModel):
    name: str
    industry: str
    website: str | None = None
    timezone: str = "UTC"
    default_language: str = "en"


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    industry: str
    website: str | None
    timezone: str
    default_language: str
    plan_tier: PlanTier
    monthly_minutes_used: int
    monthly_minutes_limit: int
    escalation_phone_number: str | None = None
    created_at: datetime
