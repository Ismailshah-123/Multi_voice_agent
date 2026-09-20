"""
api/routes/company_routes.py

WHAT THIS FILE DOES:
CRUD for Company (tenant), plus team management. A logged-in user
creates a Company here first, then creates Agents under it. Ownership
checks now accept EITHER being the original creator (Company.owner_id)
OR having an active CompanyMember row — this is what lets a business
owner invite staff to help manage the same company without sharing
their login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.company_member import CompanyMember, MemberRole
from app.schemas.company_schemas import CompanyCreateRequest, CompanyResponse

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = Company(owner_id=current_user.id, **payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)

    # Also add the creator as an explicit "owner" member row, so the
    # membership table is the single source of truth for who has access,
    # even though Company.owner_id is kept for "who pays the bill" clarity.
    membership = CompanyMember(company_id=company.id, user_id=current_user.id, role=MemberRole.owner)
    db.add(membership)
    db.commit()

    return company


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member_company_ids = db.query(CompanyMember.company_id).filter(CompanyMember.user_id == current_user.id).subquery()
    return (
        db.query(Company)
        .filter((Company.owner_id == current_user.id) | (Company.id.in_(member_company_ids)))
        .all()
    )


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_owned_company_or_404(db, company_id, current_user.id)
    return company


@router.post("/{company_id}/invite", status_code=status.HTTP_201_CREATED)
def invite_member(
    company_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds an existing platform user (by email) to this company's team.
    Requires the inviter to already have access. The invited user must
    already have a platform account (sign up first, then get invited) —
    a full email-invite-to-signup flow would be the next iteration of
    this feature.
    """
    company = _get_owned_company_or_404(db, company_id, current_user.id)
    email = payload.get("email")
    role = payload.get("role", "staff")

    invitee = db.query(User).filter(User.email == email).first()
    if not invitee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No platform account found for that email. They need to sign up first.")

    existing = db.query(CompanyMember).filter(CompanyMember.company_id == company.id, CompanyMember.user_id == invitee.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This person is already a member of this company.")

    member = CompanyMember(company_id=company.id, user_id=invitee.id, role=MemberRole(role), invited_email=email)
    db.add(member)
    db.commit()
    return {"status": "invited", "email": email, "role": role}


@router.get("/{company_id}/members")
def list_members(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    members = (
        db.query(CompanyMember, User)
        .join(User, CompanyMember.user_id == User.id)
        .filter(CompanyMember.company_id == company_id)
        .all()
    )
    return [{"user_id": u.id, "email": u.email, "full_name": u.full_name, "role": m.role} for m, u in members]


@router.patch("/{company_id}/escalation-number")
def set_escalation_number(
    company_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sets the phone number agents transfer callers to for human handoff. Redeploy agents after changing this to apply it."""
    company = _get_owned_company_or_404(db, company_id, current_user.id)
    company.escalation_phone_number = payload.get("phone_number") or None
    db.commit()
    return {"escalation_phone_number": company.escalation_phone_number}


def _get_owned_company_or_404(db: Session, company_id: uuid.UUID, owner_id: uuid.UUID) -> Company:
    """
    Fetches a Company only if the requesting user is either the original
    owner OR an active team member — otherwise 404s (not 403, to avoid
    leaking whether a given company_id exists at all).
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    if company.owner_id == owner_id:
        return company

    is_member = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == company_id, CompanyMember.user_id == owner_id)
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    return company
