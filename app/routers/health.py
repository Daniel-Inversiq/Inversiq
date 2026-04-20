"""
app/routers/health.py

GET /api/health/pipelines  — Structural health summary per pipeline_name.
GET /api/health/verticals  — Structural health summary per vertical_id.

Both endpoints are read-only and production-safe.  All logic runs against
stored PipelineRun rows and the existing intelligence signal layer — no new
state is written.

health_status values
--------------------
  healthy    All rates below watch thresholds; no high-severity signals.
  watch      One or more rates exceed watch thresholds, or a HIGH-severity
             intelligence signal is present.
  unhealthy  One or more rates exceed unhealthy thresholds.

Thresholds are defined in app/health/types.py and are explicit constants.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.health.summary import pipeline_health_summaries, vertical_health_summaries

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/pipelines")
def get_pipeline_health(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    lookback_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Aggregated structural health per pipeline_name.

    Results are sorted worst-first (unhealthy → watch → healthy), then by
    total_runs descending within each tier.

    Each item includes:
    - **failed_rate** / **needs_review_rate** / **low_confidence_rate** — share
      of runs in each problem category over the lookback window.
    - **signal_counts** — count of each intelligence signal type that applies
      to this pipeline.
    - **health_status** — single label derived from the above rates and signals.
    - **top_recommendation** — highest-priority operator action (first-match
      rule; explicit in ``app/health/summary._top_recommendation``).
    """
    summaries = pipeline_health_summaries(
        db, tenant_id=tenant_id, lookback_days=lookback_days
    )
    return {
        "total": len(summaries),
        "lookback_days": lookback_days,
        "summary": {
            "healthy": sum(1 for s in summaries if s.health_status == "healthy"),
            "watch": sum(1 for s in summaries if s.health_status == "watch"),
            "unhealthy": sum(1 for s in summaries if s.health_status == "unhealthy"),
        },
        "items": [s.to_dict() for s in summaries],
    }


@router.get("/verticals")
def get_vertical_health(
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    lookback_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Aggregated structural health per vertical_id.

    Metrics are computed across all pipelines within the vertical.
    Intelligence signals are tenant-level and apply to every vertical.

    Each item additionally includes **pipeline_count** — the number of
    distinct pipeline_names observed for this vertical in the window.
    """
    summaries = vertical_health_summaries(
        db, tenant_id=tenant_id, lookback_days=lookback_days
    )
    return {
        "total": len(summaries),
        "lookback_days": lookback_days,
        "summary": {
            "healthy": sum(1 for s in summaries if s.health_status == "healthy"),
            "watch": sum(1 for s in summaries if s.health_status == "watch"),
            "unhealthy": sum(1 for s in summaries if s.health_status == "unhealthy"),
        },
        "items": [s.to_dict() for s in summaries],
    }
