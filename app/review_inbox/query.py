"""
app/review_inbox/query.py

Read-only review inbox query layer.

build_inbox_items() queries PipelineRun records that are candidates for
operator review, runs anomaly detection on each result-page run, and scores
each using the existing compute_run_review() logic.

Design decisions
----------------
- Pre-filters to deterministic review candidates: FAILED, NEEDS_REVIEW, or
  low overall confidence. This bounds the anomaly detector calls to runs
  that are already likely to need review, avoiding full-table scans.
  Anomaly-only review cases (healthy COMPLETED runs with anomalies but no
  status/confidence flag) are not surfaced here; use the per-run debug
  endpoint for those.

- Anomaly detection runs per-run on the result page (N+1 pattern), bounded
  by `limit` (max 200). At 5 detectors × 200 runs = 1 000 indexed queries.
  Acceptable for an internal ops tool; noted as a known limitation.

- Priority ordering in SQL: FAILED (1) > low confidence (2) > NEEDS_REVIEW (3).
  Within a tier, newest-first. This keeps the most actionable items at the
  top without a Python sort over the full dataset.

- compute_run_review() is called with the anomaly dicts so anomaly-based
  priority escalations (rules 4, 6, 8) are included in the final score for
  pre-filtered candidates.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import case, or_
from sqlalchemy.orm import Session, selectinload

from app.anomaly.engine import run_all as run_anomaly_detectors
from app.anomaly.run_review import compute_run_review
from app.models.pipeline_run import PipelineRun
from app.models.run_review_state import RunReviewState

# ---------------------------------------------------------------------------
# Priority ordering expression
# ---------------------------------------------------------------------------
# Maps pre-filterable status/confidence combinations to a sort rank so the
# SQL result is already in approximate priority order before Python scoring.
# Exact priority is computed per-run by compute_run_review(); this expression
# only serves as a fast first-pass ordering hint.
_PRIORITY_EXPR = case(
    (PipelineRun.status == "FAILED", 1),
    (PipelineRun.overall_confidence_label == "low", 2),
    (PipelineRun.status == "NEEDS_REVIEW", 3),
    else_=4,
)


def build_inbox_items(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    review_recommended_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Return a list of PipelineRun inbox items that need operator review.

    Parameters
    ----------
    db                      : Active SQLAlchemy session.
    tenant_id               : Scope to a single tenant; None = all tenants.
    status                  : Filter by pipeline status (FAILED, NEEDS_REVIEW, …).
                              When supplied, the candidate pre-filter is skipped
                              so callers can inspect any status class.
    priority                : Post-filter by computed review_priority
                              (``"high"``, ``"medium"``, or ``"low"``).
    review_recommended_only : If True (default), drop items where
                              compute_run_review returns review_recommended=False.
    limit                   : Page size (default 50, max 200 enforced at router).
    offset                  : Pagination offset.

    Returns
    -------
    List of dicts — one per qualifying run, sorted high-priority first then
    newest-first within each tier.
    """
    q = db.query(PipelineRun).options(selectinload(PipelineRun.steps))

    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)

    if status:
        # Explicit status overrides the candidate pre-filter; callers may want
        # to inspect COMPLETED runs for anomaly-driven reviews.
        q = q.filter(PipelineRun.status == status.upper())
    elif review_recommended_only:
        # Pre-filter to deterministic candidates only — skips healthy runs.
        q = q.filter(
            or_(
                PipelineRun.status == "FAILED",
                PipelineRun.status == "NEEDS_REVIEW",
                PipelineRun.overall_confidence_label == "low",
            )
        )

    q = q.order_by(_PRIORITY_EXPR.asc(), PipelineRun.created_at.desc())
    q = q.limit(limit).offset(offset)

    runs = q.all()

    # Batch-fetch review states for this page in one query to avoid N+1.
    run_ids = [r.id for r in runs]
    review_states: dict[int, dict[str, Any]] = {}
    if run_ids:
        rows = (
            db.query(
                RunReviewState.pipeline_run_id,
                RunReviewState.status,
                RunReviewState.note,
                RunReviewState.updated_at,
            )
            .filter(RunReviewState.pipeline_run_id.in_(run_ids))
            .all()
        )
        review_states = {
            row.pipeline_run_id: {
                "status": row.status,
                "note": row.note,
                "updated_at": row.updated_at,
            }
            for row in rows
        }

    items: list[dict[str, Any]] = []
    for run in runs:
        anomalies = run_anomaly_detectors(
            db,
            pipeline_run_id=run.id,
            tenant_id=run.tenant_id,
        )
        anomaly_dicts = [a.to_dict() for a in anomalies]

        review = compute_run_review(
            status=run.status,
            error_category=run.error_category,
            overall_confidence_label=run.overall_confidence_label,
            anomaly_dicts=anomaly_dicts,
        )

        if review_recommended_only and not review["review_recommended"]:
            continue

        state = review_states.get(run.id, {})
        items.append(
            {
                "pipeline_run_id": run.id,
                "tenant_id": run.tenant_id,
                "lead_id": run.lead_id,
                "pipeline_name": run.pipeline_name,
                "vertical_id": run.vertical_id,
                "status": run.status,
                "review_recommended": review["review_recommended"],
                "review_priority": review["review_priority"],
                "review_reason": review["review_reason"],
                "confidence": run.overall_confidence_score,
                "anomaly_count": len(anomalies),
                "review_state": state.get("status", "pending"),
                "review_state_note": state.get("note"),
                "review_state_updated_at": state.get("updated_at"),
                "created_at": run.created_at,
            }
        )

    # Post-filter by computed priority when requested. Applied after anomaly
    # scoring because priority may be raised by anomaly-based rules.
    if priority:
        items = [i for i in items if i["review_priority"] == priority.lower()]

    return items
