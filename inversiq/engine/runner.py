# inversiq/engine/runner.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog as _structlog

from .context import ConfidenceResult, EngineContext, PipelineState, StepResult, confidence_label
from .config import EngineConfig
from .registry import StepRegistry

# Structured logger for engine execution — emits JSON to stdout via structlog.
# Bound context (trace_id, tenant_id, etc.) is added per log call, not globally,
# so concurrent pipeline runs don't bleed context into each other.
_engine_log = _structlog.get_logger("inversiq.engine")


def _classify(exc: Exception) -> str:
    """Return the error category string for *exc*.

    Lazily imports app.infra.errors so the engine package stays decoupled
    from the app layer at import time (consistent with the existing lazy
    imports for app.models.pipeline_run).
    """
    try:
        from app.infra.errors import classify_exception  # noqa: PLC0415
        return classify_exception(exc).value
    except Exception:
        return "transient"  # safe default if classifier is unavailable


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SNAPSHOT_MAX_KEYS = 20
_SNAPSHOT_MAX_STR_LEN = 400


def _log(state: PipelineState, level: str, msg: str, **fields: Any) -> None:
    """Append a structured log entry to state.logs AND emit it to structlog stdout."""
    entry = {
        "level": level,
        "message": msg,
        "tenant_id": state.context.tenant_id,
        "vertical_id": state.context.vertical_id,
        "lead_id": state.context.lead_id,
        "trace_id": state.context.trace_id,
        **fields,
    }
    state.logs.append(entry)
    # Emit to the real logger so Cloud Run / log aggregators capture it.
    # Never let a logging failure propagate into the pipeline.
    try:
        emit = getattr(_engine_log, level, _engine_log.info)
        emit(
            msg,
            tenant_id=state.context.tenant_id,
            vertical_id=state.context.vertical_id,
            lead_id=state.context.lead_id,
            trace_id=state.context.trace_id,
            **fields,
        )
    except Exception:
        pass


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
# Metric helpers  (lazy imports — keeps engine decoupled from app layer)
# ---------------------------------------------------------------------------

def _try_record_step(
    pipeline_name: str, step_name: str, tenant_id: str, status: str, duration_ms: int
) -> None:
    try:
        from app.metrics import record_pipeline_step  # noqa: PLC0415
        record_pipeline_step(pipeline_name, step_name, tenant_id, status, duration_ms)
    except Exception:
        pass  # metrics are best-effort; never break the pipeline


def _try_record_pipeline(
    pipeline_name: str, tenant_id: str, status: str, duration_s: float
) -> None:
    try:
        from app.metrics import record_pipeline_run  # noqa: PLC0415
        record_pipeline_run(pipeline_name, tenant_id, status, duration_s)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# EngineEvent emission  (best-effort — never breaks the pipeline)
# ---------------------------------------------------------------------------

