"""
schemas/agent_schemas.py

WHAT THIS FILE DOES:
Request/response models for the Agent Builder — this is the schema
behind the "Create your AI Employee in 60 seconds" form. The user fills
these fields (agent name, industry, company details are pulled from the
Company, voice, language) and hits Deploy; agent_routes.py validates the
request against this schema, then calls prompt_builder + vapi_service to
actually create the live agent.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.agent import AgentStatus


class AgentCreateRequest(BaseModel):
    company_id: uuid.UUID
    name: str = Field(..., examples=["Bella Pizza Order Assistant"])
    industry_key: str = Field(
        ..., examples=["restaurant", "clinic", "hotel", "cold_caller", "custom"],
        description="Use 'custom' with business_description for any business type not covered by a preset industry."
    )
    business_description: str | None = Field(
        None, description="Required when industry_key='custom'. Free-text description of what the business does — Groq generates a tailored prompt and actions from this."
    )
    voice_id: str | None = None
    language: str = "en"
    custom_instructions: str | None = Field(
        None, description="Extra business-specific instructions merged into the base template."
    )
    enabled_actions: list[str] | None = Field(
        None, description="If omitted, defaults to the industry template's default_actions (or AI-suggested actions for custom industries)."
    )


class AgentDeployResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: AgentStatus
    vapi_assistant_id: str | None
    phone_number: str | None
    widget_embed_id: str | None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    industry_key: str
    system_prompt: str
    voice_id: str | None
    language: str
    enabled_actions: list
    status: AgentStatus
    phone_number: str | None
    created_at: datetime
