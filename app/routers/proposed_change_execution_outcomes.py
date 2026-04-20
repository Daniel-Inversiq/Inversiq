"""
app/routers/proposed_change_execution_outcomes.py

POST /api/proposed-change-execution-outcomes/record  — record a manual outcome observation
GET  /api/proposed-change-execution-outcomes          — list outcomes for a tenant
GET  /api/proposed-change-execution-outcomes/{change_id}  — get outcome by change_id

Design:
  - POST /record loads the execution request, evaluates observed metrics
    deterministically, persists the outcome, and appends an audit event.
  - One outcome record per (tenant_id, execution_request_id) — re-recording
    overwrites the previous observation.
  - evaluation_status is always server-computed; callers supply outcome_status
    and observed_metrics_snapshot.
  - No actor/permissions layer in v1.
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
from app.models.proposed_change_execution_outcome import ProposedChangeExecutionOutcome
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.services.proposal_execution_outcome import record_execution_outcome

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/proposed-change-execution-outcomes",
    tags=["proposed-change-execution-outcomes"],
)


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class RecordOutcomeRequest(BaseModel):
    tenant_id: str
    execution_request_id: int
    # success | partial | failed
    outcome_status: str
    # {metric: scalar | {value, baseline, direction}}
    observed_metrics_snapshot: dict[str, Any]
    # Optional caller override of expected values
    expected_metrics_snapshot: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _outcome_to_dict(outcome: ProposedChangeExecutionOutcome) -> dict[str, Any]:
    return {
        "id": outcome.id,
        "tenant_id": outcome.tenant_id,
        "execution_request_id": outcome.execution_request_id,
        "change_id": outcome.change_id,
        "scope_type": outcome.scope_type,
        "scope_id": outcome.scope_id,
        "outcome_status": outcome.outcome_status,
        "evaluation_status": outcome.evaluation_status,
        "observed_metrics_snapshot": (
            json.loads(outcome.observed_metrics_snapshot)
            if outcome.observed_metrics_snapshot
            else None
        ),
        "expected_metrics_snapshot": (
            json.loads(outcome.expected_metrics_snapshot)
            if outcome.expected_metrics_snapshot
            else None
        ),
        "deviation_snapshot": (
            json.loads(outcome.deviation_snapshot)
            if outcome.deviation_snapshot
            else None
        ),
        "rollback_triggered": outcome.rollback_triggered,
        "rollback_reason": outcome.rollback_reason,
        "created_at": outcome.created_at,
        "updated_at": outcome.updated_at,
    }


def _write_audit(
    db: Session,
    *,
    outcome: ProposedChangeExecutionOutcome,
    event_type: str,
    previous_evaluation_status: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    try:
        event = ProposedChangeAuditEvent(
            tenant_id=outcome.tenant_id,
            change_id=outcome.change_id,
            scope_type=outcome.scope_type,
            scope_id=outcome.scope_id,
            event_type=event_type,
            previous_status=previous_evaluation_status,
            new_status=outcome.evaluation_status,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
    except Exception:
        _log.exception(
            "Failed to write audit event for outcome change_id=%s", outcome.change_id
        )


# ---------------------------------------------------------------------------
# POST /record
# ---------------------------------------------------------------------------


@router.post("/record")
def record_outcome(
    body: RecordOutcomeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Record a manual post-apply outcome observation.

    Loads the execution request, evaluates observed metrics against the
    monitoring plan, persists the outcome record, and appends an audit event.

    Re-recording an existing outcome (same execution_request_id) overwrites
    the previous observation.
    """
    exec_request = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.tenant_id == body.tenant_id,
            ProposedChangeExecutionRequest.id == body.execution_request_id,
        )
        .first()
    )
    if exec_request is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No execution request found for id={body.execution_request_id}, "
                f"tenant_id='{body.tenant_id}'."
            ),
        )

    # Capture previous evaluation_status for audit (if re-recording)
    existing = (
        db.query(ProposedChangeExecutionOutcome)
        .filter(
            ProposedChangeExecutionOutcome.tenant_id == body.tenant_id,
            ProposedChangeExecutionOutcome.execution_request_id == body.execution_request_id,
        )
        .first()
    )
    previous_evaluation_status = existing.evaluation_status if existing else None
    is_update = existing is not None

    try:
        outcome = record_execution_outcome(
            db,
            execution_request=exec_request,
            outcome_status=body.outcome_status,
            observed_metrics_snapshot=body.observed_metrics_snapshot,
            expected_metrics_snapshot=body.expected_metrics_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    event_type = (
        "execution_outcome_updated" if is_update else "execution_outcome_recorded"
    )
    metadata: dict[str, Any] = {
        "outcome_status": outcome.outcome_status,
        "evaluation_status": outcome.evaluation_status,
        "rollback_triggered": outcome.rollback_triggered,
    }
    if outcome.rollback_triggered:
        event_type = "rollback_triggered"
        metadata["rollback_reason"] = outcome.rollback_reason

    _write_audit(
        db,
        outcome=outcome,
        event_type=event_type,
        previous_evaluation_status=previous_evaluation_status,
        metadata=metadata,
    )

    db.commit()
    db.refresh(outcome)
    return _outcome_to_dict(outcome)


# ---------------------------------------------------------------------------
# GET /  — list outcomes for a tenant
# ---------------------------------------------------------------------------


@router.get("")
def list_outcomes(
    tenant_id: str = Query(..., description="Tenant ID"),
    outcome_status: Optional[str] = Query(None, description="Filter by outcome_status"),
    evaluation_status: Optional[str] = Query(
        None, description="Filter by evaluation_status"
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List all outcome records for a tenant, newest first.

    Optional filters: outcome_status, evaluation_status.
    """
    q = db.query(ProposedChangeExecutionOutcome).filter(
        ProposedChangeExecutionOutcome.tenant_id == tenant_id
    )
    if outcome_status:
        q = q.filter(ProposedChangeExecutionOutcome.outcome_status == outcome_status)
    if evaluation_status:
        q = q.filter(
            ProposedChangeExecutionOutcome.evaluation_status == evaluation_status
        )

    rows = (
        q.order_by(ProposedChangeExecutionOutcome.created_at.desc()).limit(limit).all()
    )
    return {
        "tenant_id": tenant_id,
        "total": len(rows),
        "filters": {
            "outcome_status": outcome_status,
            "evaluation_status": evaluation_status,
        },
        "items": [_outcome_to_dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# GET /{change_id}  — get outcome by change_id
# ---------------------------------------------------------------------------


@router.get("/{change_id}")
def get_outcome_by_change_id(
    change_id: str,
    tenant_id: str = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the outcome record for a specific change_id and tenant.

    Returns the most recent outcome if multiple exist (re-recording is
    one-per-execution-request, so in practice there is at most one).
    """
    outcome = (
        db.query(ProposedChangeExecutionOutcome)
        .filter(
            ProposedChangeExecutionOutcome.tenant_id == tenant_id,
            ProposedChangeExecutionOutcome.change_id == change_id,
        )
        .order_by(ProposedChangeExecutionOutcome.created_at.desc())
        .first()
    )
    if outcome is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No outcome found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return _outcome_to_dict(outcome)
