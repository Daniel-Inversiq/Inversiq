"""
Anomaly detectors — one function per anomaly type.

Each detector:
- Accepts a SQLAlchemy Session and scope parameters (tenant_id, lead_id,
  pipeline_run_id) to narrow the query.
- Returns a list of Anomaly dataclasses — never mutates any row.
- Uses only existing models; no new tables required.

Thresholds are passed explicitly so callers can override defaults at the
endpoint level. No global config state.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun
from .types import Anomaly, AnomalyType, Severity


# ---------------------------------------------------------------------------
# 1. PRICE_DELTA_LARGE
# ---------------------------------------------------------------------------

def detect_price_delta_large(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
    threshold: float = 0.50,
    limit: int = 200,
) -> list[Anomaly]:
    """
    Fire when |actual_price - estimated_price| / estimated_price > threshold.

    Requires both prices to be non-null and estimated_price > 0.
    A 50 % default catches material pricing errors while ignoring minor rounding.
    """
    q = db.query(LeadFeedback).filter(
        LeadFeedback.actual_price.isnot(None),
        LeadFeedback.estimated_price.isnot(None),
    )
    if tenant_id:
        q = q.filter(LeadFeedback.tenant_id == tenant_id)
    if lead_id:
        q = q.filter(LeadFeedback.lead_id == lead_id)
    if pipeline_run_id is not None:
        q = q.filter(LeadFeedback.pipeline_run_id == pipeline_run_id)

    rows = q.order_by(LeadFeedback.created_at.desc()).limit(limit).all()

    anomalies: list[Anomaly] = []
    for fb in rows:
        estimated = float(fb.estimated_price)
        actual = float(fb.actual_price)
        if estimated <= 0:
            continue
        delta_ratio = abs(actual - estimated) / estimated
        if delta_ratio > threshold:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.PRICE_DELTA_LARGE,
                    severity=Severity.HIGH,
                    description=(
                        f"Actual price {actual:.2f} differs from estimate "
                        f"{estimated:.2f} by {delta_ratio * 100:.1f}% "
                        f"(threshold {threshold * 100:.0f}%)."
                    ),
                    context={
                        "actual_price": actual,
                        "estimated_price": estimated,
                        "delta_ratio": round(delta_ratio, 4),
                        "threshold": threshold,
                        "outcome": fb.outcome,
                        "feedback_id": fb.id,
                    },
                    pipeline_run_id=fb.pipeline_run_id,
                    lead_id=fb.lead_id,
                    tenant_id=fb.tenant_id,
                )
            )
    return anomalies


# ---------------------------------------------------------------------------
# 2. FAILED_HIGH_CONFIDENCE
# ---------------------------------------------------------------------------

def detect_failed_high_confidence(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
    confidence_threshold: float = 0.60,
    limit: int = 200,
) -> list[Anomaly]:
    """
    Fire when a run FAILED but reported overall_confidence_score >= threshold.

    A failed run with high confidence is contradictory: either the confidence
    predictor is wrong, or an unexpected external failure occurred after scoring.
    Both warrant investigation.
    """
    q = db.query(PipelineRun).filter(
        PipelineRun.status == "FAILED",
        PipelineRun.overall_confidence_score.isnot(None),
        PipelineRun.overall_confidence_score >= confidence_threshold,
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id)
    if pipeline_run_id is not None:
        q = q.filter(PipelineRun.id == pipeline_run_id)

    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()

    return [
        Anomaly(
            anomaly_type=AnomalyType.FAILED_HIGH_CONFIDENCE,
            severity=Severity.HIGH,
            description=(
                f"Run {run.id} FAILED but had "
                f"overall_confidence_score={run.overall_confidence_score:.2f} "
                f"(label={run.overall_confidence_label!r}). "
                f"Failure step: {run.failure_step!r}, "
                f"error_category: {run.error_category!r}."
            ),
            context={
                "overall_confidence_score": run.overall_confidence_score,
                "overall_confidence_label": run.overall_confidence_label,
                "failure_step": run.failure_step,
                "error_category": run.error_category,
                "confidence_threshold": confidence_threshold,
            },
            pipeline_run_id=run.id,
            lead_id=run.lead_id,
            tenant_id=run.tenant_id,
        )
        for run in runs
    ]


# ---------------------------------------------------------------------------
# 3. MISSING_STEP_OUTPUT
# ---------------------------------------------------------------------------

def detect_missing_step_output(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
    limit: int = 200,
) -> list[Anomaly]:
    """
    Fire when a PipelineStepRun has status=COMPLETED but output_snapshot is null.

    A completed step is expected to have produced (and persisted) an output.
    A null snapshot on a COMPLETED step indicates either a serialisation gap or
    a silent early-return in the step implementation.
    """
    q = (
        db.query(PipelineStepRun)
        .join(PipelineRun, PipelineStepRun.pipeline_run_id == PipelineRun.id)
        .filter(
            PipelineStepRun.status == "COMPLETED",
            PipelineStepRun.output_snapshot.is_(None),
        )
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id)
    if pipeline_run_id is not None:
        q = q.filter(PipelineStepRun.pipeline_run_id == pipeline_run_id)

    steps = q.order_by(PipelineStepRun.id.desc()).limit(limit).all()

    return [
        Anomaly(
            anomaly_type=AnomalyType.MISSING_STEP_OUTPUT,
            severity=Severity.MEDIUM,
            description=(
                f"Step {step.step_name!r} (order={step.step_order}) "
                f"in run {step.pipeline_run_id} completed with no output_snapshot."
            ),
            context={
                "step_name": step.step_name,
                "step_use": step.step_use,
                "step_order": step.step_order,
                "step_contract_version": step.step_contract_version,
                "duration_ms": step.duration_ms,
            },
            pipeline_run_id=step.pipeline_run_id,
            pipeline_step_run_id=step.id,
            # tenant_id / lead_id require joining PipelineRun — omit to keep the
            # query cheap; caller can resolve via pipeline_run_id if needed.
        )
        for step in steps
    ]


# ---------------------------------------------------------------------------
# 4. CONFIDENCE_ABSENT_ON_COMPLETION
# ---------------------------------------------------------------------------

def detect_confidence_absent_on_completion(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
    limit: int = 200,
) -> list[Anomaly]:
    """
    Fire when a run reached COMPLETED with overall_confidence_score = null.

    Every pipeline that includes at least one confidence-reporting step should
    propagate a score. A null score on a completed run indicates either:
    - No step reported confidence (coverage gap in step implementations).
    - The score aggregation step was skipped or errored silently.
    """
    q = db.query(PipelineRun).filter(
        PipelineRun.status == "COMPLETED",
        PipelineRun.overall_confidence_score.is_(None),
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id)
    if pipeline_run_id is not None:
        q = q.filter(PipelineRun.id == pipeline_run_id)

    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()

    return [
        Anomaly(
            anomaly_type=AnomalyType.CONFIDENCE_ABSENT_ON_COMPLETION,
            severity=Severity.LOW,
            description=(
                f"Run {run.id} completed successfully but overall_confidence_score "
                f"is null (pipeline={run.pipeline_name!r}, "
                f"engine_version={run.engine_version!r})."
            ),
            context={
                "pipeline_name": run.pipeline_name,
                "engine_version": run.engine_version,
                "config_hash": run.config_hash,
            },
            pipeline_run_id=run.id,
            lead_id=run.lead_id,
            tenant_id=run.tenant_id,
        )
        for run in runs
    ]


# ---------------------------------------------------------------------------
# 5. REPEATED_FAILURE
# ---------------------------------------------------------------------------

def detect_repeated_failure(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    window_hours: int = 24,
    min_failures: int = 3,
    limit: int = 500,
) -> list[Anomaly]:
    """
    Fire when the same (tenant_id, pipeline_name) pair has >= min_failures
    FAILED runs within the last window_hours hours.

    Identifies systematic breakage rather than isolated one-off errors.
    lead_id / pipeline_run_id filters are intentionally unsupported — this
    detector is inherently tenant-level and cross-run.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)

    q = db.query(PipelineRun).filter(
        PipelineRun.status == "FAILED",
        PipelineRun.created_at >= cutoff,
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)

    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()

    # Group by (tenant_id, pipeline_name).
    from collections import defaultdict
    groups: dict[tuple[str, str], list[PipelineRun]] = defaultdict(list)
    for run in runs:
        groups[(run.tenant_id, run.pipeline_name)].append(run)

    anomalies: list[Anomaly] = []
    for (tid, pipeline_name), group in groups.items():
        if len(group) >= min_failures:
            # Report the most recent run_id as the representative reference.
            representative = group[0]
            # Collect distinct error categories from the group.
            categories = list({r.error_category for r in group if r.error_category})
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.REPEATED_FAILURE,
                    severity=Severity.HIGH,
                    description=(
                        f"Pipeline {pipeline_name!r} for tenant {tid!r} failed "
                        f"{len(group)} times in the last {window_hours}h "
                        f"(threshold {min_failures})."
                    ),
                    context={
                        "pipeline_name": pipeline_name,
                        "failure_count": len(group),
                        "window_hours": window_hours,
                        "min_failures": min_failures,
                        "error_categories": categories,
                        "run_ids": [r.id for r in group],
                    },
                    pipeline_run_id=representative.id,
                    tenant_id=tid,
                )
            )
    return anomalies
