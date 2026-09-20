"""
api/routes/analytics_routes.py

WHAT THIS FILE DOES:
Aggregates real data from CallLog and Lead tables into the numbers and
time-series the frontend's KPI dashboard charts need: calls per day,
total calls, average duration, leads captured, conversion rate, and
minutes used vs plan limit. All computed with real SQL aggregation
against actual data — nothing here is mocked or hardcoded.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.call_log import CallLog
from app.models.agent import Agent
from app.models.lead import Lead
from app.models.company import Company
from app.api.routes.company_routes import _get_owned_company_or_404

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary")
def get_summary(
    company_id: uuid.UUID,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_owned_company_or_404(db, company_id, current_user.id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_query = (
        db.query(CallLog)
        .join(Agent, CallLog.agent_id == Agent.id)
        .filter(Agent.company_id == company_id, CallLog.created_at >= since)
    )

    total_calls = base_query.count()
    avg_duration = base_query.with_entities(func.avg(CallLog.duration_seconds)).scalar() or 0
    total_leads = db.query(Lead).filter(Lead.company_id == company_id, Lead.created_at >= since).count()
    booked_leads = (
        db.query(Lead)
        .filter(Lead.company_id == company_id, Lead.created_at >= since, Lead.status == "booked")
        .count()
    )
    conversion_rate = round((booked_leads / total_leads) * 100, 1) if total_leads else 0.0

    # Calls per day for the trend chart
    daily_rows = (
        base_query.with_entities(
            func.date(CallLog.created_at).label("day"),
            func.count(CallLog.id).label("count"),
        )
        .group_by(func.date(CallLog.created_at))
        .order_by(func.date(CallLog.created_at))
        .all()
    )
    calls_by_day = [{"date": str(row.day), "calls": row.count} for row in daily_rows]

    # Outcome breakdown for a pie/bar chart
    outcome_rows = (
        base_query.with_entities(CallLog.outcome, func.count(CallLog.id))
        .group_by(CallLog.outcome)
        .all()
    )
    outcomes = [{"outcome": o or "no_action", "count": c} for o, c in outcome_rows]

    return {
        "total_calls": total_calls,
        "avg_duration_seconds": round(avg_duration, 1),
        "total_leads": total_leads,
        "booked_leads": booked_leads,
        "conversion_rate_percent": conversion_rate,
        "minutes_used": company.monthly_minutes_used,
        "minutes_limit": company.monthly_minutes_limit,
        "calls_by_day": calls_by_day,
        "outcomes": outcomes,
    }
