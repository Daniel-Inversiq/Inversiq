"""
app/routers/proposal_staleness.py

GET /api/proposal-staleness/pipelines  — Staleness detection per pipeline.
GET /api/proposal-staleness/verticals  — Staleness detection per vertical.

Chains the full intelligence pipeline (health → trends → reasoning → control
suggestions → proposed changes) then annotates each proposal with a staleness
status based on review history and current signal context.

Read-only. No mutations, no persistence, no approvals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.health.summary import pipeline_health_summaries, vertical_health_summaries
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.control_suggestions import compute_control_suggestions
from app.services.metrics_aggregation import aggregate_metrics
from app.services.proposal_staleness import detect_proposal_staleness
from app.services.proposed_changes import compute_proposed_changes
from app.services.reasoning_engine import run_reasoning
from app.services.trend_engine import compute_scope_trend

router = APIRouter(prefix="/api/proposal-staleness", tags=["proposal-staleness"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_review_states(
    db: Session,
    change_ids: list[str],
    *,
    tenant_id: Optional[str],
) -> dict[str, dict[str, Any]]:
    """Return {change_id: {status, created_at, updated_at, persisted}} for all given change_ids."""
    if not change_ids or not tenant_id:
        return {}

    rows = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == tenant_id,
            ProposedChangeReviewState.change_id.in_(change_ids),
        )
        .all()
    )
    return {
        r.change_id: {
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "persisted": True,
        }
        for r in rows
    }


def _staleness_for_scope(
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
    control_categories = [s["category"] for s in control.get("suggestions", [])]

    proposed = compute_proposed_changes(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=control["suggestions"],
        reasoning_categories=reasoning_categories,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
    )

    changes = proposed["proposed_changes"]
    change_ids = [c["change_id"] for c in changes]
    review_states = _load_review_states(db, change_ids, tenant_id=tenant_id)

    return detect_proposal_staleness(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
        review_states=review_states,
        current_reasoning_categories=reasoning_categories,
        current_control_categories=control_categories,
        now=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/pipelines")
def get_pipeline_proposal_staleness(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Deterministic staleness detection per pipeline.

    Runs the full intelligence chain (health → trends → reasoning → control
    suggestions → proposed changes) and annotates each proposal with a
    staleness status based on review history and current signal context.
    Read-only. Nothing is applied or stored.
    """
    health_items = pipeline_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _staleness_for_scope(
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

    total_stale = sum(i["stale_count"] for i in items)
    total_aging = sum(i["aging_count"] for i in items)

    return {
        "scope_type": "pipeline",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total_scopes": len(items),
        "total_stale": total_stale,
        "total_aging": total_aging,
        "items": items,
    }


@router.get("/verticals")
def get_vertical_proposal_staleness(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Deterministic staleness detection per vertical.

    Same logic as /api/proposal-staleness/pipelines, grouped by vertical_id.
    """
    health_items = vertical_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _staleness_for_scope(
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

    total_stale = sum(i["stale_count"] for i in items)
    total_aging = sum(i["aging_count"] for i in items)

    return {
        "scope_type": "vertical",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total_scopes": len(items),
        "total_stale": total_stale,
        "total_aging": total_aging,
        "items": items,
    }
