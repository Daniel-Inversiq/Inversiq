"""
app/routers/proposed_changes.py

GET /api/proposed-changes/pipelines  — Proposed changes per pipeline.
GET /api/proposed-changes/verticals  — Proposed changes per vertical.

Chains health, trend, reasoning, and control suggestion layers to produce
deterministic, read-only proposed change objects for later human review.
Nothing is applied, stored, or approved by these endpoints.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.health.summary import pipeline_health_summaries, vertical_health_summaries
from app.services.metrics_aggregation import aggregate_metrics
from app.services.trend_engine import compute_scope_trend
from app.services.reasoning_engine import run_reasoning
from app.services.control_suggestions import compute_control_suggestions
from app.services.proposed_changes import compute_proposed_changes
from app.models.proposed_change_review_state import ProposedChangeReviewState

router = APIRouter(prefix="/api/proposed-changes", tags=["proposed-changes"])

_REVIEW_WORKFLOW_PHASE: dict[str, str] = {
    "pending": "review",
    "approved": "review",
    "rejected": "review",
    "archived": "review",
    "ready_for_apply": "apply_intent",
}


def _default_review_state() -> dict[str, Any]:
    return {
        "status": "pending",
        "note": None,
        "updated_at": None,
        "persisted": False,
        "workflow_phase": "review",
    }


def _enrich_with_review_state(
    items: list[dict[str, Any]],
    *,
    tenant_id: Optional[str],
    db: Session,
) -> None:
    """Attach persisted review state to each proposed change object (in-place)."""
    if not tenant_id:
        for item in items:
            for change in item.get("proposed_changes", []):
                change["review_state"] = _default_review_state()
        return

    all_change_ids = [
        change["change_id"]
        for item in items
        for change in item.get("proposed_changes", [])
    ]
    if not all_change_ids:
        return

    rows = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == tenant_id,
            ProposedChangeReviewState.change_id.in_(all_change_ids),
        )
        .all()
    )
    lookup = {r.change_id: r for r in rows}

    for item in items:
        for change in item.get("proposed_changes", []):
            row = lookup.get(change["change_id"])
            if row is None:
                change["review_state"] = _default_review_state()
            else:
                change["review_state"] = {
                    "status": row.status,
                    "note": row.note,
                    "updated_at": row.updated_at,
                    "persisted": True,
                    "workflow_phase": _REVIEW_WORKFLOW_PHASE.get(row.status, "review"),
                }


def _changes_for_scope(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    health_status: str,
    signal_counts: dict,
    tenant_id: Optional[str],
    window_days: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    current = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=current_start,
        end=current_end,
        tenant_id=tenant_id,
    )
    previous = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=previous_start,
        end=current_start,
        tenant_id=tenant_id,
    )
    _, metric_trends = compute_scope_trend(current, previous)

    reasoning = run_reasoning(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health_status,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
    )
    reasoning_categories = [r["category"] for r in reasoning.get("reasoning", [])]

    control = compute_control_suggestions(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health_status,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
        reasoning_categories=reasoning_categories,
    )

    return compute_proposed_changes(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=control["suggestions"],
        reasoning_categories=reasoning_categories,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
    )


@router.get("/pipelines")
def get_pipeline_proposed_changes(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Deterministic proposed changes per pipeline.

    Chains health, trend, reasoning, and control suggestion layers to produce
    read-only proposed change objects for later human review. No mutations.
    All returned objects carry status='proposal_only'.
    """
    health_items = pipeline_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _changes_for_scope(
            db,
            scope_type="pipeline",
            scope_id=h.pipeline_name,
            health_status=h.health_status,
            signal_counts=h.signal_counts,
            tenant_id=tenant_id,
            window_days=window_days,
        )
        for h in health_items
    ]

    if limit is not None:
        items = items[:limit]

    _enrich_with_review_state(items, tenant_id=tenant_id, db=db)

    return {
        "scope_type": "pipeline",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }


@router.get("/verticals")
def get_vertical_proposed_changes(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Deterministic proposed changes per vertical.

    Same logic as /api/proposed-changes/pipelines, grouped by vertical_id.
    """
    health_items = vertical_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _changes_for_scope(
            db,
            scope_type="vertical",
            scope_id=h.vertical_id,
            health_status=h.health_status,
            signal_counts=h.signal_counts,
            tenant_id=tenant_id,
            window_days=window_days,
        )
        for h in health_items
    ]

    if limit is not None:
        items = items[:limit]

    _enrich_with_review_state(items, tenant_id=tenant_id, db=db)

    return {
        "scope_type": "vertical",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }
