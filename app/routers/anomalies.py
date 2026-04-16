"""
Read-only anomaly detection surface.

Endpoints:
  GET /api/anomalies  — run all (or one) anomaly detector, return results
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.anomaly.engine import run_all
from app.anomaly.types import AnomalyType

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("")
def list_anomalies(
    # Scope filters
    tenant_id: Optional[str] = Query(default=None, description="Scope to one tenant"),
    lead_id: Optional[str] = Query(default=None, description="Scope to one lead"),
    pipeline_run_id: Optional[int] = Query(
        default=None, description="Scope to a single pipeline run (debug mode)"
    ),
    # Anomaly type filter
    anomaly_type: Optional[AnomalyType] = Query(
        default=None,
        description=(
            "Run only this detector. One of: "
            + ", ".join(t.value for t in AnomalyType)
        ),
    ),
    # Threshold overrides
    price_delta_threshold: float = Query(
        default=0.50,
        ge=0.01,
        le=10.0,
        description="Fraction above which actual/estimated price delta is anomalous (default 0.50 = 50%)",
    ),
    confidence_threshold: float = Query(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Min confidence score that makes a FAILED run contradictory (default 0.60)",
    ),
    repeat_failure_window_hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Lookback window in hours for REPEATED_FAILURE detector (default 24)",
    ),
    repeat_failure_min_count: int = Query(
        default=3,
        ge=2,
        le=100,
        description="Min failures within the window to trigger REPEATED_FAILURE (default 3)",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Compute and return detected anomalies from existing execution, feedback,
    and confidence data.

    All detectors are deterministic and rule-based — no ML models.
    Results are computed on-demand; nothing is persisted.

    Each anomaly includes:
    - ``anomaly_type``         — which rule fired
    - ``severity``             — low | medium | high
    - ``description``          — human-readable explanation
    - ``context``              — detector-specific evidence (thresholds, counts, values)
    - Soft references (``pipeline_run_id``, ``lead_id``, ``tenant_id``) for cross-linking

    Detectors run:
    - **PRICE_DELTA_LARGE** — large actual vs estimated price gap in feedback
    - **FAILED_HIGH_CONFIDENCE** — contradictory: run FAILED with high confidence score
    - **MISSING_STEP_OUTPUT** — COMPLETED step has no output_snapshot persisted
    - **CONFIDENCE_ABSENT_ON_COMPLETION** — COMPLETED run with no confidence score at all
    - **REPEATED_FAILURE** — same pipeline failing repeatedly for the same tenant
    """
    anomalies = run_all(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        pipeline_run_id=pipeline_run_id,
        anomaly_type=anomaly_type,
        price_delta_threshold=price_delta_threshold,
        confidence_threshold=confidence_threshold,
        repeat_failure_window_hours=repeat_failure_window_hours,
        repeat_failure_min_count=repeat_failure_min_count,
    )

    # Group counts by type for the summary.
    counts: dict[str, int] = {}
    for a in anomalies:
        counts[a.anomaly_type] = counts.get(a.anomaly_type, 0) + 1

    return {
        "total": len(anomalies),
        "summary": counts,
        "items": [a.to_dict() for a in anomalies],
    }
