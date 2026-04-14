# aether/engine/runner.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .context import EngineContext, PipelineState, StepResult
from .config import EngineConfig
from .registry import StepRegistry


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SNAPSHOT_MAX_KEYS = 20
_SNAPSHOT_MAX_STR_LEN = 400


def _log(state: PipelineState, level: str, msg: str, **fields: Any) -> None:
    state.logs.append(
        {
            "level": level,
            "message": msg,
            "tenant_id": state.context.tenant_id,
            "vertical_id": state.context.vertical_id,
            "lead_id": state.context.lead_id,
            "trace_id": state.context.trace_id,
            **fields,
        }
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lightweight(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a size-capped copy of *data* safe to store as a JSON snapshot."""
    out: Dict[str, Any] = {}
    for k, v in list(data.items())[:_SNAPSHOT_MAX_KEYS]:
        if isinstance(v, str) and len(v) > _SNAPSHOT_MAX_STR_LEN:
            out[k] = v[:_SNAPSHOT_MAX_STR_LEN] + "…"
        elif isinstance(v, (dict, list)):
            out[k] = f"<{type(v).__name__} len={len(v)}>"
        else:
            out[k] = v
    return out


def _parse_error(error: Optional[str]):
    """Split 'ExcType: message' into (error_type, error_message).

    Falls back to (None, error) for plain strings.
    """
    if not error:
        return None, None
    if ": " in error:
        exc_type, _, msg = error.partition(": ")
        # Only treat the prefix as a type if it looks like an identifier
        if exc_type.replace("_", "").isalnum():
            return exc_type, msg
    return None, error


# ---------------------------------------------------------------------------
# DB persistence helpers  (only called when db is not None)
# ---------------------------------------------------------------------------

def _create_pipeline_run(db, context: EngineContext, config: EngineConfig):
    from app.models.pipeline_run import PipelineRun  # lazy import avoids circular dep

    run = PipelineRun(
        tenant_id=context.tenant_id,
        lead_id=context.lead_id,
        vertical_id=context.vertical_id,
        trace_id=context.trace_id,
        pipeline_name=config.vertical_id,
        engine_version=config.version,
        status="RUNNING",
        started_at=_now(),
    )
    db.add(run)
    db.flush()  # populate run.id
    return run


def _create_step_run(db, pipeline_run_id: int, step_cfg, step_order: int, input_snap: dict):
    from app.models.pipeline_run import PipelineStepRun

    step_run = PipelineStepRun(
        pipeline_run_id=pipeline_run_id,
        step_name=step_cfg.id,
        step_order=step_order,
        status="RUNNING",
        input_snapshot=input_snap,
        started_at=_now(),
    )
    db.add(step_run)
    db.flush()
    return step_run


def _finish_step_run(step_run, result: StepResult, duration_ms: int) -> None:
    step_run.status = result.status
    step_run.duration_ms = duration_ms
    step_run.completed_at = _now()
    step_run.output_snapshot = _lightweight(result.data or {})
    if result.status == "FAILED":
        step_run.error_type, step_run.error_message = _parse_error(result.error)


def _finish_pipeline_run(pipeline_run, state: PipelineState, db) -> None:
    # Map engine status → DB status
    if state.status == "SUCCEEDED":
        pipeline_run.status = "COMPLETED"
    else:
        pipeline_run.status = state.status  # FAILED | NEEDS_REVIEW

    pipeline_run.completed_at = _now()
    if state.failure_step:
        pipeline_run.failure_step = state.failure_step
    db.commit()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_pipeline(
    context: EngineContext,
    config: EngineConfig,
    registry: StepRegistry,
    assets: Dict[str, Any],
    initial_data: Optional[Dict[str, Any]] = None,
    db=None,  # Optional[sqlalchemy.orm.Session] — kept untyped to avoid hard dep
) -> PipelineState:
    state = PipelineState(context=context, data=initial_data or {})

    _log(state, "info", "pipeline_start", config_version=config.version)

    # Create PipelineRun record when a DB session is provided
    pipeline_run = _create_pipeline_run(db, context, config) if db is not None else None

    for step_order, step_cfg in enumerate(config.steps):
        _log(state, "info", "step_start", step_id=step_cfg.id, step_use=step_cfg.use)

        step_start_ms = time.monotonic()

        step_run = None
        if pipeline_run is not None:
            input_snap = _lightweight(state.data)
            step_run = _create_step_run(db, pipeline_run.id, step_cfg, step_order, input_snap)

        try:
            step_fn = registry.get(step_cfg.use)
            result: StepResult = step_fn(state, step_cfg, assets)

        except Exception as e:
            _log(
                state,
                "error",
                "step_exception",
                step_id=step_cfg.id,
                step_use=step_cfg.use,
                exc=f"{type(e).__name__}: {e}",
            )
            result = StepResult(status="FAILED", error=f"{type(e).__name__}: {e}")

        duration_ms = int((time.monotonic() - step_start_ms) * 1000)

        _log(
            state,
            "info" if result.status == "OK" else "warning",
            "step_end",
            step_id=step_cfg.id,
            status=result.status,
            error=result.error,
            meta=result.meta,
        )

        state.data.setdefault("steps", {})
        state.data["steps"][step_cfg.id] = result.data or {}

        if step_run is not None:
            _finish_step_run(step_run, result, duration_ms)

        if result.status == "FAILED":
            state.status = "FAILED"
            state.failure_step = step_cfg.id
            if step_cfg.on_fail == "CONTINUE":
                _log(state, "warning", "step_failed_continue", step_id=step_cfg.id)
                continue
            _log(state, "error", "pipeline_failed", failure_step=step_cfg.id)
            if pipeline_run is not None:
                _finish_pipeline_run(pipeline_run, state, db)
            return state

        if result.status == "NEEDS_REVIEW":
            state.status = "NEEDS_REVIEW"
            state.failure_step = step_cfg.id
            if step_cfg.on_needs_review == "CONTINUE":
                _log(
                    state, "warning", "step_needs_review_continue", step_id=step_cfg.id
                )
                continue
            _log(state, "warning", "pipeline_needs_review", review_step=step_cfg.id)
            if pipeline_run is not None:
                _finish_pipeline_run(pipeline_run, state, db)
            return state

    state.status = "SUCCEEDED"
    _log(state, "info", "pipeline_succeeded")
    if pipeline_run is not None:
        _finish_pipeline_run(pipeline_run, state, db)
    return state
