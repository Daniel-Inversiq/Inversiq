"""
app/routers/proposed_change_state.py

GET  /api/proposed-change-state?change_id=...&tenant_id=...  — fetch current state (default: pending)
POST /api/proposed-change-state                               — create or update state (upsert)
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

import logging

from app.db import get_db
from app.models.proposed_change_audit_event import ProposedChangeAuditEvent
from app.models.proposed_change_review_state import ProposedChangeReviewState

_audit_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proposed-change-state", tags=["proposed-change-state"])

_VALID_STATUSES = {"pending", "approved", "rejected", "archived", "ready_for_apply"}

_WORKFLOW_PHASE: dict[str, str] = {
    "pending": "review",
    "approved": "review",
    "rejected": "review",
    "archived": "review",
    "ready_for_apply": "apply_intent",
}


def _to_dict(state: ProposedChangeReviewState) -> dict[str, Any]:
    return {
        "change_id": state.change_id,
        "tenant_id": state.tenant_id,
        "scope_type": state.scope_type,
        "scope_id": state.scope_id,
        "category": state.category,
        "change_type": state.change_type,
        "title": state.title,
        "status": state.status,
        "note": state.note,
        "proposal_payload": json.loads(state.proposal_payload) if state.proposal_payload else None,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "workflow_phase": _WORKFLOW_PHASE.get(state.status, "review"),
        "persisted": True,
    }


class ProposedChangeStatePayload(BaseModel):
    tenant_id: str
    change_id: str
    scope_type: str
    scope_id: str
    category: str
    change_type: str
    title: str
    status: str
    note: Optional[str] = None
    proposal_payload: Optional[Any] = None


@router.get("")
def get_proposed_change_state(
    change_id: str = Query(..., description="Stable change ID to look up"),
    tenant_id: str = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the current review state for a proposed change.

    If no record exists, returns a synthetic default with status ``pending``
    and null timestamps so callers never need to handle a 404.
    """
    state = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == tenant_id,
            ProposedChangeReviewState.change_id == change_id,
        )
        .first()
    )
    if state is None:
        return {
            "change_id": change_id,
            "tenant_id": tenant_id,
            "status": "pending",
            "note": None,
            "created_at": None,
            "updated_at": None,
            "workflow_phase": "review",
            "persisted": False,
        }
    return _to_dict(state)


@router.post("")
def upsert_proposed_change_state(
    payload: ProposedChangeStatePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create or update the review state for a proposed change.

    Acts as an upsert: if a record already exists for the (tenant_id, change_id) pair
    it is updated in-place; otherwise a new row is created.  ``tenant_id`` is
    immutable once established — set on create, never overwritten.
    """
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{payload.status}'. Valid values: {sorted(_VALID_STATUSES)}",
        )

    payload_text = (
        json.dumps(payload.proposal_payload) if payload.proposal_payload is not None else None
    )

    state = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == payload.tenant_id,
            ProposedChangeReviewState.change_id == payload.change_id,
        )
        .first()
    )

    if state is None:
        state = ProposedChangeReviewState(
            tenant_id=payload.tenant_id,
            change_id=payload.change_id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            category=payload.category,
            change_type=payload.change_type,
            title=payload.title,
            status=payload.status,
            note=payload.note,
            proposal_payload=payload_text,
        )
        db.add(state)
        db.flush()
        _write_audit_event(
            db,
            state=state,
            event_type="created",
            previous_status=None,
            new_status=payload.status,
            previous_note=None,
            new_note=payload.note,
        )
    else:
        previous_status = state.status
        previous_note = state.note
        state.status = payload.status
        state.note = payload.note
        state.proposal_payload = payload_text

        if previous_status != payload.status:
            _write_audit_event(
                db,
                state=state,
                event_type="status_changed",
                previous_status=previous_status,
                new_status=payload.status,
                previous_note=None,
                new_note=None,
            )
        if previous_note != payload.note:
            _write_audit_event(
                db,
                state=state,
                event_type="note_updated",
                previous_status=None,
                new_status=None,
                previous_note=previous_note,
                new_note=payload.note,
            )

    db.commit()
    db.refresh(state)
    return _to_dict(state)


def _write_audit_event(
    db: Session,
    *,
    state: ProposedChangeReviewState,
    event_type: str,
    previous_status: Optional[str],
    new_status: Optional[str],
    previous_note: Optional[str],
    new_note: Optional[str],
) -> None:
    try:
        event = ProposedChangeAuditEvent(
            tenant_id=state.tenant_id,
            change_id=state.change_id,
            scope_type=state.scope_type,
            scope_id=state.scope_id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            previous_note=previous_note,
            new_note=new_note,
        )
        db.add(event)
    except Exception:
        _audit_log.exception("Failed to write audit event for change_id=%s", state.change_id)
