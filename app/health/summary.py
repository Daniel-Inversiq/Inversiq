"""
app/health/summary.py

Read-only aggregation layer for pipeline and vertical health.

Combines raw PipelineRun counts with intelligence signals to produce a
single health_status label and top_recommendation per pipeline or vertical.

Design notes
------------
- Fully deterministic: same DB state + same inputs → same output.
- Read-only: never writes to the database.
- Two scopes: per-pipeline (grouped by pipeline_name) and per-vertical
  (grouped by vertical_id).
- Signal attribution:
    REPEATED_REVIEW_FLAG  → linked to a specific pipeline_name via
                            RuleSignal.pipeline_name; attributed to that
                            pipeline only.
    All other signals     → tenant-level (no pipeline linkage); attributed
                            to every pipeline in the tenant scope.
- Intelligence signals are run once per call, not per-pipeline.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.intelligence.engine import run_all as _run_intelligence
from app.intelligence.types import RuleSignal, Severity, SignalType
from app.models.pipeline_run import PipelineRun
from .types import (
    PipelineHealthSummary,
    VerticalHealthSummary,
    UNHEALTHY_FAILED_RATE,
    UNHEALTHY_NEEDS_REVIEW_RATE,
    UNHEALTHY_LOW_CONFIDENCE_RATE,
    WATCH_FAILED_RATE,
    WATCH_NEEDS_REVIEW_RATE,
    WATCH_LOW_CONFIDENCE_RATE,
)

_STATUS_ORDER = {"unhealthy": 0, "watch": 1, "healthy": 2}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _health_status(
    failed_rate: float,
    needs_review_rate: float,
    low_confidence_rate: float,
    has_high_signal: bool,
) -> str:
    if (
        failed_rate >= UNHEALTHY_FAILED_RATE
        or needs_review_rate >= UNHEALTHY_NEEDS_REVIEW_RATE
        or low_confidence_rate >= UNHEALTHY_LOW_CONFIDENCE_RATE
    ):
        return "unhealthy"
    if (
        failed_rate >= WATCH_FAILED_RATE
        or needs_review_rate >= WATCH_NEEDS_REVIEW_RATE
        or low_confidence_rate >= WATCH_LOW_CONFIDENCE_RATE
        or has_high_signal
    ):
        return "watch"
    return "healthy"


def _top_recommendation(
    failed_rate: float,
    needs_review_rate: float,
    low_confidence_rate: float,
    signal_counts: dict[str, int],
) -> str:
    """Return the single highest-priority operator recommendation (first match wins)."""
    if failed_rate >= WATCH_FAILED_RATE:
        return (
            "Investigate step failures — review error_category and "
            "failure_step fields for recurring patterns."
        )
    if needs_review_rate >= WATCH_NEEDS_REVIEW_RATE:
        return (
            "Reduce manual review volume by tightening pipeline rules "
            "or improving input data quality."
        )
    if low_confidence_rate >= WATCH_LOW_CONFIDENCE_RATE:
        return (
            "Address low-confidence steps — check for fallback paths "
            "or missing input fields."
        )
    if signal_counts.get(SignalType.LIKELY_UNDERPRICING.value, 0) > 0:
        return "Review pricing rules — won deals are consistently below engine estimate."
    if signal_counts.get(SignalType.LIKELY_OVERPRICING.value, 0) > 0:
        return "Review pricing strategy — high loss rate suggests systematic overpricing."
    if signal_counts.get(SignalType.REPEATED_FALLBACK.value, 0) > 0:
        return "Fix repeated fallback paths to improve pipeline reliability."
    if signal_counts.get(SignalType.REPEATED_LOW_CONFIDENCE.value, 0) > 0:
        return "Improve step input data to lift confidence scores."
    return "No action needed — pipeline health looks good."


def _signals_for_pipeline(
    signals: list[RuleSignal],
    pipeline_name: str,
) -> list[RuleSignal]:
    """
    Return the subset of signals that apply to a given pipeline.

    REPEATED_REVIEW_FLAG sets RuleSignal.pipeline_name → only that pipeline.
    All other signals have pipeline_name=None → apply to every pipeline.
    """
    return [
        sig for sig in signals
        if sig.pipeline_name is None or sig.pipeline_name == pipeline_name
    ]


def _sig_counts(signals: list[RuleSignal]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for sig in signals:
        counts[sig.signal_type.value] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pipeline_health_summaries(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
) -> list[PipelineHealthSummary]:
    """Return one PipelineHealthSummary per distinct pipeline_name in the window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    q = db.query(PipelineRun).filter(PipelineRun.created_at >= cutoff)
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    runs = q.all()

    if not runs:
        return []

    # Group by pipeline_name
    groups: dict[str, list[PipelineRun]] = defaultdict(list)
    for run in runs:
        groups[run.pipeline_name].append(run)

    # Run all intelligence signals once for this tenant scope
    signals = _run_intelligence(db, tenant_id=tenant_id, lookback_days=lookback_days)

    computed_at = datetime.now(timezone.utc)
    summaries: list[PipelineHealthSummary] = []

    for pipeline_name, pipeline_runs in groups.items():
        total = len(pipeline_runs)
        failed = sum(1 for r in pipeline_runs if r.status == "FAILED")
        needs_review = sum(1 for r in pipeline_runs if r.status == "NEEDS_REVIEW")
        low_conf = sum(1 for r in pipeline_runs if r.overall_confidence_label == "low")

        failed_rate = failed / total
        needs_review_rate = needs_review / total
        low_confidence_rate = low_conf / total

        applicable = _signals_for_pipeline(signals, pipeline_name)
        counts = _sig_counts(applicable)
        has_high = any(sig.severity == Severity.HIGH for sig in applicable)

        health_status = _health_status(
            failed_rate, needs_review_rate, low_confidence_rate, has_high
        )
        recommendation = _top_recommendation(
            failed_rate, needs_review_rate, low_confidence_rate, counts
        )

        # vertical_id from the most-recent run for this pipeline
        most_recent = max(pipeline_runs, key=lambda r: r.created_at)

        summaries.append(
            PipelineHealthSummary(
                pipeline_name=pipeline_name,
                vertical_id=most_recent.vertical_id,
                tenant_id=tenant_id,
                total_runs=total,
                failed_rate=failed_rate,
                needs_review_rate=needs_review_rate,
                low_confidence_rate=low_confidence_rate,
                signal_counts=counts,
                health_status=health_status,
                top_recommendation=recommendation,
                lookback_days=lookback_days,
                computed_at=computed_at,
            )
        )

    summaries.sort(key=lambda s: (_STATUS_ORDER.get(s.health_status, 3), -s.total_runs))
    return summaries


