"""
app/routers/proposed_change_actions.py

Explicit workflow-action endpoints for proposed changes.  These endpoints
drive the deterministic state machine; they do NOT execute or apply changes.

Endpoints:
  POST /api/proposed-change-actions/approve
  POST /api/proposed-change-actions/reject
  POST /api/proposed-change-actions/reopen
  POST /api/proposed-change-actions/mark-ready-for-apply
  POST /api/proposed-change-actions/cancel-ready-for-apply

State machine
─────────────
  pending        → approved, rejected, archived
  approved       → pending, ready_for_apply
  rejected       → pending, archived
  archived       → pending
  ready_for_apply → approved

Governance gating (server-side attestation)
───────────────────────────────────────────
  approve              — server recomputes approval readiness; allows only if
                         attested approval_readiness_status == "approval_ready"
  mark-ready-for-apply — server recomputes apply planning; allows only if
                         attested apply_planning_status == "planned"

The server is the governance source of truth.  Caller-supplied readiness or
planning values in the request body are treated as optional context only and
are not used to gate the action.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.proposed_change_audit_event import ProposedChangeAuditEvent
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.proposal_apply_intent import cancel_apply_intent, create_or_update_apply_intent
from app.services.proposal_governance_attestation import compute_governance_attestation

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proposed-change-actions", tags=["proposed-change-actions"])

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"approved", "rejected", "archived"},
    "approved": {"pending", "rejected", "ready_for_apply"},
    "rejected": {"pending", "archived"},
    "archived": {"pending"},
    "ready_for_apply": {"approved"},
}

_WORKFLOW_PHASE: dict[str, str] = {
    "pending": "review",
    "approved": "review",
    "rejected": "review",
    "archived": "review",
    "ready_for_apply": "apply_intent",
}

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class _BaseActionRequest(BaseModel):
    tenant_id: str
    change_id: str
    note: Optional[str] = None


class ApproveRequest(_BaseActionRequest):
    # Kept for backward compatibility.  Server-side attestation is the
    # authority; this value is ignored for governance enforcement.
    approval_readiness_status: Optional[str] = None


class RejectRequest(_BaseActionRequest):
    pass


class ReopenRequest(_BaseActionRequest):
    pass


class MarkReadyForApplyRequest(_BaseActionRequest):
    # Kept for backward compatibility.  Server-side attestation is the
    # authority; this value is ignored for governance enforcement.
    apply_planning_status: Optional[str] = None


class CancelReadyForApplyRequest(_BaseActionRequest):
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_state(
    db: Session, tenant_id: str, change_id: str
) -> ProposedChangeReviewState:
    state = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == tenant_id,
            ProposedChangeReviewState.change_id == change_id,
        )
        .first()
    )
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No persisted state found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'. "
                "Initialise with POST /api/proposed-change-state before "
                "performing workflow actions."
            ),
        )
    return state


def _validate_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{current}' → '{target}'. "
                f"Allowed from '{current}': {sorted(allowed) or 'none'}."
            ),
        )


def _apply_action(
    db: Session,
    *,
    tenant_id: str,
    change_id: str,
    target_status: str,
    note: Optional[str],
    event_type: str,
    governance_metadata: Optional[dict[str, Any]] = None,
    extra_pre_commit: Optional[Callable[[Session, ProposedChangeReviewState], None]] = None,
) -> dict[str, Any]:
    state = _load_state(db, tenant_id, change_id)
    previous_status = state.status

    _validate_transition(previous_status, target_status)

    state.status = target_status
    if note is not None:
        state.note = note

    _write_audit(
        db,
        state=state,
        event_type=event_type,
        previous_status=previous_status,
        new_status=target_status,
        new_note=note,
        governance_metadata=governance_metadata,
    )

    if extra_pre_commit is not None:
        extra_pre_commit(db, state)

    db.commit()
    db.refresh(state)
    return _to_dict(state)


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
        "workflow_phase": _WORKFLOW_PHASE.get(state.status, "review"),
        "note": state.note,
        "proposal_payload": (
            json.loads(state.proposal_payload) if state.proposal_payload else None
        ),
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def _write_audit(
    db: Session,
    *,
    state: ProposedChangeReviewState,
    event_type: str,
    previous_status: str,
    new_status: str,
    new_note: Optional[str],
    governance_metadata: Optional[dict[str, Any]] = None,
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
            previous_note=None,
            new_note=new_note,
            metadata_json=(
                json.dumps(governance_metadata) if governance_metadata else None
            ),
        )
        db.add(event)
    except Exception:
        _log.exception("Failed to write audit event for change_id=%s", state.change_id)


def _governance_snapshot(attestation: dict[str, Any]) -> dict[str, Any]:
    """Extract a compact governance snapshot for audit metadata."""
    conflict_status = attestation.get("conflict_status") or {}
    return {
        "attested_approval_readiness_status": attestation.get(
            "approval_readiness_status"
        ),
        "attested_apply_planning_status": attestation.get("apply_planning_status"),
        "attested_staleness_status": attestation.get("staleness_status"),
        "attested_has_high_conflict": conflict_status.get("has_high_conflict"),
        "attested_at": attestation.get("attested_at"),
    }


def _write_apply_intent_audit(
    db: Session,
    *,
    state: ProposedChangeReviewState,
    event_type: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
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
            previous_note=None,
            new_note=None,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
    except Exception:
        _log.exception(
            "Failed to write apply intent audit event for change_id=%s",
            state.change_id,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/approve")
def approve(
    payload: ApproveRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Approve a proposed change.

    Server recomputes governance attestation and allows the action only if
    attested approval_readiness_status == 'approval_ready'.
    Only valid from status 'pending'.
    """
    attestation = compute_governance_attestation(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
    )

    if not attestation["attestable"]:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot approve: proposal is not attestable. "
                f"{attestation['attestation_summary']}"
            ),
        )

    if attestation["approval_readiness_status"] != "approval_ready":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot approve: server-side governance attestation shows "
                f"approval_readiness_status is "
                f"'{attestation['approval_readiness_status']}'. "
                "Approval requires approval_readiness_status='approval_ready'."
            ),
        )

    return _apply_action(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
        target_status="approved",
        note=payload.note,
        event_type="approved",
        governance_metadata=_governance_snapshot(attestation),
    )


