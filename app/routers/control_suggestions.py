"""
app/routers/control_suggestions.py

GET /api/control-suggestions/pipelines  — Bounded control suggestions per pipeline.
GET /api/control-suggestions/verticals  — Bounded control suggestions per vertical.

Combines health, trend, and reasoning signals to produce deterministic,
explainable control suggestions. Read-only advisory only — no mutations.
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

router = APIRouter(prefix="/api/control-suggestions", tags=["control-suggestions"])


def _suggestions_for_scope(
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

    return compute_control_suggestions(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health_status,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
        reasoning_categories=reasoning_categories,
    )


@router.get("/pipelines")
def get_pipeline_control_suggestions(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Bounded control suggestions per pipeline.

    Combines health status, trend metrics, and reasoning categories to propose
    deterministic, explainable operational adjustments. Read-only advisory only.
    """
    health_items = pipeline_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _suggestions_for_scope(
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

    return {
        "scope_type": "pipeline",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }


@router.get("/verticals")
def get_vertical_control_suggestions(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(7, ge=1, le=90, description="Trend comparison window in days"),
    lookback_days: int = Query(30, ge=1, le=365, description="Health aggregation window in days"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of results"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Bounded control suggestions per vertical.

    Same logic as /api/control-suggestions/pipelines, grouped by vertical_id.
    """
    health_items = vertical_health_summaries(db, tenant_id=tenant_id, lookback_days=lookback_days)

    items = [
        _suggestions_for_scope(
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

    return {
        "scope_type": "vertical",
        "window_days": window_days,
        "lookback_days": lookback_days,
        "total": len(items),
        "items": items,
    }
