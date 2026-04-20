"""
app/routers/proposed_change_execution_requests.py

Guarded execution request layer — the formal persistence step after apply intent.

Endpoints:
  POST /api/proposed-change-execution-requests/create
  POST /api/proposed-change-execution-requests/validate
  POST /api/proposed-change-execution-requests/block
  POST /api/proposed-change-execution-requests/cancel
  GET  /api/proposed-change-execution-requests
  GET  /api/proposed-change-execution-requests/{change_id}

State machine
─────────────
  requested → validated   (validate; governance still clean)
  requested → blocked     (validate with governance drift, or explicit block)
  validated → blocked     (explicit block)
  requested → cancelled
  validated → cancelled
  blocked   → cancelled

Governance gating (server-side attestation)
───────────────────────────────────────────
  create   — recomputes governance; rejects with 422 if governance is not clean.
             Clean means: attestable + approval_ready + planned +
             no high conflict + not stale/superseded.
  validate — recomputes governance; transitions to validated if still clean,
             or to blocked if governance has drifted.
  block    — no governance recompute; manual signal.
  cancel   — no governance recompute.

This is NOT execution.  No config/rule writes, no rollout scheduler.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_audit_event import ProposedChangeAuditEvent
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.proposal_execution_request import (
    block_execution_request,
    cancel_execution_request,
    create_or_update_execution_request,
    validate_execution_request,
)
from app.services.proposal_governance_attestation import compute_governance_attestation

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/proposed-change-execution-requests",
    tags=["proposed-change-execution-requests"],
)

# ---------------------------------------------------------------------------
# Valid state-machine transitions
# ---------------------------------------------------------------------------

_VALID_BLOCK_FROM: frozenset[str] = frozenset({"requested", "validated"})
_VALID_CANCEL_FROM: frozenset[str] = frozenset({"requested", "validated", "blocked"})

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class _BaseRequest(BaseModel):
    tenant_id: str
    change_id: str


class CreateExecutionRequestPayload(_BaseRequest):
    pass


class ValidateExecutionRequestPayload(_BaseRequest):
    pass


class BlockExecutionRequestPayload(_BaseRequest):
    blocking_reasons: Optional[list[str]] = None


class CancelExecutionRequestPayload(_BaseRequest):
    pass


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _parse_json_field(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def _to_dict(req: ProposedChangeExecutionRequest, *, include_snapshots: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": req.id,
        "tenant_id": req.tenant_id,
        "change_id": req.change_id,
        "apply_intent_id": req.apply_intent_id,
        "scope_type": req.scope_type,
        "scope_id": req.scope_id,
        "status": req.status,
        "change_type": req.change_type,
        "title": req.title,
        "governance_snapshot": _parse_json_field(req.governance_snapshot),
        "blocking_reasons_snapshot": _parse_json_field(req.blocking_reasons_snapshot),
        "has_execution_plan": req.execution_plan_snapshot is not None,
        "has_preflight": req.preflight_snapshot is not None,
        "has_monitoring_plan": req.monitoring_plan_snapshot is not None,
        "created_at": req.created_at,
        "updated_at": req.updated_at,
    }
    if include_snapshots:
        result["proposal_payload"] = _parse_json_field(req.proposal_payload)
        result["apply_intent_snapshot"] = _parse_json_field(req.apply_intent_snapshot)
        result["execution_plan_snapshot"] = _parse_json_field(req.execution_plan_snapshot)
        result["preflight_snapshot"] = _parse_json_field(req.preflight_snapshot)
        result["monitoring_plan_snapshot"] = _parse_json_field(req.monitoring_plan_snapshot)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_review_state(db: Session, tenant_id: str, change_id: str) -> ProposedChangeReviewState:
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
                f"No persisted review state for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return state


def _load_apply_intent(db: Session, tenant_id: str, change_id: str) -> ProposedChangeApplyIntent:
    intent = (
        db.query(ProposedChangeApplyIntent)
        .filter(
            ProposedChangeApplyIntent.tenant_id == tenant_id,
            ProposedChangeApplyIntent.change_id == change_id,
        )
        .first()
    )
    if intent is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No apply intent found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return intent


def _load_execution_request(
    db: Session, tenant_id: str, change_id: str
) -> ProposedChangeExecutionRequest:
    req = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.tenant_id == tenant_id,
            ProposedChangeExecutionRequest.change_id == change_id,
        )
        .first()
    )
    if req is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No execution request found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return req


def _governance_blocks(attestation: dict[str, Any]) -> list[str]:
    """Return blocking reasons; empty list means governance is clean."""
    reasons: list[str] = []
    conflict_status = attestation.get("conflict_status") or {}

    if not attestation.get("attestable"):
        reasons.append(
            f"not attestable: {attestation.get('attestation_summary', 'unknown')}"
        )
        return reasons

    readiness = attestation.get("approval_readiness_status")
    if readiness != "approval_ready":
        reasons.append(f"approval_readiness is '{readiness}'")

    planning = attestation.get("apply_planning_status")
    if planning != "planned":
        reasons.append(f"apply_planning is '{planning}'")

    staleness = attestation.get("staleness_status")
    if staleness in ("stale", "superseded"):
        reasons.append(f"proposal staleness is '{staleness}'")

    if conflict_status.get("has_high_conflict"):
        reasons.append("proposal has a high-severity conflict")

    return reasons


def _write_execution_audit(
    db: Session,
    *,
    req: ProposedChangeExecutionRequest,
    event_type: str,
    previous_status: Optional[str],
    new_status: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    try:
        event = ProposedChangeAuditEvent(
            tenant_id=req.tenant_id,
            change_id=req.change_id,
            scope_type=req.scope_type,
            scope_id=req.scope_id,
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
            "Failed to write execution audit event for change_id=%s", req.change_id
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create")
def create(
    payload: CreateExecutionRequestPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create (or refresh) an execution request for an approved proposal.

    Preconditions (all enforced server-side):
      - Review state exists and is ready_for_apply.
      - An apply intent exists for the proposal.
      - Recomputed governance is clean (approval_ready + planned +
        no high conflict + not stale/superseded).

    Creates the execution request with status=requested.  If a record already
    exists it is refreshed with current snapshots and reset to requested.
    """
    state = _load_review_state(db, payload.tenant_id, payload.change_id)
    if state.status != "ready_for_apply":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot create execution request: proposal status is '{state.status}'. "
                "Requires status='ready_for_apply'."
            ),
        )

    intent = _load_apply_intent(db, payload.tenant_id, payload.change_id)
    if intent.status != "ready_for_apply":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot create execution request: apply intent status is "
                f"'{intent.status}'. Requires an active intent with "
                "status='ready_for_apply'."
            ),
        )

    attestation = compute_governance_attestation(
        db, tenant_id=payload.tenant_id, change_id=payload.change_id
    )
    blocking = _governance_blocks(attestation)
    if blocking:
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot create execution request: governance is not clean. "
                + "; ".join(blocking)
                + "."
            ),
        )

    req = create_or_update_execution_request(
        db, state=state, intent=intent, attestation=attestation
    )
    _write_execution_audit(
        db,
        req=req,
        event_type="execution_request_created",
        previous_status=None,
        new_status="requested",
        metadata={"attested_at": attestation.get("attested_at")},
    )

    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.post("/validate")
