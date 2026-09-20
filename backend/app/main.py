"""
main.py

WHAT THIS FILE DOES:
The FastAPI application entrypoint. Wires together every route module,
sets up CORS (so the Streamlit dashboard on a different port/domain can
call this API), configures logging, and runs `init_db()` on startup so
tables exist automatically on first run (swap for Alembic migrations
once you have real production data you can't afford to auto-create over).

RUN LOCALLY:
    uv run uvicorn app.main:app --reload --port 8000

The interactive API docs are then available at http://localhost:8000/docs
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import SessionLocal
from app.templates.industry_templates import seed as seed_industry_templates

from app.api.routes import (
    auth_routes,
    company_routes,
    agent_routes,
    webhook_routes,
    integration_routes,
    knowledge_base_routes,
    billing_routes,
    lead_routes,
    analytics_routes,
    demo_routes,
    live_call_routes,
    vapi_widget_router,
    campaign_routes,
    admin_routes,
    onboarding_routes,
    ab_test_routes,
    knowledge_gap_routes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-tenant AI Voice Agent Platform — create an AI employee for any business in minutes.",
    version="1.0.0",
    docs_url=None if settings.ENVIRONMENT.lower() == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT.lower() == "production" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    logger.info("Starting %s in %s mode", settings.PROJECT_NAME, settings.ENVIRONMENT)
    # NOTE: table creation is now handled by Alembic migrations (run
    # `alembic upgrade head` before starting the app), NOT automatically
    # on startup. This used to call init_db()'s create_all() here, but
    # that silently created tables outside of Alembic's tracking, which
    # then made `alembic upgrade head` fail with "table already exists"
    # the first time someone adopted migrations on an existing database.
    # Alembic is now the single source of truth for schema.
    db = SessionLocal()
    try:
        seed_industry_templates(db)
    finally:
        db.close()
    logger.info("Industry templates seeded.")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health", tags=["system"])
def health_check():
    """Used by uptime monitors / Render health checks."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


app.include_router(auth_routes.router)
app.include_router(company_routes.router)
app.include_router(agent_routes.router)
app.include_router(webhook_routes.router)
app.include_router(integration_routes.router)
app.include_router(knowledge_base_routes.router)
app.include_router(billing_routes.router)
app.include_router(lead_routes.router)
app.include_router(analytics_routes.router)
app.include_router(demo_routes.router)
app.include_router(live_call_routes.router)
app.include_router(vapi_widget_router.router)
app.include_router(campaign_routes.router)
app.include_router(admin_routes.router)
app.include_router(onboarding_routes.router)
app.include_router(ab_test_routes.router)
app.include_router(knowledge_gap_routes.router)
