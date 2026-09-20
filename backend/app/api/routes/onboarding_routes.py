"""
api/routes/onboarding_routes.py

WHAT THIS FILE DOES:
Computes a simple onboarding checklist for a company by checking what
actually exists in the database — no separate "progress" table needed,
since each step is just "does at least one row of X exist for this
company." Powers the checklist shown at the top of the Dashboard on
first login, which reduces the "I don't know what to do first" drop-off
that kills self-serve SaaS signups.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.agent import Agent, AgentStatus
from app.models.knowledge_base import KnowledgeBaseItem
from app.models.integration import Integration
from app.models.call_log import CallLog
from app.api.routes.company_routes import _get_owned_company_or_404

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.get("/status")
def onboarding_status(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)

    has_deployed_agent = db.query(Agent).filter(Agent.company_id == company_id, Agent.status == AgentStatus.deployed).first() is not None
    has_uploaded_kb = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.company_id == company_id).first() is not None
    has_connected_calendar = db.query(Integration).filter(Integration.company_id == company_id, Integration.is_active == True).first() is not None  # noqa: E712
    has_received_call = db.query(CallLog).join(Agent, CallLog.agent_id == Agent.id).filter(Agent.company_id == company_id).first() is not None

    steps = [
        {"key": "deploy_agent", "label": "Deploy your first AI agent", "done": has_deployed_agent},
        {"key": "upload_kb", "label": "Upload a document to your knowledge base", "done": has_uploaded_kb},
        {"key": "connect_calendar", "label": "Connect your calendar or another integration", "done": has_connected_calendar},
        {"key": "first_call", "label": "Handle your first call", "done": has_received_call},
    ]
    completed = sum(1 for s in steps if s["done"])

    return {"steps": steps, "completed": completed, "total": len(steps), "is_fully_onboarded": completed == len(steps)}