def validate(
    payload: ValidateExecutionRequestPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Validate an execution request.

    Recomputes governance server-side.
      - If governance is still clean → transitions requested → validated.
      - If governance has drifted → transitions requested → blocked with
        blocking reasons captured.

    Only valid from status=requested.
    """
    req = _load_execution_request(db, payload.tenant_id, payload.change_id)
    if req.status != "requested":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{req.status}' → 'validated'. "
                "validate is only allowed from 'requested'."
            ),
        )

    attestation = compute_governance_attestation(
        db, tenant_id=payload.tenant_id, change_id=payload.change_id
    )
    blocking = _governance_blocks(attestation)
    previous_status = req.status

    if not blocking:
        validate_execution_request(db, request=req, attestation=attestation)
        new_status = "validated"
        event_type = "execution_request_validated"
        metadata: dict[str, Any] = {"attested_at": attestation.get("attested_at")}
    else:
        block_execution_request(db, request=req, blocking_reasons=blocking)
        new_status = "blocked"
        event_type = "execution_request_blocked"
        metadata = {"blocking_reasons": blocking, "attested_at": attestation.get("attested_at")}

    _write_execution_audit(
        db,
        req=req,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata,
    )

    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.post("/block")
def block(
    payload: BlockExecutionRequestPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Manually block an execution request.

    Captures optional blocking_reasons.  Valid from requested or validated.
    """
    req = _load_execution_request(db, payload.tenant_id, payload.change_id)
    if req.status not in _VALID_BLOCK_FROM:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{req.status}' → 'blocked'. "
                f"block is only allowed from: {sorted(_VALID_BLOCK_FROM)}."
            ),
        )

    previous_status = req.status
    block_execution_request(db, request=req, blocking_reasons=payload.blocking_reasons)

    _write_execution_audit(
        db,
        req=req,
        event_type="execution_request_blocked",
        previous_status=previous_status,
        new_status="blocked",
        metadata=(
            {"blocking_reasons": payload.blocking_reasons}
            if payload.blocking_reasons
            else None
        ),
    )

    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.post("/cancel")
def cancel(
    payload: CancelExecutionRequestPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Cancel an execution request.

    Valid from requested, validated, or blocked.
    """
    req = _load_execution_request(db, payload.tenant_id, payload.change_id)
    if req.status not in _VALID_CANCEL_FROM:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{req.status}' → 'cancelled'. "
                f"cancel is only allowed from: {sorted(_VALID_CANCEL_FROM)}."
            ),
        )

    previous_status = req.status
    cancel_execution_request(db, request=req)

    _write_execution_audit(
        db,
        req=req,
        event_type="execution_request_cancelled",
        previous_status=previous_status,
        new_status="cancelled",
    )

    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.get("")
def list_execution_requests(
    tenant_id: str = Query(..., description="Filter by tenant"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List execution requests for a tenant."""
    q = db.query(ProposedChangeExecutionRequest).filter(
        ProposedChangeExecutionRequest.tenant_id == tenant_id
    )
    if status is not None:
        q = q.filter(ProposedChangeExecutionRequest.status == status)

    items = q.order_by(ProposedChangeExecutionRequest.created_at.desc()).all()
    return {
        "tenant_id": tenant_id,
        "total": len(items),
        "items": [_to_dict(i, include_snapshots=False) for i in items],
    }


@router.get("/{change_id:path}")
def get_execution_request(
    change_id: str,
    tenant_id: str = Query(..., description="Tenant that owns this request"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a single execution request by change_id."""
    req = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.tenant_id == tenant_id,
            ProposedChangeExecutionRequest.change_id == change_id,
        )
        .first()
    )
    if req is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No execution request found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return _to_dict(req, include_snapshots=True)
