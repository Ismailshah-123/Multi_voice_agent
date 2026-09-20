"""tests/test_campaigns.py — CSV parsing and campaign contact lifecycle."""

from app.services import campaign_service
from app.models.campaign import CampaignContact, ContactStatus


def test_parse_csv_basic():
    csv_data = b"name,phone\nJohn Smith,+15551112222\nJane Doe,+15553334444\n"
    contacts = campaign_service.parse_contacts_csv(csv_data)
    assert len(contacts) == 2
    assert contacts[0] == {"phone": "+15551112222", "name": "John Smith"}


def test_parse_csv_skips_rows_without_phone():
    csv_data = b"name,phone\nNo Phone Person,\nValid,+15551112222\n"
    contacts = campaign_service.parse_contacts_csv(csv_data)
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+15551112222"


def test_parse_csv_handles_missing_name():
    csv_data = b"phone\n+15551112222\n"
    contacts = campaign_service.parse_contacts_csv(csv_data)
    assert contacts[0]["name"] is None


def test_create_campaign_with_contacts(db, make_user, make_company, make_agent):
    user = make_user()
    company = make_company(user)
    agent = make_agent(company)

    contacts = [{"phone": "+15551112222", "name": "Lead One"}]
    campaign = campaign_service.create_campaign_with_contacts(db, company.id, agent.id, "Test Campaign", contacts)

    assert campaign.total_contacts == 1
    saved = db.query(CampaignContact).filter(CampaignContact.campaign_id == campaign.id).all()
    assert len(saved) == 1
    assert saved[0].status == ContactStatus.pending


def test_start_campaign_fails_cleanly_without_outbound_number(db, make_user, make_company, make_agent):
    user = make_user()
    company = make_company(user)
    agent = make_agent(company)

    campaign = campaign_service.create_campaign_with_contacts(
        db, company.id, agent.id, "Test", [{"phone": "+15551112222", "name": "Lead"}]
    )
    result = campaign_service.start_campaign(db, campaign)

    # No VAPI_OUTBOUND_PHONE_NUMBER_ID configured in test env -> should fail per-contact, not crash
    assert result["calls_placed"] == 0
    assert result["calls_failed_to_start"] == 1
