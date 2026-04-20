"""
app/intelligence/engine.py

Orchestrator for the rule intelligence layer.

run_all() executes every detector (or a single named one) and returns the
combined list of RuleSignal instances.  All thresholds are caller-supplied so
the endpoint can expose them as query parameters without needing any global
config mutation.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.intelligence.detectors import (
    detect_repeated_fallback       as _fallback,
    detect_overpricing             as _overpricing,
    detect_repeated_low_confidence as _low_conf,
    detect_repeated_review_flag    as _review_flag,
    detect_underpricing            as _underpricing,
)
from app.intelligence.types import RuleSignal, SignalType


def run_all(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lookback_days: int = 30,
    # Pricing signal params
    pricing_min_sample: int = 5,
    underpricing_threshold: float = 0.10,
    underpricing_min_fraction: float = 0.60,
    loss_rate_threshold: float = 0.60,
    # Confidence signal params
    confidence_low_threshold: float = 0.40,
    confidence_min_runs: int = 5,
    # Fallback signal params
    fallback_min_runs: int = 3,
    # Review-flag signal params
    review_min_runs: int = 3,
    # Optional single-type filter (mirrors anomaly engine pattern)
    signal_type: Optional[SignalType] = None,
) -> list[RuleSignal]:
    """
    Run all (or one named) signal detectors and return the combined results.

    Parameters
    ----------
    db              : Active SQLAlchemy session.
    tenant_id       : Scope results to a single tenant; None = all tenants.
    lookback_days   : How far back to look for patterns (default 30 days).
    signal_type     : If set, only that detector runs.
    ...             : Per-detector threshold overrides.

    Returns
    -------
    List of RuleSignal instances — may be empty if no patterns qualify.
    """
    detectors: list[tuple[SignalType, callable]] = [
        (
            SignalType.LIKELY_UNDERPRICING,
            lambda: _underpricing(
                db,
                tenant_id=tenant_id,
                lookback_days=lookback_days,
                min_sample=pricing_min_sample,
                threshold=underpricing_threshold,
                min_fraction=underpricing_min_fraction,
            ),
        ),
        (
            SignalType.LIKELY_OVERPRICING,
            lambda: _overpricing(
                db,
                tenant_id=tenant_id,
                lookback_days=lookback_days,
                min_sample=pricing_min_sample,
                loss_rate_threshold=loss_rate_threshold,
            ),
        ),
        (
            SignalType.REPEATED_LOW_CONFIDENCE,
            lambda: _low_conf(
                db,
                tenant_id=tenant_id,
                lookback_days=lookback_days,
                min_runs=confidence_min_runs,
                confidence_threshold=confidence_low_threshold,
            ),
        ),
        (
            SignalType.REPEATED_FALLBACK,
            lambda: _fallback(
                db,
                tenant_id=tenant_id,
                lookback_days=lookback_days,
                min_runs=fallback_min_runs,
            ),
        ),
        (
            SignalType.REPEATED_REVIEW_FLAG,
            lambda: _review_flag(
                db,
                tenant_id=tenant_id,
                lookback_days=lookback_days,
                min_runs=review_min_runs,
            ),
        ),
    ]

    signals: list[RuleSignal] = []
    for stype, fn in detectors:
        if signal_type is not None and stype != signal_type:
            continue
        signals.extend(fn())

    return signals
