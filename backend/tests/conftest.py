"""
tests/conftest.py

WHAT THIS FILE DOES:
Shared pytest fixtures for the whole test suite. Sets a test .env
before any app module is imported, gives each test a fresh isolated
SQLite database, and provides a `db` fixture (direct SQLAlchemy
session, used for unit-testing business logic functions directly) —
this sidesteps a known SQLite limitation with Postgres-native UUID
columns when going through the JWT-authenticated HTTP layer (see
README's "Database" section). Tests here focus on business logic
itself, which is DB-engine agnostic.
"""

import os
import sys
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suite.db")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_pytest")
os.environ.setdefault("VAPI_API_KEY", "test_vapi_key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.core.database import Base, engine, SessionLocal
from app.models import (  # noqa
    user, company, agent, industry_template, call_log, knowledge_base,
    integration, lead, customer_profile, booking, live_call, campaign,
    company_member, invoice, prompt_variant,
)


@pytest.fixture(scope="function")
def db():
    """Fresh tables for every test function, dropped afterward."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def make_user(db):
    def _make(email="test@example.com"):
        from app.models.user import User
        u = User(email=email, hashed_password="hashed")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    return _make


@pytest.fixture
def make_company(db):
    def _make(owner, name="Test Co", industry="restaurant"):
        from app.models.company import Company
        c = Company(owner_id=owner.id, name=name, industry=industry)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c
    return _make


@pytest.fixture
def make_agent(db):
    def _make(company, name="Test Agent", industry_key="restaurant", vapi_assistant_id=None):
        from app.models.agent import Agent, AgentStatus
        a = Agent(
            company_id=company.id, name=name, industry_key=industry_key,
            system_prompt="You are a test agent.",
            vapi_assistant_id=vapi_assistant_id or f"asst_{uuid.uuid4().hex[:8]}",
            status=AgentStatus.deployed,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a
    return _make
