"""
app/routers/focus.py

GET /api/focus/pipelines  — Prioritized focus list per pipeline_name.
GET /api/focus/verticals  — Prioritized focus list per vertical_id.

Combines health status (``lookback_days`` window) with trend direction
(``window_days`` comparison window) to compute a deterministic priority
score per scope.  Items are returned sorted score-descending.

See app/services/focus_engine.py for the full scoring formula.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.health.summary import pipeline_health_summaries, vertical_health_summaries
from app.services.focus_engine import build_focus_item
from app.services.metrics_aggregation import aggregate_metrics
from app.services.trend_engine import compute_scope_trend
from app.services.trend_recommendations import recommendations_for_trends

router = APIRouter(prefix="/api/focus", tags=["focus"])


def _trend_item(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
    tenant_id: Optional[str],
) -> dict[str, Any]:
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
        end=previous_end,
        tenant_id=tenant_id,
    )
    direction, metric_trends = compute_scope_trend(current, previous)
    return {
        "trend": direction,
        "metrics": metric_trends,
        "recommendations": recommendations_for_trends(metric_trends),
    }


@router.get("/pipelines")
def get_pipeline_focus(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(
        7, ge=1, le=90, description="Trend comparison window length in days"
    ),
    lookback_days: int = Query(
        30, ge=1, le=365, description="Health aggregation window in days"
    ),
    top_n: Optional[int] = Query(
        None, ge=1, le=100, description="Limit output to the top N items"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Prioritized focus list for pipelines.

    Each item combines health status and trend direction into a single
    ``priority_score`` (0-100) and ``severity`` label.  Items are sorted
    score-descending so operators see the highest-impact issues first.

    ``key_issues`` lists the specific metrics and signals that drove the
    score; ``reason`` explains the scoring in one sentence.
    """
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    health_items = pipeline_health_summaries(
        db, tenant_id=tenant_id, lookback_days=lookback_days
    )

    items: list[dict[str, Any]] = []
    for h in health_items:
        trend = _trend_item(
            db,
            scope_type="pipeline",
            scope_id=h.pipeline_name,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=current_start,
            tenant_id=tenant_id,
        )
        items.append(
            build_focus_item(
                scope_type="pipeline",
                scope_id=h.pipeline_name,
                health_status=h.health_status,
                failed_rate=h.failed_rate,
                needs_review_rate=h.needs_review_rate,
                low_confidence_rate=h.low_confidence_rate,
                signal_counts=h.signal_counts,
                health_recommendation=h.top_recommendation,
                trend_item=trend,
            )
        )

    items.sort(key=lambda x: -x["priority_score"])
    if top_n is not None:
        items = items[:top_n]

    return {
        "scope_type": "pipeline",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }


@router.get("/verticals")
def get_vertical_focus(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(
        7, ge=1, le=90, description="Trend comparison window length in days"
    ),
    lookback_days: int = Query(
        30, ge=1, le=365, description="Health aggregation window in days"
    ),
    top_n: Optional[int] = Query(
        None, ge=1, le=100, description="Limit output to the top N items"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Prioritized focus list for verticals.

    Same logic as ``GET /api/focus/pipelines``, grouped by vertical_id.
    """
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    health_items = vertical_health_summaries(
        db, tenant_id=tenant_id, lookback_days=lookback_days
    )

    items: list[dict[str, Any]] = []
    for h in health_items:
        trend = _trend_item(
            db,
            scope_type="vertical",
            scope_id=h.vertical_id,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=current_start,
            tenant_id=tenant_id,
        )
        items.append(
            build_focus_item(
                scope_type="vertical",
                scope_id=h.vertical_id,
                health_status=h.health_status,
                failed_rate=h.failed_rate,
                needs_review_rate=h.needs_review_rate,
                low_confidence_rate=h.low_confidence_rate,
                signal_counts=h.signal_counts,
                health_recommendation=h.top_recommendation,
                trend_item=trend,
            )
        )

    items.sort(key=lambda x: -x["priority_score"])
    if top_n is not None:
        items = items[:top_n]

    return {
        "scope_type": "vertical",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }
