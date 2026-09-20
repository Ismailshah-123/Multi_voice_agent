"""
api/routes/billing_routes.py

WHAT THIS FILE DOES:
The API behind the Billing page in the dashboard. Three things:

  1. POST /checkout — creates a Stripe Checkout session for the company
     to subscribe to a plan, returns the URL the frontend redirects to.
  2. POST /portal — creates a Stripe Billing Portal session so the
     customer can manage their subscription/payment method themselves.
  3. POST /webhook — Stripe calls this when checkout completes or a
     subscription changes/cancels. This is what actually upgrades or
     downgrades the Company's plan_tier in the database — never trust
     the frontend to tell you payment succeeded, only the webhook.
"""

import uuid
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.models.company import Company, PlanTier
from app.models.invoice import Invoice
from app.api.routes.company_routes import _get_owned_company_or_404
from app.services import billing_service
from fastapi.responses import Response

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    company_id: uuid.UUID
    plan: PlanTier
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    company_id: uuid.UUID
    return_url: str


@router.post("/checkout")
def create_checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_owned_company_or_404(db, payload.company_id, current_user.id)

    customer_id = billing_service.get_or_create_stripe_customer(
        company_id=str(company.id),
        company_name=company.name,
        owner_email=current_user.email,
        existing_customer_id=company.stripe_customer_id,
    )
    if not company.stripe_customer_id:
        company.stripe_customer_id = customer_id
        db.commit()

    try:
        checkout_url = billing_service.create_checkout_session(
            company_id=str(company.id),
            customer_id=customer_id,
            plan=payload.plan,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {e.user_message or str(e)}")

    return {"checkout_url": checkout_url}


@router.post("/portal")
def create_portal(
    payload: PortalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_owned_company_or_404(db, payload.company_id, current_user.id)
    if not company.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This company has no billing account yet.")

    try:
        portal_url = billing_service.create_billing_portal_session(
            customer_id=company.stripe_customer_id,
            return_url=payload.return_url,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {e.user_message or str(e)}")

    return {"portal_url": portal_url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = billing_service.construct_webhook_event(payload, sig_header)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data)

    return {"received": True}


def _handle_checkout_completed(db: Session, session_obj: dict) -> None:
    company_id = session_obj.get("metadata", {}).get("company_id")
    plan = session_obj.get("metadata", {}).get("plan")
    subscription_id = session_obj.get("subscription")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return

    company.stripe_subscription_id = subscription_id
    if plan:
        company.plan_tier = PlanTier(plan)
        plan_config = billing_service.PLAN_CATALOG.get(PlanTier(plan), {})
        company.monthly_minutes_limit = plan_config.get("monthly_minutes_limit", company.monthly_minutes_limit)

        # Record the payment as an Invoice so the owner can download a PDF receipt.
        amount_total = session_obj.get("amount_total")  # Stripe sends this in cents
        invoice = Invoice(
            company_id=company.id,
            plan=plan,
            amount=(amount_total / 100) if amount_total else plan_config.get("_display_amount", 0),
            currency=session_obj.get("currency", "usd"),
            stripe_session_id=session_obj.get("id"),
            stripe_subscription_id=subscription_id,
        )
        db.add(invoice)

    db.commit()


def _handle_subscription_updated(db: Session, subscription_obj: dict) -> None:
    subscription_id = subscription_obj.get("id")
    company = db.query(Company).filter(Company.stripe_subscription_id == subscription_id).first()
    if not company:
        return

    price_id = subscription_obj["items"]["data"][0]["price"]["id"] if subscription_obj.get("items", {}).get("data") else None
    plan = billing_service.plan_for_price_id(price_id) if price_id else None
    if plan:
        company.plan_tier = plan
        plan_config = billing_service.PLAN_CATALOG.get(plan, {})
        company.monthly_minutes_limit = plan_config.get("monthly_minutes_limit", company.monthly_minutes_limit)
        db.commit()


def _handle_subscription_deleted(db: Session, subscription_obj: dict) -> None:
    subscription_id = subscription_obj.get("id")
    company = db.query(Company).filter(Company.stripe_subscription_id == subscription_id).first()
    if not company:
        return

    company.plan_tier = PlanTier.free
    company.stripe_subscription_id = None
    company.monthly_minutes_limit = billing_service.FREE_TIER_LIMITS["monthly_minutes_limit"]
    db.commit()


@router.get("/invoices")
def list_invoices(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    invoices = db.query(Invoice).filter(Invoice.company_id == company_id).order_by(Invoice.created_at.desc()).all()
    return [{"id": i.id, "plan": i.plan, "amount": i.amount, "currency": i.currency, "created_at": i.created_at} for i in invoices]


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    company = _get_owned_company_or_404(db, invoice.company_id, current_user.id)

    from app.services.invoice_pdf_service import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(invoice, company.name, current_user.email)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{str(invoice.id)[:8]}.pdf"},
    )


@router.get("/plans")
def list_plans():
    """Public endpoint — powers the pricing page. No auth required."""
    return {
        "free": {"display_price": "$0/month", **billing_service.FREE_TIER_LIMITS},
        **{plan.value: config for plan, config in billing_service.PLAN_CATALOG.items()},
    }
