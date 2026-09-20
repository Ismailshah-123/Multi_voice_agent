"""tests/test_sentiment.py — frustration keyword detection."""

from app.services.sentiment_service import is_frustrated


def test_detects_explicit_human_request():
    assert is_frustrated("Can I speak to a human please")


def test_detects_frustration_phrases():
    assert is_frustrated("This is ridiculous, I already told you my address")


def test_normal_conversation_not_flagged():
    assert not is_frustrated("I would like to order a pizza")
    assert not is_frustrated("Great, thanks so much!")


def test_empty_text_not_flagged():
    assert not is_frustrated("")
    assert not is_frustrated(None)
