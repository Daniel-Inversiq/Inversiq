"""
Read-only internal metrics surface for business and operational feedback.

These are debug/ops-oriented aggregate queries over existing records.
No ML, no scoring, no dashboards — just queryable numbers.

Endpoints:
  GET /api/metrics/business             — overall summary
  GET /api/metrics/business/by-vertical — breakdown by vertical_id
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun

router = APIRouter(prefix="/api/metrics/business", tags=["business-metrics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feedback_base(db: Session, tenant_id: Optional[str]):
    q = db.query(LeadFeedback)
    if tenant_id:
        q = q.filter(LeadFeedback.tenant_id == tenant_id)
    return q


def _pipeline_base(db: Session, tenant_id: Optional[str]):
    q = db.query(PipelineRun)
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id)
    return q


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def business_metrics_summary(
    tenant_id: Optional[str] = Query(default=None, description="Scope to a single tenant"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Overall business + pipeline metrics.

    Feedback metrics come from ``lead_feedback``.
    Pipeline metrics come from ``pipeline_runs``.
    """
    # --- Feedback: win / loss counts ---
    outcome_rows = (
        _feedback_base(db, tenant_id)
        .with_entities(LeadFeedback.outcome, func.count().label("cnt"))
        .group_by(LeadFeedback.outcome)
        .all()
    )
    outcome_map: dict[str, int] = {row.outcome: row.cnt for row in outcome_rows}
    wins = outcome_map.get("won", 0)
    losses = outcome_map.get("lost", 0)
    total_feedback = wins + losses

    # --- Feedback: average actual vs estimated price delta ---
    # Only rows where both prices are present are included.
    avg_delta = (
        _feedback_base(db, tenant_id)
        .filter(
            LeadFeedback.actual_price.isnot(None),
            LeadFeedback.estimated_price.isnot(None),
        )
        .with_entities(
            func.avg(LeadFeedback.actual_price - LeadFeedback.estimated_price)
        )
        .scalar()
    )

    # --- Pipeline: counts by status ---
    status_rows = (
        _pipeline_base(db, tenant_id)
        .with_entities(PipelineRun.status, func.count().label("cnt"))
        .group_by(PipelineRun.status)
        .all()
    )
    by_status: dict[str, int] = {row.status: row.cnt for row in status_rows}
    pipeline_total = sum(by_status.values())

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "filters": {"tenant_id": tenant_id},
        "feedback": {
            "total": total_feedback,
            "won": wins,
            "lost": losses,
            "win_rate": round(wins / total_feedback, 3) if total_feedback else None,
            # Positive delta → actual > estimated (under-priced). Negative → over-estimated.
            "avg_price_delta": (
                round(float(avg_delta), 2) if avg_delta is not None else None
            ),
        },
        "pipeline": {
            "total": pipeline_total,
            "failed": by_status.get("FAILED", 0),
            "needs_review": by_status.get("NEEDS_REVIEW", 0),
            "by_status": by_status,
        },
    }


@router.get("/by-vertical")
def business_metrics_by_vertical(
    tenant_id: Optional[str] = Query(default=None, description="Scope to a single tenant"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Pipeline and feedback counts grouped by ``vertical_id``.

    Feedback breakdown requires a linked ``pipeline_run_id`` to resolve the
    vertical — feedback rows without one are excluded from this view.
    """
    # Pipeline: (vertical_id, status, count)
    pl_rows = (
        _pipeline_base(db, tenant_id)
        .with_entities(
            PipelineRun.vertical_id,
            PipelineRun.status,
            func.count().label("cnt"),
        )
        .group_by(PipelineRun.vertical_id, PipelineRun.status)
        .all()
    )

    # Feedback joined to pipeline_runs to get vertical_id.
    # LeadFeedback rows without a pipeline_run_id are silently excluded.
    fb_q = (
        db.query(
            PipelineRun.vertical_id,
            LeadFeedback.outcome,
            func.count().label("cnt"),
        )
        .join(PipelineRun, PipelineRun.id == LeadFeedback.pipeline_run_id)
        .group_by(PipelineRun.vertical_id, LeadFeedback.outcome)
    )
    if tenant_id:
        fb_q = fb_q.filter(LeadFeedback.tenant_id == tenant_id)
    fb_rows = fb_q.all()

    # Assemble per-vertical dict
    verticals: dict[str, dict[str, Any]] = {}

    for row in pl_rows:
        v = verticals.setdefault(
            row.vertical_id,
            {"pipeline": {}, "feedback": {"won": 0, "lost": 0}},
        )
        v["pipeline"][row.status] = row.cnt

    for row in fb_rows:
        v = verticals.setdefault(
            row.vertical_id,
            {"pipeline": {}, "feedback": {"won": 0, "lost": 0}},
        )
        v["feedback"][row.outcome] = row.cnt

    items = []
    for vertical_id, data in sorted(verticals.items()):
        fb = data["feedback"]
        total_fb = fb.get("won", 0) + fb.get("lost", 0)
        pl = data["pipeline"]
        items.append(
            {
                "vertical_id": vertical_id,
                "pipeline": {
                    "total": sum(pl.values()),
                    "failed": pl.get("FAILED", 0),
                    "needs_review": pl.get("NEEDS_REVIEW", 0),
                    "by_status": pl,
                },
                "feedback": {
                    "total": total_fb,
                    "won": fb.get("won", 0),
                    "lost": fb.get("lost", 0),
                    "win_rate": (
                        round(fb.get("won", 0) / total_fb, 3) if total_fb else None
                    ),
                },
            }
        )

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "filters": {"tenant_id": tenant_id},
        "items": items,
    }
