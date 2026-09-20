"""
scripts/create_stripe_plans.py

WHAT THIS FILE DOES:
Run this ONCE to create the 3 subscription products/prices in your
Stripe account via API, instead of manually clicking through the
Dashboard. Prints the real Price IDs at the end — copy those into
app/services/billing_service.py's PLAN_CATALOG (replacing the
"price_xxx_replace_me" placeholders).

USAGE:
    Set STRIPE_SECRET_KEY in your .env first (use your TEST key, sk_test_...,
    while developing — switch to sk_live_... only when you're ready for
    real customers).

    uv run python scripts/create_stripe_plans.py

Safe to re-run: it will create duplicate products if run twice, so only
run it once per Stripe account (test mode and live mode are separate
accounts, so you'll run it once for test and once for live).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

PLANS_TO_CREATE = [
    {"key": "starter", "name": "Starter", "amount_usd_cents": 3000, "description": "Up to 3 AI agents, 500 minutes/month"},
    {"key": "professional", "name": "Professional", "amount_usd_cents": 6000, "description": "Up to 15 AI agents, 2,000 minutes/month"},
    {"key": "enterprise", "name": "Enterprise", "amount_usd_cents": 9000, "description": "Up to 50 AI agents, 6,000 minutes/month"},
]


def main():
    if not settings.STRIPE_SECRET_KEY:
        print("ERROR: STRIPE_SECRET_KEY is not set in your .env file. Add it and try again.")
        sys.exit(1)

    print(f"Creating Stripe products using key starting with: {settings.STRIPE_SECRET_KEY[:12]}...")
    print("(sk_test_... = test mode, sk_live_... = LIVE real charges)\n")

    results = {}
    for plan in PLANS_TO_CREATE:
        product = stripe.Product.create(
            name=f"AI Voice Agent Platform — {plan['name']}",
            description=plan["description"],
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=plan["amount_usd_cents"],
            currency="usd",
            recurring={"interval": "month"},
        )
        results[plan["key"]] = price.id
        print(f"Created '{plan['name']}' plan -> Price ID: {price.id}")

    print("\nDone. Now open app/services/billing_service.py and update PLAN_CATALOG:")
    for key, price_id in results.items():
        print(f'  PlanTier.{key} -> "stripe_price_id": "{price_id}"')


if __name__ == "__main__":
    main()