@router.post("/reject")
def reject(
    payload: RejectRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Reject a proposed change.

    Valid from 'pending' or 'approved'.
    """
    return _apply_action(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
        target_status="rejected",
        note=payload.note,
        event_type="rejected",
    )


@router.post("/reopen")
def reopen(
    payload: ReopenRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Reopen a proposed change back to 'pending'.

    Valid from 'rejected', 'approved', or 'archived'.
    """
    return _apply_action(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
        target_status="pending",
        note=payload.note,
        event_type="reopened",
    )


@router.post("/mark-ready-for-apply")
def mark_ready_for_apply(
    payload: MarkReadyForApplyRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Advance an approved proposal to 'ready_for_apply' (apply-intent state).

    Server recomputes governance attestation and allows the action only if
    attested apply_planning_status == 'planned'.
    Only valid from 'approved'.

    Creates or updates a ProposedChangeApplyIntent record in the same
    transaction as the status transition.
    """
    attestation = compute_governance_attestation(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
    )

    if not attestation["attestable"]:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot mark ready_for_apply: proposal is not attestable. "
                f"{attestation['attestation_summary']}"
            ),
        )

    if attestation["apply_planning_status"] != "planned":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot mark ready_for_apply: server-side governance attestation "
                f"shows apply_planning_status is "
                f"'{attestation['apply_planning_status']}'. "
                "Requires apply_planning_status='planned'."
            ),
        )

    def _persist_intent(db: Session, state: ProposedChangeReviewState) -> None:
        create_or_update_apply_intent(db, state=state, attestation=attestation)
        _write_apply_intent_audit(
            db,
            state=state,
            event_type="apply_intent_created",
            previous_status=None,
            new_status="ready_for_apply",
        )

    return _apply_action(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
        target_status="ready_for_apply",
        note=payload.note,
        event_type="marked_ready_for_apply",
        governance_metadata=_governance_snapshot(attestation),
        extra_pre_commit=_persist_intent,
    )


@router.post("/cancel-ready-for-apply")
def cancel_ready_for_apply(
    payload: CancelReadyForApplyRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Cancel apply intent — revert from 'ready_for_apply' back to 'approved'.

    Only valid from 'ready_for_apply'.

    Cancels the corresponding ProposedChangeApplyIntent record in the same
    transaction as the status transition.
    """
    # Enforce explicit source state — pending→approved is valid in the general
    # machine (used by approve), so we guard the source here.
    state = _load_state(db, payload.tenant_id, payload.change_id)
    if state.status != "ready_for_apply":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{state.status}' → 'approved'. "
                "cancel-ready-for-apply is only valid from 'ready_for_apply'."
            ),
        )

    def _cancel_intent(db: Session, state: ProposedChangeReviewState) -> None:
        cancel_apply_intent(db, state=state)
        _write_apply_intent_audit(
            db,
            state=state,
            event_type="apply_intent_cancelled",
            previous_status="ready_for_apply",
            new_status="cancelled",
        )

    return _apply_action(
        db,
        tenant_id=payload.tenant_id,
        change_id=payload.change_id,
        target_status="approved",
        note=payload.note,
        event_type="cancelled_ready_for_apply",
        extra_pre_commit=_cancel_intent,
    )
