"""
core/database.py

WHAT THIS FILE DOES:
Sets up the SQLAlchemy database engine, session factory, and the
declarative Base that every model in models/ inherits from. Also provides
`get_db()`, a FastAPI dependency that gives each request its own DB
session and guarantees it's closed afterward (prevents connection leaks,
which is one of the most common production bugs in FastAPI apps).

USAGE in a route:
    from app.core.database import get_db
    from sqlalchemy.orm import Session
    from fastapi import Depends

    @router.get("/agents")
    def list_agents(db: Session = Depends(get_db)):
        return db.query(Agent).all()
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # checks connection is alive before using it (avoids stale-connection errors)
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session per-request, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Creates all tables from models that inherit Base.
    In production you should use Alembic migrations instead of this,
    but it's useful for quick local setup / first run.
    """
    from app.models import user, company, agent, industry_template, call_log, knowledge_base, integration, lead, customer_profile, booking, live_call, campaign, company_member, invoice, prompt_variant, unanswered_question  # noqa
    Base.metadata.create_all(bind=engine)
