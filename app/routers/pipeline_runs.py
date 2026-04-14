"""
Read-only debug surface for PipelineRun execution history.

Endpoints:
  GET /api/pipeline-runs/{id}          — single run + all step details
  GET /api/pipeline-runs               — recent runs, filterable by lead_id
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
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
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }
    if include_steps:
        data["steps"] = [_serialize_step(s) for s in run.steps]
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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
    status: Optional[str] = Query(default=None, description="Filter by status (RUNNING, SUCCEEDED, FAILED)"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List recent PipelineRuns, newest first.

    At least one of lead_id or status should be supplied for useful results,
    but both are optional so operators can do broad sweeps during debugging.
    """
    q = db.query(PipelineRun)
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id)
    if status:
        q = q.filter(PipelineRun.status == status.upper())
    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()
    return {
        "total": len(runs),
        "items": [_serialize_run(r) for r in runs],
    }
