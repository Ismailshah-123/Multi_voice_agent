"""
services/prompt_builder.py

WHAT THIS FILE DOES:
Takes an IndustryTemplate + a Company + optional custom instructions from
the user, and generates the final system prompt and greeting text that
gets sent to Vapi when an agent is deployed. This is the "AI Prompt
Builder" feature from the product spec — the user never writes a prompt
by hand, they just fill a form and this function does the merge.

Kept as pure functions (no DB writes) so it's easy to unit test.
"""

from app.templates.industry_templates import get_template


class UnknownIndustryError(Exception):
    pass


def build_system_prompt(
    industry_key: str,
    company_name: str,
    business_hours: str = "not specified",
    custom_instructions: str | None = None,
) -> str:
    """
    Fills the industry template's base_prompt_template with company
    specifics. Raises UnknownIndustryError if industry_key doesn't match
    any seeded template (caller should catch this and return a 400).
    """
    template = get_template(industry_key)
    if not template:
        raise UnknownIndustryError(f"No industry template found for key '{industry_key}'")

    return template["base_prompt_template"].format(
        company_name=company_name,
        business_hours=business_hours,
        custom_instructions=custom_instructions or "",
    ).strip()


def build_greeting(industry_key: str, company_name: str) -> str:
    template = get_template(industry_key)
    if not template:
        raise UnknownIndustryError(f"No industry template found for key '{industry_key}'")

    greeting_template = template.get("default_greeting_template") or "Thanks for contacting {company_name}, how can I help?"
    return greeting_template.format(company_name=company_name)


def resolve_actions(industry_key: str, requested_actions: list[str] | None) -> list[str]:
    """
    If the user explicitly picked actions in the builder UI, use those
    (validated against the template's allowed set). Otherwise fall back
    to the industry template's default_actions. `get_caller_history` is
    always included regardless of industry — every agent should be able
    to recognize returning callers.
    """
    template = get_template(industry_key)
    if not template:
        raise UnknownIndustryError(f"No industry template found for key '{industry_key}'")

    allowed = set(template["default_actions"])
    if not requested_actions:
        actions = list(template["default_actions"])
    else:
        actions = [a for a in requested_actions if a in allowed] or list(template["default_actions"])

    if "get_caller_history" not in actions:
        actions.insert(0, "get_caller_history")
    return actions
