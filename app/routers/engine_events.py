"""
Read-only debug surface for EngineEvent execution logs.

Endpoints:
  GET /api/engine-events?pipeline_run_id=...   — events for a specific run
  GET /api/engine-events?lead_id=...           — events for a specific lead
  GET /api/engine-events?trace_id=...          — events for a trace

At least one filter is required; results are ordered newest-first.
This surface is debug/inspection-only — no writes, no aggregation.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.engine_event import EngineEvent

router = APIRouter(prefix="/api/engine-events", tags=["engine-events"])


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _serialize_event(ev: EngineEvent) -> dict[str, Any]:
    return {
        "id": ev.id,
        "event_type": ev.event_type,
        "occurred_at": ev.occurred_at,
        "tenant_id": ev.tenant_id,
        "lead_id": ev.lead_id,
        "vertical_id": ev.vertical_id,
        "trace_id": ev.trace_id,
        "pipeline_run_id": ev.pipeline_run_id,
        "pipeline_step_run_id": ev.pipeline_step_run_id,
        "step_name": ev.step_name,
        "step_use": ev.step_use,
        "status": ev.status,
        "error_category": ev.error_category,
        "payload": ev.payload,
        "meta": ev.meta,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("")
def list_engine_events(
    pipeline_run_id: Optional[int] = Query(
        default=None,
        description="Filter by pipeline_run_id",
    ),
    lead_id: Optional[str] = Query(
        default=None,
        description="Filter by lead_id",
    ),
    trace_id: Optional[str] = Query(
        default=None,
        description="Filter by trace_id",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event_type prefix (e.g. 'pipeline.failed' or 'pipeline')",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of results (newest first)",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List recent EngineEvents for debugging pipeline execution.

    At least one of ``pipeline_run_id``, ``lead_id``, or ``trace_id`` must be
    supplied — open-ended scans across all tenants are not allowed.

    Results are ordered by ``occurred_at`` descending (newest first).
    """
    if not any([pipeline_run_id, lead_id, trace_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one filter is required: pipeline_run_id, lead_id, or trace_id.",
        )

    q = db.query(EngineEvent)

    if pipeline_run_id is not None:
        q = q.filter(EngineEvent.pipeline_run_id == pipeline_run_id)
    if lead_id:
        q = q.filter(EngineEvent.lead_id == lead_id)
    if trace_id:
        q = q.filter(EngineEvent.trace_id == trace_id)
    if event_type:
        # Support prefix matching: "pipeline" matches "pipeline.started", etc.
        q = q.filter(EngineEvent.event_type.like(f"{event_type}%"))

    events = q.order_by(EngineEvent.occurred_at.desc()).limit(limit).all()
    return {
        "total": len(events),
        "items": [_serialize_event(e) for e in events],
    }
