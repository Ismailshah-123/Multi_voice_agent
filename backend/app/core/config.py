"""
core/config.py

WHAT THIS FILE DOES:
Central configuration for the entire backend. Every environment variable
(database URL, API keys for Vapi/Groq/OpenAI, OAuth credentials for
Google/Microsoft, WhatsApp, Twilio, Stripe, JWT secret) is loaded here ONCE
using pydantic-settings. Every other file imports `settings` from here
instead of calling os.getenv() directly. This is the standard pattern for
production FastAPI apps because:
  1. It validates required env vars at startup (app crashes immediately
     with a clear error if a key is missing, instead of failing randomly
     at runtime deep inside a request).
  2. It gives you autocomplete + type safety everywhere you use settings.
  3. It's the single source of truth for config, which matters a lot once
     you have multiple environments (local, staging, production).
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ---- App ----
    PROJECT_NAME: str = "AI Voice Agent Platform"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"

    # Public URL of THIS backend (e.g. your Render URL). Required so Vapi
    # knows where to POST function-call and end-of-call webhooks. Must be
    # a URL reachable from the internet, not localhost, once deployed.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ---- Database ----
    DATABASE_URL: str

    # ---- Redis / Celery (background jobs: embeddings, call summaries) ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- Auth ----
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ---- Voice Engine (Vapi) ----
    VAPI_API_KEY: str
    VAPI_PUBLIC_KEY: str = ""  # used ONLY by the browser widget (safe to expose client-side), different from VAPI_API_KEY
    VAPI_ORG_ID: str = ""
    VAPI_BASE_URL: str = "https://api.vapi.ai"
    # Phone number ID (from Vapi dashboard) to call FROM for outbound
    # cold-calling campaigns. Provision a number in Vapi first, then
    # paste its ID here. Not required for inbound-only usage.
    VAPI_OUTBOUND_PHONE_NUMBER_ID: str = ""
    # Shared secret you set when configuring the assistant's server URL in
    # Vapi — used to verify incoming webhooks actually came from Vapi, not
    # a spoofed request. See webhook_routes.py.
    VAPI_WEBHOOK_SECRET: str = ""

    # ---- AI Providers ----
    GROQ_API_KEY: str = ""
    # No longer required — embeddings now run locally and free via
    # sentence-transformers (see services/embedding_service.py). Left
    # here only in case you want to swap back to OpenAI for something else.
    OPENAI_API_KEY: str = ""

    # ---- Telephony (fallback / number provisioning) ----
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""

    # ---- Google (Gmail + Calendar) ----
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/google/callback"

    # ---- Microsoft (Outlook + Calendar) ----
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/microsoft/callback"

    # ---- WhatsApp Business ----
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ---- Billing ----
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # ---- Vector DB (RAG knowledge base) ----
    # Empty by default -> rag_service.py falls back to local on-disk Qdrant
    # (./qdrant_data), so RAG works out of the box with zero external
    # services. Set this to a real Qdrant Cloud/self-hosted URL for
    # production (recommended once you have concurrent users, since local
    # file-mode Qdrant only supports one process at a time).
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # ---- CORS ----
    ALLOWED_ORIGINS: str = "http://localhost:8501,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @model_validator(mode="after")
    def _production_safety_checks(self):
        """Fail fast at startup if production is configured unsafely."""
        if self.ENVIRONMENT.lower() == "production":
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be a random string of at least 32 characters in production.")
            if "*" in self.allowed_origins_list:
                raise ValueError("ALLOWED_ORIGINS cannot contain '*' in production (credentials are enabled).")
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Cached so the .env file is only parsed once per process, not on every
    request. Import this function (or the `settings` instance below)
    wherever you need config.
    """
    return Settings()


settings = get_settings()
