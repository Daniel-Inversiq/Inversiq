"""
POST /api/leads/{lead_id}/feedback — record outcome data for a lead.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lead_feedback import LeadFeedback

router = APIRouter(prefix="/api/leads", tags=["lead-feedback"])


class FeedbackRequest(BaseModel):
    outcome: str  # "won" or "lost"
    tenant_id: str
    pipeline_run_id: Optional[int] = None
    actual_price: Optional[float] = None
    estimated_price: Optional[float] = None
    override_reason: Optional[str] = None
    notes: Optional[str] = None


@router.post("/{lead_id}/feedback")
def submit_lead_feedback(
    lead_id: str,
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record a won/lost outcome for a lead."""
    if payload.outcome not in ("won", "lost"):
        raise HTTPException(
            status_code=422,
            detail="outcome must be 'won' or 'lost'",
        )

    feedback = LeadFeedback(
        tenant_id=payload.tenant_id,
        lead_id=lead_id,
        pipeline_run_id=payload.pipeline_run_id,
        outcome=payload.outcome,
        actual_price=payload.actual_price,
        estimated_price=payload.estimated_price,
        override_reason=payload.override_reason,
        notes=payload.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {
        "ok": True,
        "id": feedback.id,
        "lead_id": feedback.lead_id,
        "outcome": feedback.outcome,
        "created_at": feedback.created_at,
    }
