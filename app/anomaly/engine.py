"""
Anomaly engine — runs all detectors and merges results.

Call ``run_all()`` to get every anomaly that fires across all detectors
for a given scope. Individual detectors can also be called directly if
you only need a specific anomaly type.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .detectors import (
    detect_confidence_absent_on_completion,
    detect_failed_high_confidence,
    detect_missing_step_output,
    detect_price_delta_large,
    detect_repeated_failure,
)
from .types import Anomaly, AnomalyType


def run_all(
    db: Session,
    *,
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
    # Detector-level thresholds — callers may override defaults.
    price_delta_threshold: float = 0.50,
    confidence_threshold: float = 0.60,
    repeat_failure_window_hours: int = 24,
    repeat_failure_min_count: int = 3,
    # Optionally restrict to a single anomaly type.
    anomaly_type: Optional[AnomalyType] = None,
) -> list[Anomaly]:
    """
    Run all (or a single named) anomaly detector and return merged results.

    Parameters
    ----------
    db                          : SQLAlchemy session.
    tenant_id                   : Scope to one tenant.
    lead_id                     : Scope to one lead (not all detectors support this).
    pipeline_run_id             : Scope to a single run (debug mode).
    price_delta_threshold       : Fraction above which price delta is anomalous (default 0.50).
    confidence_threshold        : Minimum score that makes a FAILED run contradictory (default 0.60).
    repeat_failure_window_hours : Lookback window for the repeated-failure detector (default 24h).
    repeat_failure_min_count    : Minimum failure count within the window (default 3).
    anomaly_type                : If set, only that detector runs.
    """
    results: list[Anomaly] = []

    _common = dict(
        tenant_id=tenant_id,
        lead_id=lead_id,
        pipeline_run_id=pipeline_run_id,
    )

    if anomaly_type is None or anomaly_type == AnomalyType.PRICE_DELTA_LARGE:
        results.extend(
            detect_price_delta_large(db, **_common, threshold=price_delta_threshold)
        )

    if anomaly_type is None or anomaly_type == AnomalyType.FAILED_HIGH_CONFIDENCE:
        results.extend(
            detect_failed_high_confidence(
                db, **_common, confidence_threshold=confidence_threshold
            )
        )

    if anomaly_type is None or anomaly_type == AnomalyType.MISSING_STEP_OUTPUT:
        results.extend(detect_missing_step_output(db, **_common))

    if anomaly_type is None or anomaly_type == AnomalyType.CONFIDENCE_ABSENT_ON_COMPLETION:
        results.extend(detect_confidence_absent_on_completion(db, **_common))

    if anomaly_type is None or anomaly_type == AnomalyType.REPEATED_FAILURE:
        # repeated_failure is tenant-level; lead_id / pipeline_run_id do not apply.
        results.extend(
            detect_repeated_failure(
                db,
                tenant_id=tenant_id,
                window_hours=repeat_failure_window_hours,
                min_failures=repeat_failure_min_count,
            )
        )

    return results
