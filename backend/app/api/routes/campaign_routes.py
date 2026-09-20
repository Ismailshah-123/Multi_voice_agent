"""
api/routes/campaign_routes.py

WHAT THIS FILE DOES:
The API behind outbound cold-calling campaigns. POST /campaigns creates
a campaign with a CSV of contacts. POST /campaigns/{id}/start triggers
real outbound calls to every pending contact. GET endpoints let the
dashboard show progress as calls complete.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.campaign import Campaign, CampaignContact
from app.api.routes.company_routes import _get_owned_company_or_404
from app.services import campaign_service

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    company_id: uuid.UUID = Form(...),
    agent_id: uuid.UUID = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)

    file_bytes = await file.read()
    contacts = campaign_service.parse_contacts_csv(file_bytes)
    if not contacts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid contacts found. CSV must have a 'phone' column.",
        )

    campaign = campaign_service.create_campaign_with_contacts(db, company_id, agent_id, name, contacts)
    return {"id": campaign.id, "name": campaign.name, "total_contacts": campaign.total_contacts, "status": campaign.status}


@router.post("/{campaign_id}/start")
def start_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_owned_campaign_or_404(db, campaign_id, current_user.id)
    try:
        result = campaign_service.start_campaign(db, campaign)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.get("")
def list_campaigns(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    campaigns = db.query(Campaign).filter(Campaign.company_id == company_id).order_by(Campaign.created_at.desc()).all()
    return [
        {
            "id": c.id, "name": c.name, "status": c.status,
            "total_contacts": c.total_contacts, "calls_completed": c.calls_completed,
            "created_at": c.created_at,
        }
        for c in campaigns
    ]


@router.get("/{campaign_id}/contacts")
def list_campaign_contacts(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_owned_campaign_or_404(db, campaign_id, current_user.id)
    contacts = db.query(CampaignContact).filter(CampaignContact.campaign_id == campaign.id).all()
    return [
        {"id": c.id, "name": c.name, "phone": c.phone, "status": c.status, "outcome_notes": c.outcome_notes}
        for c in contacts
    ]


def _get_owned_campaign_or_404(db: Session, campaign_id: uuid.UUID, owner_id: uuid.UUID) -> Campaign:
    from app.models.company import Company
    campaign = (
        db.query(Campaign)
        .join(Company, Campaign.company_id == Company.id)
        .filter(Campaign.id == campaign_id, Company.owner_id == owner_id)
        .first()
)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return campaign


@router.post("/{campaign_id}/pause")
def pause_campaign_endpoint(
        campaign_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
        campaign = _get_owned_campaign_or_404(db, campaign_id, current_user.id)
        campaign_service.pause_campaign(db, campaign)
        return {"status": "paused"}
 
 
@router.get("/do-not-call")
def list_do_not_call(
        company_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
        _get_owned_company_or_404(db, company_id, current_user.id)
        from app.models.do_not_call import DoNotCallEntry
        entries = db.query(DoNotCallEntry).filter(DoNotCallEntry.company_id == company_id).all()
        return [{"id": e.id, "phone": e.phone, "reason": e.reason, "added_at": e.added_at} for e in entries]
 
 
@router.post("/do-not-call")
def add_do_not_call_manual(
        payload: dict,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
        company_id = uuid.UUID(payload["company_id"])
        _get_owned_company_or_404(db, company_id, current_user.id)
        campaign_service.add_to_do_not_call(db, company_id, payload["phone"], payload.get("reason", "Added manually"))
        return {"status": "added"}