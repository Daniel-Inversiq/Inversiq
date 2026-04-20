"""
app/routers/intelligence.py

GET /api/intelligence/signals — read-only rule intelligence query surface.

Returns tenant-level improvement signals derived from recurring patterns in
stored LeadFeedback, PipelineRun, and PipelineStepRun data.  All thresholds
are exposed as query parameters so operators can tune sensitivity without
code changes.

All signals are suggestions only — nothing is auto-modified.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.intelligence.engine import run_all
from app.intelligence.types import SignalType

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("/signals")
def get_signals(
    # Scope
    tenant_id: Optional[str] = Query(None, description="Scope to a single tenant"),
    lookback_days: int = Query(30, ge=1, le=365, description="Days of history to scan"),
    # Pricing thresholds
    pricing_min_sample: int = Query(
        5, ge=1, description="Min feedback records required to emit a pricing signal"
    ),
    underpricing_threshold: float = Query(
        0.10, ge=0.01, le=1.0,
        description="Fraction below estimate that counts as underpriced (default 10%)",
    ),
    underpricing_min_fraction: float = Query(
        0.60, ge=0.01, le=1.0,
        description="Min fraction of won deals that must be underpriced to fire",
    ),
    loss_rate_threshold: float = Query(
        0.60, ge=0.01, le=1.0,
        description="Loss rate above which likely_overpricing fires (default 60%)",
    ),
    # Confidence thresholds
    confidence_low_threshold: float = Query(
        0.40, ge=0.01, le=1.0,
        description="Score below which a step run is considered low-confidence",
    ),
    confidence_min_runs: int = Query(
        5, ge=1, description="Min low-confidence step runs to emit a signal"
    ),
    # Fallback threshold
    fallback_min_runs: int = Query(
        3, ge=1, description="Min fallback step runs to emit a repeated_fallback signal"
    ),
    # Review-flag threshold
    review_min_runs: int = Query(
        3, ge=1, description="Min NEEDS_REVIEW pipeline runs to emit a signal"
    ),
    # Type filter
    signal_type: Optional[SignalType] = Query(
        None, description="Run only this detector (omit to run all)"
    ),
    db: Session = Depends(get_db),
) -> dict:
    """
    Query the rule intelligence layer for improvement signals.

    Returns a summary envelope and a list of RuleSignal items, each with:
    - **signal_type** — which pattern was detected
    - **severity** — low / medium / high
    - **description** — human-readable pattern explanation
    - **suggested_action** — concrete next step for the operator
    - **context** — thresholds, counts, and averages used to derive the signal
    - **tenant_id** — the tenant this signal applies to
    - **pipeline_name** — set for pipeline-level signals, null otherwise
    """
    signals = run_all(
        db,
        tenant_id=tenant_id,
        lookback_days=lookback_days,
        pricing_min_sample=pricing_min_sample,
        underpricing_threshold=underpricing_threshold,
        underpricing_min_fraction=underpricing_min_fraction,
        loss_rate_threshold=loss_rate_threshold,
        confidence_low_threshold=confidence_low_threshold,
        confidence_min_runs=confidence_min_runs,
        fallback_min_runs=fallback_min_runs,
        review_min_runs=review_min_runs,
        signal_type=signal_type,
    )

    summary: dict[str, int] = {}
    for s in signals:
        summary[s.signal_type] = summary.get(s.signal_type, 0) + 1

    return {
        "total": len(signals),
        "lookback_days": lookback_days,
        "summary": summary,
        "items": [s.to_dict() for s in signals],
    }
