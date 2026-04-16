"""
Anomaly detection — shared types.

An Anomaly is a read-only observation derived from existing stored data.
Nothing here mutates the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AnomalyType(str, Enum):
    # Business signal: actual price diverged significantly from estimate.
    PRICE_DELTA_LARGE = "PRICE_DELTA_LARGE"
    # Contradictory signal: run FAILED despite high/medium reported confidence.
    FAILED_HIGH_CONFIDENCE = "FAILED_HIGH_CONFIDENCE"
    # Data quality: a COMPLETED step produced no output snapshot.
    MISSING_STEP_OUTPUT = "MISSING_STEP_OUTPUT"
    # Coverage gap: a COMPLETED run has no confidence score at all.
    CONFIDENCE_ABSENT_ON_COMPLETION = "CONFIDENCE_ABSENT_ON_COMPLETION"
    # Operational: same pipeline is failing repeatedly for the same tenant.
    REPEATED_FAILURE = "REPEATED_FAILURE"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Anomaly:
    """
    One detected anomaly instance.

    Fields
    ------
    anomaly_type    : Which rule fired.
    severity        : Operational urgency.
    description     : Human-readable explanation of why this is anomalous.
    context         : Detector-specific key/value evidence (thresholds, counts, etc.).

    Soft references — nullable; present only when the anomaly originates from a
    specific record. Callers can use these to join back to existing debug endpoints.
    """

    anomaly_type: AnomalyType
    severity: Severity
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    pipeline_run_id: Optional[int] = None
    pipeline_step_run_id: Optional[int] = None
    lead_id: Optional[str] = None
    tenant_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        review_recommended, action_hint = _triage_anomaly(self)
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "context": self.context,
            "review_recommended": review_recommended,
            "action_hint": action_hint,
            "pipeline_run_id": self.pipeline_run_id,
            "pipeline_step_run_id": self.pipeline_step_run_id,
            "lead_id": self.lead_id,
            "tenant_id": self.tenant_id,
        }


# ---------------------------------------------------------------------------
# Triage — deterministic, rule-based per anomaly type.
# Lives here to avoid circular imports (triage needs AnomalyType; Anomaly
# needs triage). No external state, no DB calls.
# ---------------------------------------------------------------------------

def _triage_anomaly(anomaly: Anomaly) -> tuple[bool, str]:
    """
    Return ``(review_recommended, action_hint)`` for *anomaly*.

    Rules are explicit per AnomalyType. The second element is a short,
    operator-facing sentence — enough to decide the next action without
    opening the full debug payload.
    """
    t = anomaly.anomaly_type
    ctx = anomaly.context

    if t == AnomalyType.PRICE_DELTA_LARGE:
        return (
            True,
            "Review the pricing estimate for this lead — the actual price "
            "diverged materially from the model output.",
        )

    if t == AnomalyType.FAILED_HIGH_CONFIDENCE:
        ec = ctx.get("error_category")
        if ec in ("transient", "external_dependency"):
            return (
                True,
                "Retry candidate — the pipeline had high confidence before "
                "failing on a likely transient error.",
            )
        return (
            True,
            "Investigate the failure step — the confidence model predicted "
            "success but the run failed.",
        )

    if t == AnomalyType.MISSING_STEP_OUTPUT:
        return (
            True,
            "Inspect the step implementation for a silent early return — "
            "output_snapshot was not persisted on a COMPLETED step.",
        )

    if t == AnomalyType.CONFIDENCE_ABSENT_ON_COMPLETION:
        return (
            False,
            "Add confidence reporting to at least one pipeline step — "
            "no confidence score was propagated on this completed run.",
        )

    if t == AnomalyType.REPEATED_FAILURE:
        categories: set[str] = set(ctx.get("error_categories") or [])
        if categories and categories <= {"transient", "external_dependency"}:
            return (
                True,
                "Check infrastructure health — repeated transient failures "
                "may indicate environmental instability.",
            )
        if categories and categories <= {"permanent", "validation"}:
            return (
                True,
                "Fix the pipeline bug — this is a systematic, permanent "
                "failure pattern.",
            )
        return (
            True,
            "Investigate systematic pipeline breakage — the same pipeline "
            "has failed repeatedly within the detection window.",
        )

    # Fallback: every known type is handled above; this guards future additions.
    return (True, "Review this anomaly — no specific action hint is available.")
