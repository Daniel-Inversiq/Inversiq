"""
app/intelligence/detectors.py

Rule-based signal detectors — one function per SignalType.

Each detector:
- Accepts a SQLAlchemy Session and scope/threshold parameters.
- Returns a list of RuleSignal dataclasses — never mutates any row.
- Aggregates across multiple records (trend signals, not per-record anomalies).
- Groups by tenant_id so a single call without tenant_id returns signals for
  every qualifying tenant in the result set.

Thresholds are passed explicitly so callers can override defaults at the
endpoint level.  No global config state.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun
from app.intelligence.types import RuleSignal, Severity, SignalType


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cutoff(lookback_days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=lookback_days)


# ---------------------------------------------------------------------------
# 1. LIKELY_UNDERPRICING
# ---------------------------------------------------------------------------

def detect_underpricing(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    min_sample: int = 5,
    threshold: float = 0.10,
    min_fraction: float = 0.60,
) -> list[RuleSignal]:
    """
    Emit when the business consistently wins deals where actual_price is
    materially below the engine's estimated_price.

    Pattern: ≥ min_fraction of won feedback records (with both prices, in
    lookback window) have actual_price < estimated_price × (1 − threshold).

    Interpretation: The engine over-estimates; the business discounts to win
    and is leaving margin on the table.
    """
    cut = _cutoff(lookback_days)
    q = db.query(LeadFeedback).filter(
        LeadFeedback.outcome == "won",
        LeadFeedback.actual_price.isnot(None),
        LeadFeedback.estimated_price.isnot(None),
        LeadFeedback.created_at >= cut,
    )
    if tenant_id:
        q = q.filter(LeadFeedback.tenant_id == tenant_id)

    rows = [r for r in q.all() if float(r.estimated_price or 0) > 0]

    # Group by tenant
    by_tenant: dict[str, list] = defaultdict(list)
    for r in rows:
        by_tenant[r.tenant_id].append(r)

    signals: list[RuleSignal] = []
    for tid, t_rows in by_tenant.items():
        if len(t_rows) < min_sample:
            continue
        low_count = sum(
            1 for r in t_rows
            if float(r.actual_price) < float(r.estimated_price) * (1.0 - threshold)
        )
        fraction = low_count / len(t_rows)
        if fraction < min_fraction:
            continue

        avg_actual = sum(float(r.actual_price) for r in t_rows) / len(t_rows)
        avg_estimated = sum(float(r.estimated_price) for r in t_rows) / len(t_rows)
        signals.append(
            RuleSignal(
                signal_type=SignalType.LIKELY_UNDERPRICING,
                severity=Severity.MEDIUM,
                description=(
                    f"{fraction:.0%} of won deals have actual_price more than "
                    f"{threshold:.0%} below the engine estimate across "
                    f"{len(t_rows)} samples — pricing may be too conservative."
                ),
                suggested_action=(
                    "Review pricing model calibration. "
                    f"Actual prices averaged {avg_actual:.2f} vs estimates of "
                    f"{avg_estimated:.2f} on won deals. "
                    "Consider raising base estimates and validating with a small "
                    "price-increase test."
                ),
                context={
                    "sample_count": len(t_rows),
                    "underpriced_count": low_count,
                    "underpriced_fraction": round(fraction, 4),
                    "threshold": threshold,
                    "min_fraction": min_fraction,
                    "avg_actual_price": round(avg_actual, 2),
                    "avg_estimated_price": round(avg_estimated, 2),
                    "lookback_days": lookback_days,
                },
                tenant_id=tid,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# 2. LIKELY_OVERPRICING
# ---------------------------------------------------------------------------

def detect_overpricing(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    min_sample: int = 5,
    loss_rate_threshold: float = 0.60,
) -> list[RuleSignal]:
    """
    Emit when the overall loss rate (lost / total outcomes) exceeds the
    threshold across a sufficient feedback sample.

    A high loss rate is the primary aggregate indicator of systematic
    overpricing relative to the market.
    """
    cut = _cutoff(lookback_days)
    q = db.query(LeadFeedback).filter(
        LeadFeedback.outcome.in_(["won", "lost"]),
        LeadFeedback.created_at >= cut,
    )
    if tenant_id:
        q = q.filter(LeadFeedback.tenant_id == tenant_id)

    rows = q.all()

    by_tenant: dict[str, list] = defaultdict(list)
    for r in rows:
        by_tenant[r.tenant_id].append(r)

    signals: list[RuleSignal] = []
    for tid, t_rows in by_tenant.items():
        if len(t_rows) < min_sample:
            continue
        lost_count = sum(1 for r in t_rows if r.outcome == "lost")
        loss_rate = lost_count / len(t_rows)
        if loss_rate < loss_rate_threshold:
            continue

        signals.append(
            RuleSignal(
                signal_type=SignalType.LIKELY_OVERPRICING,
                severity=Severity.MEDIUM,
                description=(
                    f"Loss rate is {loss_rate:.0%} "
                    f"({lost_count}/{len(t_rows)} deals) over the last "
                    f"{lookback_days} days — above the {loss_rate_threshold:.0%} "
                    "threshold, suggesting systematic overpricing."
                ),
                suggested_action=(
                    "Compare won vs lost deal pricing. "
                    "Identify whether losses cluster around specific job types, "
                    "sizes, or geographies. "
                    "Consider a temporary price reduction test on the highest-loss "
                    "segments to validate the hypothesis."
                ),
                context={
                    "total_feedback": len(t_rows),
                    "won_count": len(t_rows) - lost_count,
                    "lost_count": lost_count,
                    "loss_rate": round(loss_rate, 4),
                    "loss_rate_threshold": loss_rate_threshold,
                    "min_sample": min_sample,
                    "lookback_days": lookback_days,
                },
                tenant_id=tid,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# 3. REPEATED_LOW_CONFIDENCE
# ---------------------------------------------------------------------------

def detect_repeated_low_confidence(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    min_runs: int = 5,
    confidence_threshold: float = 0.40,
) -> list[RuleSignal]:
    """
    Emit when a specific step (by step_name) repeatedly produces confidence
    scores below the threshold.

    Groups by (tenant_id, step_name).  Only step runs with a non-null
    confidence_score are evaluated; steps that never report confidence are
    covered by the CONFIDENCE_ABSENT_ON_COMPLETION anomaly detector instead.
    """
    cut = _cutoff(lookback_days)
    q = (
        db.query(
            PipelineRun.tenant_id,
            PipelineStepRun.step_name,
            func.count(PipelineStepRun.id).label("low_conf_count"),
            func.avg(PipelineStepRun.confidence_score).label("avg_score"),
            func.min(PipelineStepRun.confidence_score).label("min_score"),
        )
        .select_from(PipelineStepRun)
        .join(PipelineRun, PipelineRun.id == PipelineStepRun.pipeline_run_id)
        .filter(
            PipelineStepRun.confidence_score.isnot(None),
            PipelineStepRun.confidence_score < confidence_threshold,
            PipelineRun.created_at >= cut,
        )
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)

    q = (
        q.group_by(PipelineRun.tenant_id, PipelineStepRun.step_name)
        .having(func.count(PipelineStepRun.id) >= min_runs)
    )

    signals: list[RuleSignal] = []
    for row in q.all():
        avg_score = float(row.avg_score) if row.avg_score is not None else 0.0
        min_score = float(row.min_score) if row.min_score is not None else 0.0
        signals.append(
            RuleSignal(
                signal_type=SignalType.REPEATED_LOW_CONFIDENCE,
                severity=Severity.MEDIUM,
                description=(
                    f"Step '{row.step_name}' produced low confidence scores "
                    f"(< {confidence_threshold}) on {row.low_conf_count} runs "
                    f"in the last {lookback_days} days "
                    f"(avg: {avg_score:.2f}, min: {min_score:.2f})."
                ),
                suggested_action=(
                    f"Inspect input data quality for step '{row.step_name}'. "
                    "Check for missing or low-signal inputs that consistently "
                    "degrade confidence. Consider adding explicit fallback handling "
                    "or improving the data source for this step."
                ),
                context={
                    "step_name": row.step_name,
                    "low_conf_count": row.low_conf_count,
                    "avg_confidence_score": round(avg_score, 4),
                    "min_confidence_score": round(min_score, 4),
                    "confidence_threshold": confidence_threshold,
                    "min_runs": min_runs,
                    "lookback_days": lookback_days,
                },
                tenant_id=row.tenant_id,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# 4. REPEATED_FALLBACK
# ---------------------------------------------------------------------------

def detect_repeated_fallback(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    min_runs: int = 3,
) -> list[RuleSignal]:
    """
    Emit when a specific step repeatedly uses fallback logic, as indicated
    by confidence_reason containing the substring "fallback".

    Groups by (tenant_id, step_name).  Relies on steps populating
    confidence_reason with "fallback" when they use a degraded code path.
    """
    cut = _cutoff(lookback_days)
    q = (
        db.query(
            PipelineRun.tenant_id,
            PipelineStepRun.step_name,
            func.count(PipelineStepRun.id).label("fallback_count"),
        )
        .select_from(PipelineStepRun)
        .join(PipelineRun, PipelineRun.id == PipelineStepRun.pipeline_run_id)
        .filter(
            PipelineStepRun.confidence_reason.ilike("%fallback%"),
            PipelineRun.created_at >= cut,
        )
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)

    q = (
        q.group_by(PipelineRun.tenant_id, PipelineStepRun.step_name)
        .having(func.count(PipelineStepRun.id) >= min_runs)
    )

    signals: list[RuleSignal] = []
    for row in q.all():
        signals.append(
            RuleSignal(
                signal_type=SignalType.REPEATED_FALLBACK,
                severity=Severity.MEDIUM,
                description=(
                    f"Step '{row.step_name}' used fallback logic on "
                    f"{row.fallback_count} runs in the last {lookback_days} days — "
                    "a systematic fallback pattern is present."
                ),
                suggested_action=(
                    f"Investigate why step '{row.step_name}' falls back repeatedly. "
                    "Check for a specific input pattern that triggers the fallback path. "
                    "Consider adding a dedicated code path for this pattern rather than "
                    "relying on generic fallback logic."
                ),
                context={
                    "step_name": row.step_name,
                    "fallback_count": row.fallback_count,
                    "min_runs": min_runs,
                    "lookback_days": lookback_days,
                },
                tenant_id=row.tenant_id,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# 5. REPEATED_REVIEW_FLAG
# ---------------------------------------------------------------------------

def detect_repeated_review_flag(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    min_runs: int = 3,
) -> list[RuleSignal]:
    """
    Emit when a pipeline is repeatedly landing in NEEDS_REVIEW status.

    Groups by (tenant_id, pipeline_name).  Repeated review flags on the same
    pipeline suggest that a review rule or threshold is miscalibrated and
    should be tightened or relaxed.
    """
    cut = _cutoff(lookback_days)
    q = (
        db.query(
            PipelineRun.tenant_id,
            PipelineRun.pipeline_name,
            func.count(PipelineRun.id).label("review_count"),
        )
        .filter(
            PipelineRun.status == "NEEDS_REVIEW",
            PipelineRun.created_at >= cut,
        )
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)

    q = (
        q.group_by(PipelineRun.tenant_id, PipelineRun.pipeline_name)
        .having(func.count(PipelineRun.id) >= min_runs)
    )

    signals: list[RuleSignal] = []
    for row in q.all():
        signals.append(
            RuleSignal(
                signal_type=SignalType.REPEATED_REVIEW_FLAG,
                severity=Severity.LOW,
                description=(
                    f"Pipeline '{row.pipeline_name}' has been flagged for review "
                    f"{row.review_count} times in the last {lookback_days} days — "
                    "suggests a review rule or threshold needs recalibration."
                ),
                suggested_action=(
                    f"Audit the review-trigger rules for pipeline '{row.pipeline_name}'. "
                    "If these are consistent false positives, raise the relevant threshold. "
                    "If they represent genuine quality gaps, investigate the root input "
                    "pattern and consider automating the resolution."
                ),
                context={
                    "pipeline_name": row.pipeline_name,
                    "review_count": row.review_count,
                    "min_runs": min_runs,
                    "lookback_days": lookback_days,
                },
                tenant_id=row.tenant_id,
                pipeline_name=row.pipeline_name,
            )
        )
    return signals
