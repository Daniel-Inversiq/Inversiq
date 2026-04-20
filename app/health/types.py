"""
app/health/types.py

Thresholds and output types for the pipeline/vertical health summary layer.

All thresholds are module-level constants — explicit and inspectable without
running the engine.  They are intentionally not exposed as query parameters:
the health summary is meant to give a stable, operator-facing signal, not an
ad-hoc configurable query.

Classification logic (first matching rule wins, per dimension):

  unhealthy  failed_rate >= 0.30
             needs_review_rate >= 0.40
             low_confidence_rate >= 0.50

  watch      failed_rate >= 0.10
             needs_review_rate >= 0.20
             low_confidence_rate >= 0.30
             any HIGH-severity intelligence signal

  healthy    none of the above
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

UNHEALTHY_FAILED_RATE: float = 0.30
UNHEALTHY_NEEDS_REVIEW_RATE: float = 0.40
UNHEALTHY_LOW_CONFIDENCE_RATE: float = 0.50

WATCH_FAILED_RATE: float = 0.10
WATCH_NEEDS_REVIEW_RATE: float = 0.20
WATCH_LOW_CONFIDENCE_RATE: float = 0.30


# ---------------------------------------------------------------------------
# Output shapes
# ---------------------------------------------------------------------------

@dataclass
class PipelineHealthSummary:
    """Aggregated health view for a single pipeline_name."""

    pipeline_name: str
    vertical_id: Optional[str]   # most-recent vertical seen for this pipeline
    tenant_id: Optional[str]
    total_runs: int
    failed_rate: float
    needs_review_rate: float
    low_confidence_rate: float
    signal_counts: dict           # {signal_type_str: count}
    health_status: str            # "healthy" | "watch" | "unhealthy"
    top_recommendation: str
    lookback_days: int
    computed_at: datetime

    def to_dict(self) -> dict:
        return {
            "pipeline_name": self.pipeline_name,
            "vertical_id": self.vertical_id,
            "tenant_id": self.tenant_id,
            "total_runs": self.total_runs,
            "failed_rate": round(self.failed_rate, 4),
            "needs_review_rate": round(self.needs_review_rate, 4),
            "low_confidence_rate": round(self.low_confidence_rate, 4),
            "signal_counts": self.signal_counts,
            "health_status": self.health_status,
            "top_recommendation": self.top_recommendation,
            "lookback_days": self.lookback_days,
            "computed_at": self.computed_at.isoformat(),
        }


@dataclass
class VerticalHealthSummary:
    """Aggregated health view for a single vertical_id."""

    vertical_id: str
    tenant_id: Optional[str]
    total_runs: int
    pipeline_count: int           # number of distinct pipeline_names observed
    failed_rate: float
    needs_review_rate: float
    low_confidence_rate: float
    signal_counts: dict
    health_status: str
    top_recommendation: str
    lookback_days: int
    computed_at: datetime

    def to_dict(self) -> dict:
        return {
            "vertical_id": self.vertical_id,
            "tenant_id": self.tenant_id,
            "total_runs": self.total_runs,
            "pipeline_count": self.pipeline_count,
            "failed_rate": round(self.failed_rate, 4),
            "needs_review_rate": round(self.needs_review_rate, 4),
            "low_confidence_rate": round(self.low_confidence_rate, 4),
            "signal_counts": self.signal_counts,
            "health_status": self.health_status,
            "top_recommendation": self.top_recommendation,
            "lookback_days": self.lookback_days,
            "computed_at": self.computed_at.isoformat(),
        }
