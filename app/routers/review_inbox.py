"""
app/routers/review_inbox.py

GET /api/review-inbox — read-only review inbox query surface.

Returns PipelineRun records that need operator review, each with a flat,
inspectable shape including priority, reason, confidence, and anomaly count.

All thresholds and scoring come from the existing anomaly and run-review
layers — nothing is re-implemented here.  This endpoint does not modify
any state.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.review_inbox.query import build_inbox_items

router = APIRouter(prefix="/api/review-inbox", tags=["review-inbox"])


@router.get("")
def get_review_inbox(
    tenant_id: Optional[str] = Query(
        None, description="Scope to a single tenant"
    ),
    status: Optional[str] = Query(
        None,
        description=(
            "Filter by pipeline status (FAILED, NEEDS_REVIEW, COMPLETED, RUNNING). "
            "When set, the candidate pre-filter is bypassed so any status class "
            "can be inspected."
        ),
    ),
    priority: Optional[str] = Query(
        None,
        description="Post-filter by computed review priority (high, medium, low)",
    ),
    review_recommended_only: bool = Query(
        True,
        description=(
            "Return only runs where review is recommended (default true). "
            "Set false to include all candidate runs — useful for auditing the "
            "pre-filter or inspecting borderline cases."
        ),
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Review inbox: list pipeline runs that need operator review.

    Each item in ``items`` contains:

    - **pipeline_run_id** — use with ``GET /api/pipeline-runs/{id}/debug``
      for the full debug payload including step snapshots and event timeline.
    - **review_priority** — ``high`` / ``medium`` / ``low`` — derived from
      pipeline status, error category, confidence label, and anomaly severity.
    - **review_reason** — one-sentence explanation of why review is needed.
    - **confidence** — overall pipeline confidence score (null if no step
      reported one).
    - **anomaly_count** — number of anomalies detected on this run.

    Results are sorted by priority (high first) then newest-first within
    each tier.

    **Pre-filter**: by default only FAILED, NEEDS_REVIEW, and low-confidence
    runs are candidates. Pass ``status`` to override (e.g. inspect COMPLETED
    runs). Anomaly-only review cases on otherwise healthy runs are not
    pre-filtered — use the per-run debug endpoint for those.
    """
    items = build_inbox_items(
        db,
        tenant_id=tenant_id,
        status=status,
        priority=priority,
        review_recommended_only=review_recommended_only,
        limit=limit,
        offset=offset,
    )

    priority_summary: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for item in items:
        p = item.get("review_priority")
        if p in priority_summary:
            priority_summary[p] += 1

    return {
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "summary": priority_summary,
        "items": items,
    }
