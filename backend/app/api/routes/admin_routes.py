"""
api/routes/admin_routes.py

WHAT THIS FILE DOES:
Platform-owner-only endpoints — a bird's-eye view across ALL companies
on the platform: how many businesses signed up, total calls handled
platform-wide, which companies are on which plan. This is what YOU (the
platform owner) need to actually run this as a business, separate from
what any individual company owner sees in their own dashboard.

Protected by require_superadmin — a regular business owner, even with
full access to their own company, gets a 403 here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.agent import Agent
from app.models.call_log import CallLog

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user


@router.get("/overview")
def platform_overview(
    db: Session = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    total_companies = db.query(Company).count()
    total_agents = db.query(Agent).count()
    total_calls = db.query(CallLog).count()

    plan_breakdown = (
        db.query(Company.plan_tier, func.count(Company.id))
        .group_by(Company.plan_tier)
        .all()
    )

    return {
        "total_companies": total_companies,
        "total_agents": total_agents,
        "total_calls": total_calls,
        "plan_breakdown": [{"plan": str(p), "count": c} for p, c in plan_breakdown],
    }


@router.get("/companies")
def list_all_companies(
    db: Session = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    companies = db.query(Company).join(User, Company.owner_id == User.id).add_columns(User.email).all()
    result = []
    for company, owner_email in companies:
        call_count = db.query(CallLog).join(Agent, CallLog.agent_id == Agent.id).filter(Agent.company_id == company.id).count()
        agent_count = db.query(Agent).filter(Agent.company_id == company.id).count()
        result.append({
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "owner_email": owner_email,
            "plan_tier": company.plan_tier,
            "agent_count": agent_count,
            "call_count": call_count,
            "monthly_minutes_used": company.monthly_minutes_used,
            "created_at": company.created_at,
        })
    return result
