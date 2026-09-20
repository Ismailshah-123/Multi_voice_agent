"""
models/__init__.py

WHAT THIS FILE DOES:
Re-exports every model class so other files can do
`from app.models import Agent, Company, User` instead of importing from
each individual file. Also ensures every model is registered with
SQLAlchemy's Base metadata before `init_db()` or Alembic tries to create
tables (Python only registers a class with SQLAlchemy once its module has
been imported).
"""

from app.models.user import User
from app.models.company import Company, PlanTier
from app.models.agent import Agent, AgentStatus
from app.models.industry_template import IndustryTemplate
from app.models.knowledge_base import KnowledgeBaseItem, ProcessingStatus
from app.models.call_log import CallLog
from app.models.integration import Integration, IntegrationProvider
from app.models.lead import Lead, LeadStatus
from app.models.customer_profile import CustomerProfile
from app.models.booking import Booking, BookingStatus
from app.models.live_call import LiveCall, LiveCallStatus
from app.models.campaign import Campaign, CampaignStatus, CampaignContact, ContactStatus
from app.models.company_member import CompanyMember, MemberRole
from app.models.invoice import Invoice
from app.models.prompt_variant import PromptVariant
from app.models.unanswered_question import UnansweredQuestion
from app.models.order import Order, OrderStatus

__all__ = [
    "User",
    "Company",
    "PlanTier",
    "Agent",
    "AgentStatus",
    "IndustryTemplate",
    "KnowledgeBaseItem",
    "ProcessingStatus",
    "CallLog",
    "Integration",
    "IntegrationProvider",
    "Lead",
    "LeadStatus",
    "CustomerProfile",
    "Booking",
    "BookingStatus",
    "LiveCall",
    "LiveCallStatus",
    "Campaign",
    "CampaignStatus",
    "CampaignContact",
    "ContactStatus",
    "CompanyMember",
    "MemberRole",
    "Invoice",
    "PromptVariant",
    "UnansweredQuestion",
    "Order",
    "OrderStatus"
]
