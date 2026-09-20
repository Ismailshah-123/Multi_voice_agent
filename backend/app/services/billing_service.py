"""
services/billing_service.py

WHAT THIS FILE DOES:
Wraps all Stripe interactions: creating a Checkout session so a company
can subscribe to a plan, creating a Stripe Customer, cancelling a
subscription, and handling the billing portal (so customers can update
their card / cancel themselves without you building that UI).

PLAN CONFIG lives in this file (PLAN_CATALOG) — maps each PlanTier to its
Stripe Price ID and the minute/agent limits enforced elsewhere (e.g.
webhook_routes.py checks monthly_minutes_used against
monthly_minutes_limit before allowing a call, and agent_routes.py can
check agent count against a max-agents limit).

SETUP REQUIRED before this works:
  1. Create a Stripe account, create Products + Prices for each plan
     tier (Starter, Professional, Enterprise) in the Stripe Dashboard.
  2. Copy each Price ID into PLAN_CATALOG below (or move to .env if you
     prefer not to hardcode them).
  3. Put STRIPE_SECRET_KEY in .env.
  4. Set up a webhook endpoint in the Stripe Dashboard pointing to
     POST /api/v1/billing/webhook, subscribe to at least:
     checkout.session.completed, customer.subscription.updated,
     customer.subscription.deleted. Copy the signing secret into
     STRIPE_WEBHOOK_SECRET.

NOTE: This code has NOT been tested against a live Stripe account in
this environment (no network access to api.stripe.com here). The shape
of every call below matches Stripe's current Python SDK (v11) exactly,
but you should run one real test checkout in Stripe test mode before
going live — test mode is free and uses fake card numbers.
"""

import stripe
from app.core.config import settings
from app.models.company import PlanTier

stripe.api_key = settings.STRIPE_SECRET_KEY

# Map each plan to its Stripe Price ID and the limits enforced on the Company row.
# Replace the placeholder price_xxx values with your real Stripe Price IDs.
PLAN_CATALOG = {
    PlanTier.starter: {
        "stripe_price_id": "price_starter_replace_me",
        "monthly_minutes_limit": 500,
        "max_agents": 3,
        "display_price": "$30/month",
    },
    PlanTier.professional: {
        "stripe_price_id": "price_professional_replace_me",
        "monthly_minutes_limit": 2000,
        "max_agents": 15,
        "display_price": "$60/month",
    },
    PlanTier.enterprise: {
        "stripe_price_id": "price_enterprise_replace_me",
        "monthly_minutes_limit": 6000,
        "max_agents": 50,
        "display_price": "$90/month",
    },
}

FREE_TIER_LIMITS = {"monthly_minutes_limit": 60, "max_agents": 1}


def get_or_create_stripe_customer(company_id: str, company_name: str, owner_email: str, existing_customer_id: str | None) -> str:
    """Returns the Stripe Customer ID, creating one if the company doesn't have one yet."""
    if existing_customer_id:
        return existing_customer_id

    customer = stripe.Customer.create(
        name=company_name,
        email=owner_email,
        metadata={"company_id": str(company_id)},
    )
    return customer.id


def create_checkout_session(company_id: str, customer_id: str, plan: PlanTier, success_url: str, cancel_url: str) -> str:
    """
    Creates a Stripe Checkout session for the given plan and returns the
    hosted checkout URL to redirect the user to. This is what the
    "Upgrade Plan" button in the Billing dashboard page calls.
    """
    plan_config = PLAN_CATALOG.get(plan)
    if not plan_config:
        raise ValueError(f"No Stripe price configured for plan '{plan}'. Set it in PLAN_CATALOG.")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": plan_config["stripe_price_id"], "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"company_id": str(company_id), "plan": plan.value},
    )
    return session.url


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """
    Returns a URL to Stripe's hosted billing portal, where the customer
    can update payment methods, view invoices, or cancel — no custom UI
    needed for any of that.
    """
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url


def cancel_subscription(subscription_id: str) -> None:
    stripe.Subscription.cancel(subscription_id)


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """
    Verifies the webhook came from Stripe (not a spoofed request) using
    the signing secret, and returns the parsed event. Raises
    stripe.error.SignatureVerificationError if verification fails —
    caller should catch this and return 400.
    """
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


def plan_for_price_id(price_id: str) -> PlanTier | None:
    """Reverse lookup: given a Stripe Price ID from a webhook event, find which PlanTier it maps to."""
    for plan, config in PLAN_CATALOG.items():
        if config["stripe_price_id"] == price_id:
            return plan
    return None
