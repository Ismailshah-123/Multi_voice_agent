"""
api/routes/agent_routes.py

WHAT THIS FILE DOES:
This is the Agent Builder API — the endpoint behind "Create your AI
Employee in 60 seconds," plus listing, fetching, deleting agents, and
the free text preview-chat testing endpoint.

FIX IN THIS VERSION: delete_agent now cleans up dependent PromptVariant
rows (and their Vapi assistants) BEFORE deleting the agent's own DB
row. Previously it deleted the Vapi assistant first, then tried to
delete the DB row directly — which failed with a foreign key violation
if the agent had any A/B test variants, since those still referenced
it. That left the Vapi assistant already gone but the DB row
permanently stuck (every retry failed the same way). See delete_agent
below for the corrected order.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.agent import Agent, AgentStatus
from app.schemas.agent_schemas import AgentCreateRequest, AgentResponse, AgentDeployResponse
from app.services import prompt_builder, vapi_service, ai_prompt_generator
from app.services.action_schemas import build_vapi_tools
from app.core.config import settings
from app.api.routes.company_routes import _get_owned_company_or_404

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("", response_model=AgentDeployResponse, status_code=status.HTTP_201_CREATED)
def create_and_deploy_agent(
    payload: AgentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_owned_company_or_404(db, payload.company_id, current_user.id)

    if payload.industry_key == "custom":
        if not payload.business_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="business_description is required when industry_key is 'custom'.",
            )
        try:
            ai_config = ai_prompt_generator.generate_agent_config(company.name, payload.business_description)
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI prompt generation failed: {e}")

        system_prompt = ai_config["system_prompt"]
        if payload.custom_instructions:
            system_prompt = f"{system_prompt}\n\nAdditional instructions: {payload.custom_instructions}"
        greeting = ai_config["greeting"]
        enabled_actions = payload.enabled_actions or ai_config["suggested_actions"]
        if "get_caller_history" not in enabled_actions:
            enabled_actions = ["get_caller_history"] + list(enabled_actions)
    else:
        try:
            system_prompt = prompt_builder.build_system_prompt(
                industry_key=payload.industry_key,
                company_name=company.name,
                custom_instructions=payload.custom_instructions,
            )
            greeting = prompt_builder.build_greeting(payload.industry_key, company.name)
            enabled_actions = prompt_builder.resolve_actions(payload.industry_key, payload.enabled_actions)
        except prompt_builder.UnknownIndustryError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    agent = Agent(
        company_id=company.id,
        name=payload.name,
        industry_key=payload.industry_key,
        greeting=greeting,
        system_prompt=system_prompt,
        voice_id=payload.voice_id,
        language=payload.language,
        enabled_actions=enabled_actions,
        status=AgentStatus.deploying,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    try:
        webhook_url = f"{settings.PUBLIC_BASE_URL}/api/v1/webhooks/vapi"
        tools = build_vapi_tools(enabled_actions, server_url=webhook_url, escalation_phone_number=company.escalation_phone_number)

        final_prompt = agent.system_prompt
        if company.escalation_phone_number:
            final_prompt += (
                "\n\nIf you cannot help the caller, if they explicitly ask for a human, or if they seem "
                "frustrated after you've tried to assist, use the transfer_to_human tool to connect them "
                "to a team member. Let them know you're transferring them first."
            )

        vapi_assistant = vapi_service.create_assistant(
            name=agent.name,
            system_prompt=final_prompt,
            first_message=agent.greeting,
            voice_id=agent.voice_id,
            language=agent.language,
            tools=tools,
        )
        agent.vapi_assistant_id = vapi_assistant["id"]
        agent.status = AgentStatus.deployed
    except vapi_service.VapiServiceError as e:
        agent.status = AgentStatus.failed
        db.commit()
        real_reason = e.response_body or str(e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent saved but deployment to the voice engine failed. Vapi said: {real_reason}",
        )

    db.commit()
    db.refresh(agent)
    return agent


@router.get("", response_model=list[AgentResponse])
def list_agents(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    return db.query(Agent).filter(Agent.company_id == company_id).all()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an agent and everything that depends on it, in the correct
    order: dependent PromptVariant rows (and their Vapi assistants)
    FIRST — best-effort, errors ignored since a resource being "already
    gone" during cleanup is fine — THEN the agent's own Vapi assistant,
    THEN the agent's DB row last. This order is what avoids the foreign
    key violation that used to leave deleted agents permanently stuck.
    """
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)

    from app.models.prompt_variant import PromptVariant
    variants = db.query(PromptVariant).filter(PromptVariant.agent_id == agent.id).all()
    for variant in variants:
        if variant.vapi_assistant_id:
            try:
                vapi_service.delete_assistant(variant.vapi_assistant_id)
            except vapi_service.VapiServiceError:
                pass  # already gone or never fully deployed — fine, continue cleanup
        db.delete(variant)
    db.commit()

    if agent.vapi_assistant_id:
        try:
            vapi_service.delete_assistant(agent.vapi_assistant_id)
        except vapi_service.VapiServiceError:
            pass  # proceed with local deletion even if remote cleanup fails

    db.delete(agent)
    db.commit()


@router.post("/{agent_id}/preview-chat")
def preview_chat(
    agent_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test this agent's conversation via free text chat (Groq), without
    spending any Vapi call minutes. Body: {"message": str, "history": [{"role":..., "content":...}]}
    """
    agent = _get_owned_agent_or_404(db, agent_id, current_user.id)

    from app.services.preview_chat_service import send_preview_message

    message = payload.get("message", "")
    history = payload.get("history", [])
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message is required.")

    try:
        reply = send_preview_message(agent.system_prompt, history, message)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return {"reply": reply}


def _get_owned_agent_or_404(db: Session, agent_id: uuid.UUID, owner_id: uuid.UUID) -> Agent:
    from app.models.company import Company
    agent = (
        db.query(Agent)
        .join(Company, Agent.company_id == Company.id)
        .filter(Agent.id == agent_id, Company.owner_id == owner_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return agent