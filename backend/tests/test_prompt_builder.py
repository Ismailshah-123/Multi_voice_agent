"""tests/test_prompt_builder.py — industry template prompt generation."""

import pytest
from app.services.prompt_builder import build_system_prompt, build_greeting, resolve_actions, UnknownIndustryError


def test_build_system_prompt_fills_company_name():
    prompt = build_system_prompt("restaurant", company_name="Bella Pizza")
    assert "Bella Pizza" in prompt


def test_build_system_prompt_unknown_industry_raises():
    with pytest.raises(UnknownIndustryError):
        build_system_prompt("not_a_real_industry", company_name="X")


def test_build_greeting_includes_company_name():
    greeting = build_greeting("clinic", "Sunrise Dental")
    assert "Sunrise Dental" in greeting


def test_resolve_actions_always_includes_caller_history():
    actions = resolve_actions("restaurant", None)
    assert "get_caller_history" in actions
    assert "take_order" in actions


def test_resolve_actions_filters_invalid_requested_actions():
    actions = resolve_actions("restaurant", ["take_order", "not_a_real_action"])
    assert "take_order" in actions
    assert "not_a_real_action" not in actions