def vertical_health_summaries(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
) -> list[VerticalHealthSummary]:
    """Return one VerticalHealthSummary per distinct vertical_id in the window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    q = db.query(PipelineRun).filter(PipelineRun.created_at >= cutoff)
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    runs = q.all()

    if not runs:
        return []

    # Group by vertical_id (None → "_unknown")
    groups: dict[str, list[PipelineRun]] = defaultdict(list)
    for run in runs:
        groups[run.vertical_id or "_unknown"].append(run)

    # All intelligence signals are tenant-level for vertical grouping
    signals = _run_intelligence(db, tenant_id=tenant_id, lookback_days=lookback_days)
    all_counts = _sig_counts(signals)
    has_high = any(sig.severity == Severity.HIGH for sig in signals)

    computed_at = datetime.now(timezone.utc)
    summaries: list[VerticalHealthSummary] = []

    for vertical_id, vertical_runs in groups.items():
        total = len(vertical_runs)
        failed = sum(1 for r in vertical_runs if r.status == "FAILED")
        needs_review = sum(1 for r in vertical_runs if r.status == "NEEDS_REVIEW")
        low_conf = sum(1 for r in vertical_runs if r.overall_confidence_label == "low")
        pipeline_count = len({r.pipeline_name for r in vertical_runs})

        failed_rate = failed / total
        needs_review_rate = needs_review / total
        low_confidence_rate = low_conf / total

        health_status = _health_status(
            failed_rate, needs_review_rate, low_confidence_rate, has_high
        )
        recommendation = _top_recommendation(
            failed_rate, needs_review_rate, low_confidence_rate, all_counts
        )

        summaries.append(
            VerticalHealthSummary(
                vertical_id=vertical_id,
                tenant_id=tenant_id,
                total_runs=total,
                pipeline_count=pipeline_count,
                failed_rate=failed_rate,
                needs_review_rate=needs_review_rate,
                low_confidence_rate=low_confidence_rate,
                signal_counts=dict(all_counts),
                health_status=health_status,
                top_recommendation=recommendation,
                lookback_days=lookback_days,
                computed_at=computed_at,
            )
        )

    summaries.sort(key=lambda s: (_STATUS_ORDER.get(s.health_status, 3), -s.total_runs))
    return summaries
