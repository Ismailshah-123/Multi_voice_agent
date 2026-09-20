"""
models/knowledge_base.py

WHAT THIS FILE DOES:
Defines the `KnowledgeBaseItem` table — tracks every document (PDF, CSV,
website, FAQ, menu, price list) a company uploads. The actual text
content is chunked and embedded into Qdrant (vector DB) by
services/rag_service.py; this table just tracks the source file metadata
and processing status, and stores the Qdrant collection name so queries
stay scoped to one company only.

This is what makes RAG "no mixing between customers": every company gets
its own Qdrant collection named `kb_{company_id}`, and the agent's
prompt/action handler only ever queries its own company's collection.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)   # "pdf" | "csv" | "docx" | "url" | "faq"
    source_url = Column(String, nullable=True)   # for "url" type or stored file location (S3/R2 key)
    category = Column(String, nullable=True)     # "menu", "policies", "insurance", etc.

    status = Column(SAEnum(ProcessingStatus), default=ProcessingStatus.pending)
    chunk_count = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="knowledge_base_items")
