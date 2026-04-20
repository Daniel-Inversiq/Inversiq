"""
app/routers/trends.py

GET /api/trends/pipelines  — Trend intelligence per pipeline_name.
GET /api/trends/verticals  — Trend intelligence per vertical_id.

Compares two equal-length time windows (default: 7 days each):
  current  window: [now - window_days, now)
  previous window: [now - 2 * window_days, now - window_days)

For each scope with at least one PipelineRun in the combined window, metrics
are aggregated via the metrics_aggregation service and compared through the
deterministic trend engine.  Degrading metrics are mapped to recommendations.

All endpoints are read-only and production-safe.  Nothing is written.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.pipeline_run import PipelineRun
from app.services.metrics_aggregation import aggregate_metrics
from app.services.trend_engine import compute_scope_trend
from app.services.trend_recommendations import recommendations_for_trends

router = APIRouter(prefix="/api/trends", tags=["trends"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _window_shape(
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
) -> dict[str, Any]:
    return {
        "current": {
            "start": current_start.isoformat(),
            "end": current_end.isoformat(),
        },
        "previous": {
            "start": previous_start.isoformat(),
            "end": previous_end.isoformat(),
        },
    }


def _build_trend_item(
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
    current_metrics = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=current_start,
        end=current_end,
        tenant_id=tenant_id,
    )
    previous_metrics = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=previous_start,
        end=previous_end,
        tenant_id=tenant_id,
    )

    aggregate_direction, metric_trends = compute_scope_trend(current_metrics, previous_metrics)
    recs = recommendations_for_trends(metric_trends)

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "trend": aggregate_direction,
        "metrics": metric_trends,
        "recommendations": recs,
    }


def _discover_scopes(
    db: Session,
    *,
    field,
    combined_cutoff: datetime,
    current_end: datetime,
    tenant_id: Optional[str],
) -> list[str]:
    """Return sorted distinct non-null values of `field` in the combined window."""
    q = db.query(field).filter(
        PipelineRun.created_at >= combined_cutoff,
        PipelineRun.created_at < current_end,
    )
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    return sorted({row[0] for row in q.distinct().all() if row[0]})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/pipelines")
def get_pipeline_trends(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(
        7, ge=1, le=90, description="Length of each comparison window in days"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Trend intelligence per pipeline_name.

    Compares the current window (last ``window_days`` days) against the
    previous window (the ``window_days`` days before that).

    Each item includes per-metric deltas, direction, severity, and a
    deduplicated list of recommendations for any degrading metrics.

    Metrics with ``direction: insufficient_data`` indicate that one or both
    windows had no data for that metric (e.g. no feedback records linked).
    """
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_end = current_start
    previous_start = current_start - timedelta(days=window_days)

    scope_ids = _discover_scopes(
        db,
        field=PipelineRun.pipeline_name,
        combined_cutoff=previous_start,
        current_end=current_end,
        tenant_id=tenant_id,
    )

    items = [
        _build_trend_item(
            db,
            scope_type="pipeline",
            scope_id=sid,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
            tenant_id=tenant_id,
        )
        for sid in scope_ids
    ]

    return {
        "scope_type": "pipeline",
        "window_days": window_days,
        "window": _window_shape(current_start, current_end, previous_start, previous_end),
        "total": len(items),
        "items": items,
    }


@router.get("/verticals")
def get_vertical_trends(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    window_days: int = Query(
        7, ge=1, le=90, description="Length of each comparison window in days"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Trend intelligence per vertical_id.

    Same logic as ``GET /api/trends/pipelines``, grouped by vertical_id.
    """
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_end = current_start
    previous_start = current_start - timedelta(days=window_days)

    scope_ids = _discover_scopes(
        db,
        field=PipelineRun.vertical_id,
        combined_cutoff=previous_start,
        current_end=current_end,
        tenant_id=tenant_id,
    )

    items = [
        _build_trend_item(
            db,
            scope_type="vertical",
            scope_id=sid,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
            tenant_id=tenant_id,
        )
        for sid in scope_ids
    ]

    return {
        "scope_type": "vertical",
        "window_days": window_days,
        "window": _window_shape(current_start, current_end, previous_start, previous_end),
        "total": len(items),
        "items": items,
    }
