"""tests/test_action_schemas.py — tool schema generation, including custom/AI-generated action names."""

from app.services.action_schemas import build_vapi_tools, infer_schema_for_action


def test_known_action_gets_correct_schema():
    tools = build_vapi_tools(["book_appointment"], server_url="https://example.com/webhook")
    assert len(tools) == 1
    params = tools[0]["function"]["parameters"]["properties"]
    assert "start_datetime" in params


def test_unknown_action_gets_inferred_schema_not_skipped():
    """Custom/AI-generated agents invent action names not in the static table — must still work."""
    tools = build_vapi_tools(["schedule_dog_walk"], server_url="https://example.com/webhook")
    assert len(tools) == 1  # not silently dropped


def test_infer_schema_booking_keywords():
    schema = infer_schema_for_action("book_grooming_session")
    assert "start_datetime" in schema["parameters"]["properties"]


def test_infer_schema_faq_fallback():
    schema = infer_schema_for_action("answer_random_question")
    assert "question" in schema["parameters"]["properties"]


def test_escalation_number_adds_transfer_tool():
    tools = build_vapi_tools(["book_appointment"], server_url="https://example.com/webhook", escalation_phone_number="+15551234567")
    transfer_tools = [t for t in tools if t.get("type") == "transferCall"]
    assert len(transfer_tools) == 1
    assert transfer_tools[0]["destinations"][0]["number"] == "+15551234567"


def test_no_escalation_number_no_transfer_tool():
    tools = build_vapi_tools(["book_appointment"], server_url="https://example.com/webhook")
    transfer_tools = [t for t in tools if t.get("type") == "transferCall"]
    assert len(transfer_tools) == 0
