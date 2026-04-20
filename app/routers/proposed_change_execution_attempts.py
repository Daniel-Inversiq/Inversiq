"""
app/routers/proposed_change_execution_attempts.py

Guarded execution runner foundation — first controlled execution lifecycle.

Endpoints:
  POST /api/proposed-change-execution-attempts/create
  POST /api/proposed-change-execution-attempts/start
  POST /api/proposed-change-execution-attempts/complete
  POST /api/proposed-change-execution-attempts/fail
  POST /api/proposed-change-execution-attempts/cancel
  POST /api/proposed-change-execution-attempts/rollback
  GET  /api/proposed-change-execution-attempts
  GET  /api/proposed-change-execution-attempts/{change_id}

State machine
─────────────
  queued  → running     (start, only when preflight passes)
  queued  → cancelled   (cancel)
  running → succeeded   (complete)
  running → failed      (fail)
  running → rolled_back (rollback)
  failed  → rolled_back (rollback)

Execution model (v1)
────────────────────
  - No real config/rule mutations are performed.
  - Execution is a controlled stub; the lifecycle and persistence are real.
  - Outcome recording remains a separate step after completion.
  - Multiple attempts per request are allowed (attempt_number auto-increments).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.proposed_change_audit_event import ProposedChangeAuditEvent
from app.models.proposed_change_execution_attempt import ProposedChangeExecutionAttempt
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.services.proposal_execution_runner import (
    cancel_execution_attempt,
    complete_execution_attempt,
    create_execution_attempt,
    fail_execution_attempt,
    fail_preflight,
    rollback_execution_attempt,
    run_preflight_checks,
    start_execution_attempt,
)

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/proposed-change-execution-attempts",
    tags=["proposed-change-execution-attempts"],
)

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateAttemptPayload(BaseModel):
    tenant_id: str
    execution_request_id: int


class AttemptActionPayload(BaseModel):
    tenant_id: str
    attempt_id: int


class CompleteAttemptPayload(BaseModel):
    tenant_id: str
    attempt_id: int
    execution_result_snapshot: Optional[dict[str, Any]] = None


class FailAttemptPayload(BaseModel):
    tenant_id: str
    attempt_id: int
    failure_reason: Optional[str] = None


class CancelAttemptPayload(BaseModel):
    tenant_id: str
    attempt_id: int


class RollbackAttemptPayload(BaseModel):
    tenant_id: str
    attempt_id: int
    rollback_snapshot: Optional[dict[str, Any]] = None


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


def _attempt_to_dict(
    attempt: ProposedChangeExecutionAttempt,
    *,
    include_snapshots: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": attempt.id,
        "tenant_id": attempt.tenant_id,
        "execution_request_id": attempt.execution_request_id,
        "change_id": attempt.change_id,
        "scope_type": attempt.scope_type,
        "scope_id": attempt.scope_id,
        "status": attempt.status,
        "attempt_number": attempt.attempt_number,
        "failure_reason": attempt.failure_reason,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
        "created_at": attempt.created_at,
        "updated_at": attempt.updated_at,
        "has_preflight_result": attempt.preflight_result_snapshot is not None,
        "has_execution_result": attempt.execution_result_snapshot is not None,
        "has_rollback_snapshot": attempt.rollback_snapshot is not None,
    }
    if include_snapshots:
        result["preflight_result_snapshot"] = _parse_json_field(
            attempt.preflight_result_snapshot
        )
        result["execution_result_snapshot"] = _parse_json_field(
            attempt.execution_result_snapshot
        )
        result["rollback_snapshot"] = _parse_json_field(attempt.rollback_snapshot)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_execution_request(
    db: Session, tenant_id: str, execution_request_id: int
) -> ProposedChangeExecutionRequest:
    req = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.id == execution_request_id,
            ProposedChangeExecutionRequest.tenant_id == tenant_id,
        )
        .first()
    )
    if req is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No execution request found for id={execution_request_id}, "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return req


def _load_attempt(
    db: Session, tenant_id: str, attempt_id: int
) -> ProposedChangeExecutionAttempt:
    attempt = (
        db.query(ProposedChangeExecutionAttempt)
        .filter(
            ProposedChangeExecutionAttempt.id == attempt_id,
            ProposedChangeExecutionAttempt.tenant_id == tenant_id,
        )
        .first()
    )
    if attempt is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No execution attempt found for id={attempt_id}, "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return attempt


def _has_active_attempt(db: Session, execution_request_id: int) -> bool:
    """Return True if a running or queued attempt already exists for the request."""
    return (
        db.query(ProposedChangeExecutionAttempt.id)
        .filter(
            ProposedChangeExecutionAttempt.execution_request_id == execution_request_id,
            ProposedChangeExecutionAttempt.status.in_({"queued", "running"}),
        )
        .first()
        is not None
    )


def _write_attempt_audit(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    event_type: str,
    previous_status: Optional[str],
    new_status: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    try:
        event = ProposedChangeAuditEvent(
            tenant_id=attempt.tenant_id,
            change_id=attempt.change_id,
            scope_type=attempt.scope_type,
            scope_id=attempt.scope_id,
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
            "Failed to write attempt audit event for change_id=%s", attempt.change_id
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create")
def create(
    payload: CreateAttemptPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a queued execution attempt for a validated execution request.

    Preconditions:
      - Execution request exists and belongs to the tenant.
      - Execution request status is 'validated'.
      - No active (queued or running) attempt already exists for this request.
    """
    req = _load_execution_request(db, payload.tenant_id, payload.execution_request_id)
    if req.status != "validated":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot create execution attempt: request status is '{req.status}'. "
                "Requires status='validated'."
            ),
        )
    if _has_active_attempt(db, req.id):
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot create execution attempt: an active (queued or running) "
                "attempt already exists for this request."
            ),
        )

    attempt = create_execution_attempt(db, request=req)
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_created",
        previous_status=None,
        new_status="queued",
        metadata={"execution_request_id": req.id, "attempt_number": attempt.attempt_number},
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.post("/start")
def start(
    payload: AttemptActionPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run preflight checks and transition a queued attempt to running.

    Preflight is evaluated server-side from execution request snapshots.
    If preflight fails the attempt transitions to failed and 422 is returned.

    Only valid from status='queued'.
    """
    attempt = _load_attempt(db, payload.tenant_id, payload.attempt_id)
    if attempt.status != "queued":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{attempt.status}' → 'running'. "
                "start is only allowed from 'queued'."
            ),
        )

    req = _load_execution_request(db, payload.tenant_id, attempt.execution_request_id)
    preflight_result = run_preflight_checks(req)

    previous_status = attempt.status

    if not preflight_result["passed"]:
        fail_preflight(db, attempt=attempt, preflight_result=preflight_result)
        _write_attempt_audit(
            db,
            attempt=attempt,
            event_type="execution_attempt_failed",
            previous_status=previous_status,
            new_status="failed",
            metadata={
                "reason": "preflight_failed",
                "preflight_summary": preflight_result.get("summary"),
            },
        )
        db.commit()
        db.refresh(attempt)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Execution attempt failed preflight: {preflight_result.get('summary')} "
                "Attempt has been transitioned to 'failed'."
            ),
        )

    start_execution_attempt(db, attempt=attempt, preflight_result=preflight_result)
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_started",
        previous_status=previous_status,
        new_status="running",
        metadata={"preflight_summary": preflight_result.get("summary")},
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.post("/complete")
def complete(
    payload: CompleteAttemptPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Transition a running attempt to succeeded.

    An optional execution_result_snapshot can be provided; otherwise a v1 stub
    result is recorded.  No real config mutations are performed.

    Only valid from status='running'.
    """
    attempt = _load_attempt(db, payload.tenant_id, payload.attempt_id)
    if attempt.status != "running":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{attempt.status}' → 'succeeded'. "
                "complete is only allowed from 'running'."
            ),
        )

    previous_status = attempt.status
    complete_execution_attempt(
        db,
        attempt=attempt,
        execution_result=payload.execution_result_snapshot,
    )
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_succeeded",
        previous_status=previous_status,
        new_status="succeeded",
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.post("/fail")
def fail(
    payload: FailAttemptPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Transition a running attempt to failed.

    Only valid from status='running'.
    """
    attempt = _load_attempt(db, payload.tenant_id, payload.attempt_id)
    if attempt.status != "running":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{attempt.status}' → 'failed'. "
                "fail is only allowed from 'running'."
            ),
        )

    previous_status = attempt.status
    fail_execution_attempt(db, attempt=attempt, failure_reason=payload.failure_reason)
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_failed",
        previous_status=previous_status,
        new_status="failed",
        metadata=(
            {"failure_reason": payload.failure_reason} if payload.failure_reason else None
        ),
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.post("/cancel")
def cancel(
    payload: CancelAttemptPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Cancel a queued attempt.

    Only valid from status='queued'.
    """
    attempt = _load_attempt(db, payload.tenant_id, payload.attempt_id)
    if attempt.status != "queued":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{attempt.status}' → 'cancelled'. "
                "cancel is only allowed from 'queued'."
            ),
        )

    previous_status = attempt.status
    cancel_execution_attempt(db, attempt=attempt)
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_cancelled",
        previous_status=previous_status,
        new_status="cancelled",
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.post("/rollback")
def rollback(
    payload: RollbackAttemptPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Transition a running or failed attempt to rolled_back.

    An optional rollback_snapshot can be provided.  No real rollback actions
    are performed in v1; this records intent and state only.

    Valid from status='running' or status='failed'.
    """
    attempt = _load_attempt(db, payload.tenant_id, payload.attempt_id)
    if attempt.status not in {"running", "failed"}:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid transition: '{attempt.status}' → 'rolled_back'. "
                "rollback is only allowed from 'running' or 'failed'."
            ),
        )

    previous_status = attempt.status
    rollback_execution_attempt(
        db,
        attempt=attempt,
        rollback_snapshot=payload.rollback_snapshot,
    )
    _write_attempt_audit(
        db,
        attempt=attempt,
        event_type="execution_attempt_rolled_back",
        previous_status=previous_status,
        new_status="rolled_back",
    )

    db.commit()
    db.refresh(attempt)
    return _attempt_to_dict(attempt)


@router.get("")
def list_attempts(
    tenant_id: str = Query(..., description="Filter by tenant"),
    execution_request_id: Optional[int] = Query(
        None, description="Filter by execution request ID"
    ),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List execution attempts for a tenant, optionally filtered by request or status."""
    q = db.query(ProposedChangeExecutionAttempt).filter(
        ProposedChangeExecutionAttempt.tenant_id == tenant_id
    )
    if execution_request_id is not None:
        q = q.filter(
            ProposedChangeExecutionAttempt.execution_request_id == execution_request_id
        )
    if status is not None:
        q = q.filter(ProposedChangeExecutionAttempt.status == status)

    items = q.order_by(ProposedChangeExecutionAttempt.created_at.desc()).all()
    return {
        "tenant_id": tenant_id,
        "total": len(items),
        "items": [_attempt_to_dict(i, include_snapshots=False) for i in items],
    }


@router.get("/{change_id:path}")
def get_attempts_by_change(
    change_id: str,
    tenant_id: str = Query(..., description="Tenant that owns these attempts"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve all execution attempts for a given change_id."""
    items = (
        db.query(ProposedChangeExecutionAttempt)
        .filter(
            ProposedChangeExecutionAttempt.tenant_id == tenant_id,
            ProposedChangeExecutionAttempt.change_id == change_id,
        )
        .order_by(ProposedChangeExecutionAttempt.attempt_number.asc())
        .all()
    )
    return {
        "tenant_id": tenant_id,
        "change_id": change_id,
        "total": len(items),
        "items": [_attempt_to_dict(i, include_snapshots=True) for i in items],
    }
