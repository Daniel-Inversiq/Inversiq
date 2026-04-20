"""
app/services/metrics_aggregation.py

Read-only metrics aggregation service for trend intelligence.

Returns a normalized metrics dict for a given scope (pipeline_name or
vertical_id) and an explicit time window [start, end).  Designed to be
called twice per trend request — once for the current window, once for the
previous — so the trend engine can compute deltas.

Metrics returned
----------------
  run_count              int    — Total PipelineRuns in window
  success_rate           float  — COMPLETED / run_count
  failed_rate            float  — FAILED / run_count
  review_rate            float  — NEEDS_REVIEW / run_count
  avg_confidence         float  — Mean overall_confidence_score (non-null only)
  low_confidence_rate    float  — overall_confidence_label == "low" / run_count
  fallback_rate          float  — fallback steps / total steps (joined via run)
  feedback_count         int    — LeadFeedback records linked via pipeline_run_id
  negative_feedback_rate float  — lost / (won + lost)
  underpricing_rate      float  — underpriced won / won deals with both prices

All rates are None when the denominator is zero (insufficient data for that
metric).  run_count and feedback_count are always present as integers (0+).

Design notes
------------
- Purely read-only; never writes or modifies any row.
- Deterministic: same DB state + same inputs → same output.
- Step and feedback queries use joins rather than Python-side ID lists to
  avoid SQLite parameter limits on large windows.
- LeadFeedback is joined via pipeline_run_id (nullable); records without a
  pipeline_run_id link are excluded from feedback metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun

# A won deal is "underpriced" when actual_price < estimated_price * (1 - margin)
_UNDERPRICING_MARGIN: float = 0.10


def _empty_metrics() -> dict[str, Any]:
    """Return a zero-run metrics dict with all rates None."""
    return {
        "run_count": 0,
        "success_rate": None,
        "failed_rate": None,
        "review_rate": None,
        "avg_confidence": None,
        "low_confidence_rate": None,
        "fallback_rate": None,
        "feedback_count": 0,
        "negative_feedback_rate": None,
        "underpricing_rate": None,
    }


def aggregate_metrics(
    db: Session,
    *,
    scope_type: str,
    scope_key: str,
    start: datetime,
    end: datetime,
    tenant_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Compute normalized operational metrics for one scope + time window.

    Parameters
    ----------
    scope_type : "pipeline" or "vertical"
        Determines which PipelineRun field is used to scope the query.
    scope_key : str
        The pipeline_name or vertical_id value to filter on.
    start, end : datetime
        Half-open window [start, end).  Both should be timezone-aware.
    tenant_id : str, optional
        When provided, further restricts all queries to this tenant.

    Returns
    -------
    dict
        Metrics dict as described in the module docstring.
    """
    if scope_type not in ("pipeline", "vertical"):
        raise ValueError(f"scope_type must be 'pipeline' or 'vertical', got {scope_type!r}")

    # ------------------------------------------------------------------
    # Build base filter list — shared across all queries in this call
    # ------------------------------------------------------------------
    base_run_filters = [
        PipelineRun.created_at >= start,
        PipelineRun.created_at < end,
    ]
    if tenant_id:
        base_run_filters.append(PipelineRun.tenant_id == tenant_id)
    if scope_type == "pipeline":
        base_run_filters.append(PipelineRun.pipeline_name == scope_key)
    else:
        base_run_filters.append(PipelineRun.vertical_id == scope_key)

    # ------------------------------------------------------------------
    # Load PipelineRun rows — used for status / confidence aggregation
    # ------------------------------------------------------------------
    runs = db.query(PipelineRun).filter(*base_run_filters).all()
    run_count = len(runs)

    if run_count == 0:
        return _empty_metrics()

    # ------------------------------------------------------------------
    # Status and confidence metrics (Python-side, already in memory)
    # ------------------------------------------------------------------
    completed = sum(1 for r in runs if r.status == "COMPLETED")
    failed = sum(1 for r in runs if r.status == "FAILED")
    needs_review = sum(1 for r in runs if r.status == "NEEDS_REVIEW")
    low_conf = sum(1 for r in runs if r.overall_confidence_label == "low")

    conf_scores = [
        float(r.overall_confidence_score)
        for r in runs
        if r.overall_confidence_score is not None
    ]
    avg_confidence = sum(conf_scores) / len(conf_scores) if conf_scores else None

    # ------------------------------------------------------------------
    # Fallback rate — PipelineStepRun joined to PipelineRun
    # Using a join avoids large IN clauses on run IDs.
    # ------------------------------------------------------------------
    total_steps: int = (
        db.query(func.count(PipelineStepRun.id))
        .select_from(PipelineStepRun)
        .join(PipelineRun, PipelineRun.id == PipelineStepRun.pipeline_run_id)
        .filter(*base_run_filters)
        .scalar()
        or 0
    )
    fallback_steps: int = (
        db.query(func.count(PipelineStepRun.id))
        .select_from(PipelineStepRun)
        .join(PipelineRun, PipelineRun.id == PipelineStepRun.pipeline_run_id)
        .filter(
            *base_run_filters,
            PipelineStepRun.confidence_reason.ilike("%fallback%"),
        )
        .scalar()
        or 0
    )
    fallback_rate = fallback_steps / total_steps if total_steps > 0 else None

    # ------------------------------------------------------------------
    # Feedback metrics — LeadFeedback joined to PipelineRun
    # Only records with a pipeline_run_id link are included.
    # ------------------------------------------------------------------
    fb_rows = (
        db.query(LeadFeedback)
        .join(PipelineRun, PipelineRun.id == LeadFeedback.pipeline_run_id)
        .filter(
            *base_run_filters,
            LeadFeedback.outcome.in_(["won", "lost"]),
        )
        .all()
    )
    feedback_count = len(fb_rows)

    if feedback_count > 0:
        lost_count = sum(1 for r in fb_rows if r.outcome == "lost")
        negative_feedback_rate: Optional[float] = lost_count / feedback_count

        priced_won = [
            r
            for r in fb_rows
            if r.outcome == "won"
            and r.actual_price is not None
            and r.estimated_price is not None
            and float(r.estimated_price or 0) > 0
        ]
        underpriced_count = sum(
            1
            for r in priced_won
            if float(r.actual_price) < float(r.estimated_price) * (1.0 - _UNDERPRICING_MARGIN)
        )
        underpricing_rate: Optional[float] = (
            underpriced_count / len(priced_won) if priced_won else None
        )
    else:
        negative_feedback_rate = None
        underpricing_rate = None

    return {
        "run_count": run_count,
        "success_rate": completed / run_count,
        "failed_rate": failed / run_count,
        "review_rate": needs_review / run_count,
        "avg_confidence": avg_confidence,
        "low_confidence_rate": low_conf / run_count,
        "fallback_rate": fallback_rate,
        "feedback_count": feedback_count,
        "negative_feedback_rate": negative_feedback_rate,
        "underpricing_rate": underpricing_rate,
    }
