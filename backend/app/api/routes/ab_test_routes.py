"""
api/routes/ab_test_routes.py

WHAT THIS FILE DOES:
Lets a business owner create a second version ("variant B") of an
existing agent's prompt, deploy it as its own separate Vapi assistant
with its own phone number, and compare its conversion rate against the
original over time.

FIXES IN THIS VERSION:
1. Added DELETE endpoint — previously there was no way to remove a bad
   variant once created (e.g. accidental duplicate submissions, wrong
   text pasted into the label field). Garbage data was permanent.
2. Vapi assistant names truncated to stay within the 40-character limit.
3. create_variant now checks for an existing identical label on this
   agent first and returns a clear error instead of silently creating
   a duplicate — this is what was producing the repeated/garbled
   entries in the A/B Testing panel.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.prompt_variant import PromptVariant
from app.api.routes.agent_routes import _get_owned_agent_or_404
from app.services import vapi_service
from app.services.action_schemas import build_vapi_tools
from app.core.config import settings

router = APIRouter(prefix="/api/v1/ab-tests", tags=["ab-tests"])


@router.post("/{agent_id}/variants")
def create_variant(
    agent_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates and deploys a new prompt variant for this agent. Body:
    {"variant_label": "B", "system_prompt": "...modified prompt..."}
    Deploys it as a fully separate Vapi assistant so it can take real
    calls independently of the original.
    """
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)
    variant_label = (payload.get("variant_label") or "B").strip()
    system_prompt = payload.get("system_prompt") or agent.system_prompt

    if not variant_label:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant label cannot be empty.")

    existing = (
        db.query(PromptVariant)
        .filter(PromptVariant.agent_id == agent.id, PromptVariant.variant_label == variant_label)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A variant labeled '{variant_label}' already exists for this agent. Delete it first or use a different label.",
        )

    variant = PromptVariant(agent_id=agent.id, variant_label=variant_label, system_prompt=system_prompt)
    db.add(variant)
    db.commit()
    db.refresh(variant)

    try:
        webhook_url = f"{settings.PUBLIC_BASE_URL}/api/v1/webhooks/vapi"
        tools = build_vapi_tools(agent.enabled_actions or [], server_url=webhook_url)

        suffix = f" (Var {variant_label})"
        variant_name = agent.name[: 40 - len(suffix)] + suffix

        vapi_assistant = vapi_service.create_assistant(
            name=variant_name,
            system_prompt=system_prompt,
            first_message=agent.greeting,
            voice_id=agent.voice_id,
            language=agent.language,
            tools=tools,
        )
        variant.vapi_assistant_id = vapi_assistant["id"]
        db.commit()
    except vapi_service.VapiServiceError as e:
        real_reason = e.response_body or str(e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Variant saved but deployment failed. Vapi said: {real_reason}")

    return {"id": variant.id, "variant_label": variant.variant_label, "vapi_assistant_id": variant.vapi_assistant_id}


@router.get("/{agent_id}/variants")
def list_variants(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)
    variants = db.query(PromptVariant).filter(PromptVariant.agent_id == agent.id).all()

    result = [{
        "id": "original", "variant_label": "Original", "calls_count": None,
        "conversions_count": None, "conversion_rate": None, "system_prompt": agent.system_prompt,
    }]
    for v in variants:
        result.append({
            "id": v.id, "variant_label": v.variant_label, "calls_count": v.calls_count,
            "conversions_count": v.conversions_count, "conversion_rate": v.conversion_rate,
            "system_prompt": v.system_prompt, "phone_number": v.phone_number,
        })
    return result


@router.delete("/{agent_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    agent_id: uuid.UUID,
    variant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a prompt variant — this endpoint was previously missing
    entirely, meaning any bad/duplicate variant was permanently stuck.
    Cleans up its Vapi assistant first (best-effort, ignores errors
    since it may already be gone), then removes the DB row.
    """
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)
    variant = (
        db.query(PromptVariant)
        .filter(PromptVariant.id == variant_id, PromptVariant.agent_id == agent.id)
        .first()
    )
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found.")

    if variant.vapi_assistant_id:
        try:
            vapi_service.delete_assistant(variant.vapi_assistant_id)
        except vapi_service.VapiServiceError:
            pass

    db.delete(variant)
    db.commit()