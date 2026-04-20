"""
app/routers/review_state.py

GET  /api/review-state?pipeline_run_id=...  — fetch current state (default: pending)
POST /api/review-state                      — create or update state (upsert)
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.run_review_state import RunReviewState

router = APIRouter(prefix="/api/review-state", tags=["review-state"])

_VALID_STATUSES = {"pending", "acknowledged", "resolved", "ignored"}


def _to_dict(state: RunReviewState) -> dict[str, Any]:
    return {
        "pipeline_run_id": state.pipeline_run_id,
        "tenant_id": state.tenant_id,
        "status": state.status,
        "note": state.note,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


class ReviewStatePayload(BaseModel):
    pipeline_run_id: int
    tenant_id: str
    status: str
    note: Optional[str] = None


@router.get("")
def get_review_state(
    pipeline_run_id: int = Query(..., description="Pipeline run ID to look up"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the current review state for a pipeline run.

    If no record exists, returns a synthetic default with status ``pending``
    and null timestamps — callers can use this as the authoritative default
    without needing to handle a 404.
    """
    state = (
        db.query(RunReviewState)
        .filter(RunReviewState.pipeline_run_id == pipeline_run_id)
        .first()
    )
    if state is None:
        return {
            "pipeline_run_id": pipeline_run_id,
            "tenant_id": None,
            "status": "pending",
            "note": None,
            "created_at": None,
            "updated_at": None,
        }
    return _to_dict(state)


@router.post("")
def upsert_review_state(
    payload: ReviewStatePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create or update the review state for a pipeline run.

    Acts as an upsert: if a record already exists for ``pipeline_run_id`` it is
    updated in-place; otherwise a new row is created.  ``tenant_id`` from the
    payload is used on create but not overwritten on update — the run's tenant
    is immutable once established.
    """
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{payload.status}'. Valid values: {sorted(_VALID_STATUSES)}",
        )

    state = (
        db.query(RunReviewState)
        .filter(RunReviewState.pipeline_run_id == payload.pipeline_run_id)
        .first()
    )

    if state is None:
        state = RunReviewState(
            pipeline_run_id=payload.pipeline_run_id,
            tenant_id=payload.tenant_id,
            status=payload.status,
            note=payload.note,
        )
        db.add(state)
    else:
        state.status = payload.status
        state.note = payload.note

    db.commit()
    db.refresh(state)
    return _to_dict(state)
