"""tests/test_onboarding_and_teams.py — onboarding checklist and multi-user team access."""

from fastapi import HTTPException
import pytest

from app.api.routes.company_routes import _get_owned_company_or_404
from app.api.routes.onboarding_routes import onboarding_status
from app.models.company_member import CompanyMember, MemberRole


def test_fresh_company_onboarding_is_zero(db, make_user, make_company):
    owner = make_user("owner@x.com")
    company = make_company(owner)
    result = onboarding_status(company.id, db, owner)
    assert result["completed"] == 0
    assert result["total"] == 4
    assert result["is_fully_onboarded"] is False


def test_onboarding_updates_after_deploying_agent(db, make_user, make_company, make_agent):
    owner = make_user("owner@x.com")
    company = make_company(owner)
    make_agent(company)
    result = onboarding_status(company.id, db, owner)
    assert result["completed"] == 1
    deploy_step = next(s for s in result["steps"] if s["key"] == "deploy_agent")
    assert deploy_step["done"] is True


def test_staff_blocked_before_invite(db, make_user, make_company):
    owner = make_user("owner@x.com")
    staff = make_user("staff@x.com")
    company = make_company(owner)

    with pytest.raises(HTTPException) as exc_info:
        _get_owned_company_or_404(db, company.id, staff.id)
    assert exc_info.value.status_code == 404


def test_staff_allowed_after_invite(db, make_user, make_company):
    owner = make_user("owner@x.com")
    staff = make_user("staff@x.com")
    company = make_company(owner)

    db.add(CompanyMember(company_id=company.id, user_id=staff.id, role=MemberRole.staff))
    db.commit()

    result = _get_owned_company_or_404(db, company.id, staff.id)
    assert result.id == company.id
