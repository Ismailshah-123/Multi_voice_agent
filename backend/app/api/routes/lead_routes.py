"""
api/routes/lead_routes.py

WHAT THIS FILE DOES:
Exposes the Lead records created automatically during calls (via
action_handler.py + post_call_workflow.py) so the dashboard's CRM/Leads
page can show them. This is the built-in CRM every company gets for
free, before they connect HubSpot/Salesforce.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.lead import Lead
from app.api.routes.company_routes import _get_owned_company_or_404

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])



@router.get("/export")
def export_leads_csv(
        company_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
        """Exports all leads as a downloadable CSV — standard expectation for any real CRM."""
        _get_owned_company_or_404(db, company_id, current_user.id)
        leads = db.query(Lead).filter(Lead.company_id == company_id).order_by(Lead.created_at.desc()).all()
 
        import csv, io
        from fastapi.responses import Response
 
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Phone", "Email", "Status", "Source", "Notes", "Created At"])
        for lead in leads:
            writer.writerow([lead.name, lead.phone, lead.email, lead.status, lead.source, lead.notes, lead.created_at])
 
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
        )

@router.get("")
def list_leads(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    leads = db.query(Lead).filter(Lead.company_id == company_id).order_by(Lead.created_at.desc()).all()
    return [
        {
            "id": l.id, "name": l.name, "phone": l.phone, "email": l.email,
            "notes": l.notes, "status": l.status, "source": l.source,
            "created_at": l.created_at,
        }
        for l in leads
    ]