def _emit_engine_event(
    db,
    *,
    event_type: str,
    context: EngineContext,
    pipeline_run_id: Optional[int] = None,
    pipeline_step_run_id: Optional[int] = None,
    step_cfg=None,
    status: Optional[str] = None,
    error_category: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Add an EngineEvent row to the current DB transaction.

    Lazy-imports EngineEvent to keep the engine package decoupled from app.
    Never raises — event writes are best-effort and must not break the pipeline.
    All events are flushed / committed by the caller's existing db.commit()
    in _finish_pipeline_run; no extra roundtrip is added here.
    """
    if db is None:
        return
    try:
        from app.models.engine_event import EngineEvent  # noqa: PLC0415
        db.add(EngineEvent(
            event_type=event_type,
            occurred_at=_now(),
            tenant_id=context.tenant_id,
            lead_id=context.lead_id,
            vertical_id=context.vertical_id,
            trace_id=context.trace_id,
            pipeline_run_id=pipeline_run_id,
            pipeline_step_run_id=pipeline_step_run_id,
            step_name=step_cfg.id if step_cfg is not None else None,
            step_use=step_cfg.use if step_cfg is not None else None,
            status=status,
            error_category=error_category,
            payload=payload,
            meta=meta,
        ))
    except Exception:
        pass  # events are best-effort — never break the pipeline


# ---------------------------------------------------------------------------
# DB persistence helpers  (only called when db is not None)
# ---------------------------------------------------------------------------

def _get_contract(step_fn) -> Optional[dict]:
    """Return the step's __step_contract__ dict, or None if absent."""
    return getattr(step_fn, "__step_contract__", None)


def _check_contract(
    state: PipelineState,
    step_cfg,
    result: StepResult,
    contract: Optional[dict],
) -> None:
    """Warn (never block) when a produces key is missing from result.data."""
    if contract is None or result.status == "FAILED":
        return
    produces = contract.get("produces") or []
    missing = [k for k in produces if k not in (result.data or {})]
    if missing:
        _log(
            state,
            "warning",
            "step_contract_violation",
            step_name=step_cfg.id,
            step_use=step_cfg.use,
            missing_keys=missing,
            contract_produces=produces,
        )


def _create_pipeline_run(db, context: EngineContext, config: EngineConfig):
    from app.models.pipeline_run import PipelineRun  # lazy import avoids circular dep

    run = PipelineRun(
        tenant_id=context.tenant_id,
        lead_id=context.lead_id,
        vertical_id=context.vertical_id,
        trace_id=context.trace_id,
        pipeline_name=config.vertical_id,
        engine_version=config.version,
        config_hash=config.config_hash(),
        status="RUNNING",
        started_at=_now(),
    )
    db.add(run)
    db.flush()  # populate run.id
    return run


def _create_step_run(
    db,
    pipeline_run_id: int,
    step_cfg,
    step_order: int,
    input_snap: dict,
    contract: Optional[dict] = None,
):
    from app.models.pipeline_run import PipelineStepRun

    step_run = PipelineStepRun(
        pipeline_run_id=pipeline_run_id,
        step_name=step_cfg.id,
        step_use=step_cfg.use,
        step_order=step_order,
        status="RUNNING",
        input_snapshot=input_snap,
        step_contract_version=(contract or {}).get("version"),
        started_at=_now(),
    )
    db.add(step_run)
    # No flush here: step_run.id is never read after creation.  All step_run
    # attribute updates (_finish_step_run) operate directly on the ORM object,
    # and the INSERT is deferred to the final db.commit() in _finish_pipeline_run.
    # This eliminates one DB roundtrip per pipeline step (typically 6-10 per run).
    return step_run


def _finish_step_run(
    step_run,
    result: StepResult,
    duration_ms: int,
    error_category: Optional[str] = None,
) -> None:
    step_run.status = result.status
    step_run.duration_ms = duration_ms
    step_run.completed_at = _now()
    step_run.output_snapshot = _lightweight(result.data or {})
    if result.status == "FAILED":
        step_run.error_type, step_run.error_message = _parse_error(result.error)
        step_run.error_category = error_category
    if result.confidence is not None:
        step_run.confidence_score = result.confidence.score
        step_run.confidence_label = result.confidence.label
        step_run.confidence_reason = result.confidence.reason


def _finish_pipeline_run(
    pipeline_run,
    state: PipelineState,
    db,
    *,
    error_category: Optional[str] = None,
    step_confidence_scores: Optional[list] = None,
) -> None:
    # Map engine status → DB status
    if state.status == "SUCCEEDED":
        pipeline_run.status = "COMPLETED"
    else:
        pipeline_run.status = state.status  # FAILED | NEEDS_REVIEW

    pipeline_run.completed_at = _now()
    if state.failure_step:
        pipeline_run.failure_step = state.failure_step
    # Denormalise the failing step's error category to the run row so callers
    # can filter for "all transient failures" without joining on steps.
    if error_category is not None:
        pipeline_run.error_category = error_category

    # Propagate overall confidence: weakest-link (min) of all step scores.
    # Null when no step in the run reported a confidence score.
    scores = [s for s in (step_confidence_scores or []) if s is not None]
    if scores:
        overall = min(scores)
        pipeline_run.overall_confidence_score = overall
        pipeline_run.overall_confidence_label = confidence_label(overall)

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
    pipeline_start_ms = time.monotonic()
    # Accumulates confidence scores from every step that provides one.
    # Passed to _finish_pipeline_run for overall (weakest-link) propagation.
    step_confidence_scores: list[Optional[float]] = []

    _log(state, "info", "pipeline_start", config_version=config.version, pipeline_name=config.vertical_id)

    # Create PipelineRun record when a DB session is provided
    pipeline_run = _create_pipeline_run(db, context, config) if db is not None else None

    # pipeline.started — emitted after flush() so pipeline_run.id is populated
    _emit_engine_event(
        db,
        event_type="pipeline.started",
        context=context,
        pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
        status="RUNNING",
        meta={"pipeline_name": config.vertical_id, "engine_version": config.version},
    )

    for step_order, step_cfg in enumerate(config.steps):
        _log(
            state, "info", "step_start",
            step_name=step_cfg.id, step_use=step_cfg.use, step_order=step_order,
        )

        step_start_ms = time.monotonic()

        step_run = None
        # Peek at the contract before entering the try block so we can store
        # step_contract_version on the step_run row up-front.  registry.peek
        # returns None rather than raising, so a misconfigured step key is
        # still caught by registry.get inside the try block below.
        contract = _get_contract(registry.peek(step_cfg.use))

        if pipeline_run is not None:
            input_snap = _lightweight(state.data)
            step_run = _create_step_run(
                db, pipeline_run.id, step_cfg, step_order, input_snap, contract
            )

        # pipeline.step.started — pipeline_step_run_id is None (no flush; see comment
        # on _create_step_run).  pipeline_run_id + step_name is sufficient for correlation.
        _emit_engine_event(
            db,
            event_type="pipeline.step.started",
            context=context,
            pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
            step_cfg=step_cfg,
            status="RUNNING",
        )

        step_error_category: Optional[str] = None

        try:
            step_fn = registry.get(step_cfg.use)
            result: StepResult = step_fn(state, step_cfg, assets)
            _check_contract(state, step_cfg, result, contract)

        except Exception as e:
            step_error_category = _classify(e)
            _log(
                state,
                "error",
                "step_exception",
                step_name=step_cfg.id,
                step_use=step_cfg.use,
                exc=f"{type(e).__name__}: {e}",
                error_category=step_error_category,
            )
            result = StepResult(status="FAILED", error=f"{type(e).__name__}: {e}")

        duration_ms = int((time.monotonic() - step_start_ms) * 1000)

        _log(
            state,
            "info" if result.status == "OK" else "warning",
            "step_end",
            step_name=step_cfg.id,
            status=result.status,
            duration_ms=duration_ms,
            error=result.error,
        )

        # Record per-step Prometheus metric regardless of outcome.
        _try_record_step(
            pipeline_name=context.vertical_id,
            step_name=step_cfg.id,
            tenant_id=context.tenant_id,
            status=result.status,
            duration_ms=duration_ms,
        )

        state.data.setdefault("steps", {})
        state.data["steps"][step_cfg.id] = result.data or {}

        # Collect step confidence score for overall run propagation.
        step_confidence_scores.append(
            result.confidence.score if result.confidence is not None else None
        )

        if step_run is not None:
            _finish_step_run(step_run, result, duration_ms, step_error_category)

        # pipeline.step.{completed,failed,needs_review}
        _emit_engine_event(
            db,
            event_type=(
                "pipeline.step.failed" if result.status == "FAILED"
                else "pipeline.step.needs_review" if result.status == "NEEDS_REVIEW"
                else "pipeline.step.completed"
            ),
            context=context,
            pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
            step_cfg=step_cfg,
            status=(
                result.status if result.status in ("FAILED", "NEEDS_REVIEW", "SKIPPED")
                else "COMPLETED"
            ),
            error_category=step_error_category if result.status == "FAILED" else None,
            payload=(
                {"duration_ms": duration_ms, "error": result.error}
                if result.status == "FAILED"
                else {"duration_ms": duration_ms}
            ),
        )

        if result.status == "FAILED":
            state.status = "FAILED"
            state.failure_step = step_cfg.id
            if step_cfg.on_fail == "CONTINUE":
                _log(state, "warning", "step_failed_continue", step_name=step_cfg.id)
                continue
            _log(state, "error", "pipeline_failed", failure_step=step_cfg.id, error_category=step_error_category)
            _emit_engine_event(
                db,
                event_type="pipeline.failed",
                context=context,
                pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
                step_cfg=step_cfg,
                status="FAILED",
                error_category=step_error_category,
                payload={"failure_step": step_cfg.id},
            )
            if pipeline_run is not None:
                _finish_pipeline_run(
                    pipeline_run, state, db,
                    error_category=step_error_category,
                    step_confidence_scores=step_confidence_scores,
                )
            _try_record_pipeline(
                pipeline_name=context.vertical_id,
                tenant_id=context.tenant_id,
                status="FAILED",
                duration_s=time.monotonic() - pipeline_start_ms,
            )
            return state

        if result.status == "NEEDS_REVIEW":
            state.status = "NEEDS_REVIEW"
            state.failure_step = step_cfg.id
            if step_cfg.on_needs_review == "CONTINUE":
                _log(
                    state, "warning", "step_needs_review_continue", step_name=step_cfg.id
                )
                continue
            _log(state, "warning", "pipeline_needs_review", review_step=step_cfg.id)
            _emit_engine_event(
                db,
                event_type="pipeline.needs_review",
                context=context,
                pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
                step_cfg=step_cfg,
                status="NEEDS_REVIEW",
                payload={"failure_step": step_cfg.id},
            )
            if pipeline_run is not None:
                _finish_pipeline_run(
                    pipeline_run, state, db,
                    step_confidence_scores=step_confidence_scores,
                )
            _try_record_pipeline(
                pipeline_name=context.vertical_id,
                tenant_id=context.tenant_id,
                status="NEEDS_REVIEW",
                duration_s=time.monotonic() - pipeline_start_ms,
            )
            return state

    state.status = "SUCCEEDED"
    _log(state, "info", "pipeline_succeeded", pipeline_name=config.vertical_id)
    _emit_engine_event(
        db,
        event_type="pipeline.completed",
        context=context,
        pipeline_run_id=pipeline_run.id if pipeline_run is not None else None,
        status="COMPLETED",
        meta={"pipeline_name": config.vertical_id},
    )
    if pipeline_run is not None:
        _finish_pipeline_run(
            pipeline_run, state, db,
            step_confidence_scores=step_confidence_scores,
        )
    _try_record_pipeline(
        pipeline_name=context.vertical_id,
        tenant_id=context.tenant_id,
        status="SUCCEEDED",
        duration_s=time.monotonic() - pipeline_start_ms,
    )
    return state
