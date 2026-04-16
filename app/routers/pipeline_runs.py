"""
Read-only debug surface for PipelineRun execution history.

Endpoints:
  GET /api/pipeline-runs/{id}          — single run + all step details
  GET /api/pipeline-runs/{id}/debug    — full debug view: run + steps + events + feedback
  GET /api/pipeline-runs               — recent runs, filterable by lead_id / status
  GET /api/pipeline-runs/failed        — DLQ-light: failed runs with recoverability hint
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.anomaly.engine import run_all as run_anomaly_detectors
from app.anomaly.run_review import compute_run_review
from app.db import get_db
from app.infra.errors import recoverability_hint
from app.models.engine_event import EngineEvent
from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun

router = APIRouter(prefix="/api/pipeline-runs", tags=["pipeline-runs"])


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _serialize_step(step: PipelineStepRun) -> dict[str, Any]:
    return {
        "id": step.id,
        "step_name": step.step_name,
        "step_order": step.step_order,
        "status": step.status,
        "duration_ms": step.duration_ms,
        "started_at": step.started_at,
        "completed_at": step.completed_at,
        "error_type": step.error_type,
        "error_message": step.error_message,
        "error_category": step.error_category,
        # Confidence — null when the step did not report one.
        "confidence_score": step.confidence_score,
        "confidence_label": step.confidence_label,
        "confidence_reason": step.confidence_reason,
        # Snapshots are included so callers can inspect I/O without a replay.
        "input_snapshot": step.input_snapshot,
        "output_snapshot": step.output_snapshot,
    }


def _serialize_run(run: PipelineRun, *, include_steps: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "lead_id": run.lead_id,
        "vertical_id": run.vertical_id,
        "trace_id": run.trace_id,
        "pipeline_name": run.pipeline_name,
        "engine_version": run.engine_version,
        "status": run.status,
        "failure_step": run.failure_step,
        "error_category": run.error_category,
        # Overall confidence — weakest-link min() of step scores; null if none reported.
        "overall_confidence_score": run.overall_confidence_score,
        "overall_confidence_label": run.overall_confidence_label,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }
    if include_steps:
        data["steps"] = [_serialize_step(s) for s in run.steps]
    return data


def _serialize_step_debug(step: PipelineStepRun) -> dict[str, Any]:
    """Extended step serialisation for the debug view — adds step_use and contract version."""
    return {
        **_serialize_step(step),
        "step_use": step.step_use,
        "step_contract_version": step.step_contract_version,
    }


def _serialize_event(event: EngineEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "status": event.status,
        "step_name": event.step_name,
        "step_use": event.step_use,
        "pipeline_step_run_id": event.pipeline_step_run_id,
        "error_category": event.error_category,
        "payload": event.payload,
        "meta": event.meta,
    }


def _serialize_feedback(fb: LeadFeedback) -> dict[str, Any]:
    return {
        "id": fb.id,
        "outcome": fb.outcome,
        "actual_price": float(fb.actual_price) if fb.actual_price is not None else None,
        "estimated_price": float(fb.estimated_price) if fb.estimated_price is not None else None,
        "override_reason": fb.override_reason,
        "notes": fb.notes,
        "created_at": fb.created_at,
    }


def _serialize_failed_run(run: PipelineRun) -> dict[str, Any]:
    """Compact failure summary for the DLQ-light endpoint."""
    # Find the failing step inline — steps are pre-loaded and ordered.
    failing_step = next(
        (s for s in run.steps if s.step_name == run.failure_step),
        None,
    )
    failing_detail: Optional[dict[str, Any]] = None
    if failing_step is not None:
        failing_detail = {
            "step_name": failing_step.step_name,
            "error_type": failing_step.error_type,
            "error_message": failing_step.error_message,
            "error_category": failing_step.error_category,
            "duration_ms": failing_step.duration_ms,
        }

    return {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "lead_id": run.lead_id,
        "vertical_id": run.vertical_id,
        "trace_id": run.trace_id,
        "pipeline_name": run.pipeline_name,
        "engine_version": run.engine_version,
        "failure_step": run.failure_step,
        "error_category": run.error_category,
        # recoverability is the actionable hint: "retryable" | "terminal" | "unknown"
        "recoverability": recoverability_hint(run.error_category),
        "failed_at": run.completed_at,
        "failing_step_detail": failing_detail,
    }


def build_pipeline_run_debug_payload(db: Session, run_id: int) -> dict[str, Any]:
    """
    Shared read-only debug payload for API and internal ops pages.
    """
    run = (
        db.query(PipelineRun)
        .options(selectinload(PipelineRun.steps))
        .filter(PipelineRun.id == run_id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"PipelineRun {run_id} not found")

    events = (
        db.query(EngineEvent)
        .filter(EngineEvent.pipeline_run_id == run_id)
        .order_by(EngineEvent.occurred_at.asc())
        .all()
    )

    feedback_rows = (
        db.query(LeadFeedback)
        .filter(LeadFeedback.pipeline_run_id == run_id)
        .all()
    )

    # Anomalies scoped to this run.  pipeline_run_id narrows 4 of 5 detectors;
    # tenant_id scopes REPEATED_FAILURE (which is inherently tenant-level) so
    # only patterns from the same tenant are surfaced.
    anomalies = run_anomaly_detectors(
        db,
        pipeline_run_id=run_id,
        tenant_id=run.tenant_id,
    )
    anomaly_dicts = [a.to_dict() for a in anomalies]

    review = compute_run_review(
        status=run.status,
        error_category=run.error_category,
        overall_confidence_label=run.overall_confidence_label,
        anomaly_dicts=anomaly_dicts,
    )

    step_statuses = [s.status for s in run.steps]

    return {
        "run": {
            "id": run.id,
            "tenant_id": run.tenant_id,
            "lead_id": run.lead_id,
            "vertical_id": run.vertical_id,
            "trace_id": run.trace_id,
            "pipeline_name": run.pipeline_name,
            "engine_version": run.engine_version,
            "config_hash": run.config_hash,
            "status": run.status,
            "failure_step": run.failure_step,
            "error_category": run.error_category,
            "overall_confidence_score": run.overall_confidence_score,
            "overall_confidence_label": run.overall_confidence_label,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        },
        "steps": [_serialize_step_debug(s) for s in run.steps],
        "events": [_serialize_event(e) for e in events],
        "feedback": [_serialize_feedback(f) for f in feedback_rows] or None,
        "anomalies": anomaly_dicts,
        "review": review,
        "summary": {
            "total_steps": len(run.steps),
            "completed_steps": step_statuses.count("COMPLETED"),
            "failed_steps": step_statuses.count("FAILED"),
            "skipped_steps": step_statuses.count("SKIPPED"),
            "event_count": len(events),
            "has_feedback": len(feedback_rows) > 0,
            "recoverability": recoverability_hint(run.error_category),
            "anomaly_count": len(anomalies),
            "review_recommended": review["review_recommended"],
            "review_priority": review["review_priority"],
        },
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# NOTE: /failed must be declared before /{run_id} so FastAPI doesn't treat
# "failed" as an integer path parameter.
@router.get("/failed")
def list_failed_pipeline_runs(
    tenant_id: Optional[str] = Query(default=None, description="Filter by tenant_id"),
    error_category: Optional[str] = Query(
        default=None,
        description="Filter by error_category (transient|permanent|validation|external_dependency)",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    DLQ-light: list failed pipeline runs with failure detail and recoverability hint.

    Each item includes:
    - ``recoverability``: ``"retryable"`` (transient/external_dependency) or
      ``"terminal"`` (permanent/validation) or ``"unknown"``
    - ``failing_step_detail``: step-level error type, message, and category
    - ``failed_at``: when the run was marked FAILED

    Intended for operational triage — not a replacement for a full DLQ.
    """
    q = (
        db.query(PipelineRun)
        .options(selectinload(PipelineRun.steps))
        .filter(PipelineRun.status == "FAILED")
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    if error_category:
        q = q.filter(PipelineRun.error_category == error_category.lower())
    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()
    return {
        "total": len(runs),
        "items": [_serialize_failed_run(r) for r in runs],
    }


@router.get("/{run_id}/debug")
def get_pipeline_run_debug(
    run_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Full debug view for a single PipelineRun.

    Returns in one response:
    - ``run``      — all run metadata (config_hash, engine_version, confidence, errors)
    - ``steps``    — ordered step history with I/O snapshots, confidence, and step_use
    - ``events``   — EngineEvent rows for this run, chronological (oldest first)
    - ``feedback`` — linked LeadFeedback if any; null otherwise
    - ``summary``  — step/event counts and recoverability hint for quick scanning

    Read-only. Does not trigger re-execution.
    """
    return build_pipeline_run_debug_payload(db, run_id)


@router.get("/{run_id}")
def get_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single PipelineRun by id, including all step details."""
    run = (
        db.query(PipelineRun)
        .options(selectinload(PipelineRun.steps))
        .filter(PipelineRun.id == run_id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"PipelineRun {run_id} not found")
    return _serialize_run(run, include_steps=True)


@router.get("")
def list_pipeline_runs(
    lead_id: Optional[str] = Query(default=None, description="Filter by lead_id"),
    tenant_id: Optional[str] = Query(default=None, description="Filter by tenant_id"),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status (RUNNING, COMPLETED, FAILED, NEEDS_REVIEW)",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List recent PipelineRuns, newest first.

    At least one filter should be supplied for useful results,
    but all are optional so operators can do broad sweeps during debugging.
    """
    q = db.query(PipelineRun)
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id)
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    if status:
        q = q.filter(PipelineRun.status == status.upper())
    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()
    return {
        "total": len(runs),
        "items": [_serialize_run(r) for r in runs],
    }
