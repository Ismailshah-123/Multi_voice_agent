"""
api/routes/knowledge_base_routes.py

WHAT THIS FILE DOES:
The API behind the "Upload Documents" step in the product workflow and
the Knowledge Base page in the dashboard. POST /upload does the full
pipeline in one call: save file metadata -> parse text -> chunk -> embed
-> store in this company's Qdrant collection -> mark status completed.

If parsing/embedding fails partway through, the KnowledgeBaseItem is
marked `failed` with the error message saved, instead of leaving it stuck
on `processing` forever with no explanation.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.knowledge_base import KnowledgeBaseItem, ProcessingStatus
from app.api.routes.company_routes import _get_owned_company_or_404
from app.services import document_parser, rag_service

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    company_id: uuid.UUID = Form(...),
    category: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)

    file_type = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()

    kb_item = KnowledgeBaseItem(
        company_id=company_id,
        file_name=file.filename,
        file_type=file_type,
        category=category,
        status=ProcessingStatus.processing,
    )
    db.add(kb_item)
    db.commit()
    db.refresh(kb_item)

    try:
        file_bytes = await file.read()
        text = document_parser.extract_text(file_bytes, file_type)
        if not text.strip():
            raise ValueError("No extractable text found in this file.")

        chunk_count = rag_service.ingest_document(
            company_id=company_id,
            kb_item_id=kb_item.id,
            text=text,
            category=category,
            file_name=file.filename,
        )
        kb_item.status = ProcessingStatus.completed
        kb_item.chunk_count = str(chunk_count)

    except Exception as e:
        kb_item.status = ProcessingStatus.failed
        kb_item.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Upload saved but processing failed: {e}",
        )

    db.commit()
    db.refresh(kb_item)
    return {
        "id": kb_item.id,
        "file_name": kb_item.file_name,
        "status": kb_item.status,
        "chunks_stored": kb_item.chunk_count,
    }


@router.get("")
def list_documents(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_company_or_404(db, company_id, current_user.id)
    items = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.company_id == company_id).all()
    return [
        {
            "id": i.id, "file_name": i.file_name, "file_type": i.file_type,
            "category": i.category, "status": i.status, "chunk_count": i.chunk_count,
            "error_message": i.error_message,
        }
        for i in items
    ]


@router.delete("/{kb_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    kb_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_item = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.id == kb_item_id).first()
    if not kb_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    _get_owned_company_or_404(db, kb_item.company_id, current_user.id)

    rag_service.delete_document(kb_item.company_id, kb_item.id)
    db.delete(kb_item)
    db.commit()


@router.get("/query")
def test_query(
        company_id: uuid.UUID,
        question: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
        _get_owned_company_or_404(db, company_id, current_user.id)
        matches = rag_service.query(company_id, question)
 
        # Also generate the REAL answer your agent would actually speak,
        # using the same path live calls use - so this page shows both
        # the raw retrieval (for debugging) AND the polished final answer.
        generated_answer = rag_service.answer_from_knowledge_base(company_id, question)
 
        return {"matches": matches, "generated_answer": generated_answer}
 
