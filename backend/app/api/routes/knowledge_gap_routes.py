"""
    api/routes/knowledge_gap_routes.py
 
    Exposes knowledge gaps discovered by the RAG confidence system -
    real customer questions the agent couldn't confidently answer.
"""
 
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
 
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.unanswered_question import UnansweredQuestion
from app.api.routes.company_routes import _get_owned_company_or_404
 
router = APIRouter(prefix="/api/v1/knowledge-gaps", tags=["knowledge-gaps"])
 
 
@router.get("")
def list_gaps(
        company_id: uuid.UUID,
        include_resolved: bool = False,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        _get_owned_company_or_404(db, company_id, current_user.id)
        q = db.query(UnansweredQuestion).filter(UnansweredQuestion.company_id == company_id)
        if not include_resolved:
            q = q.filter(UnansweredQuestion.resolved == False)  # noqa: E712
        gaps = q.order_by(UnansweredQuestion.occurrence_count.desc()).all()
        return [
            {
                "id": g.id, "question": g.question, "occurrence_count": g.occurrence_count,
                "resolved": g.resolved, "first_seen_at": g.first_seen_at, "last_seen_at": g.last_seen_at,
            }
            for g in gaps
        ]
 
 
@router.patch("/{gap_id}/resolve")
def resolve_gap(
        gap_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        gap = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == gap_id).first()
        if not gap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found.")
        _get_owned_company_or_404(db, gap.company_id, current_user.id)
        gap.resolved = True
        db.commit()
        return {"status": "resolved"}