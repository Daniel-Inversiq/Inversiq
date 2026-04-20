"""
app/intelligence/types.py

Shared types for the rule intelligence layer.

A RuleSignal is a tenant-level improvement suggestion derived from recurring
patterns in stored data (LeadFeedback, PipelineRun, PipelineStepRun).

Design constraints
------------------
- Deterministic and rule-based — no ML, no probabilistic models.
- Read-only — never mutates the database.
- Does not auto-modify rules or configs; suggestions only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SignalType(str, Enum):
    # Pricing patterns derived from LeadFeedback
    LIKELY_UNDERPRICING = "likely_underpricing"
    LIKELY_OVERPRICING = "likely_overpricing"
    # Execution patterns derived from PipelineStepRun
    REPEATED_LOW_CONFIDENCE = "repeated_low_confidence"
    REPEATED_FALLBACK = "repeated_fallback"
    # Pipeline-level patterns derived from PipelineRun
    REPEATED_REVIEW_FLAG = "repeated_review_flag"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RuleSignal:
    """
    One detected improvement signal.

    Fields
    ------
    signal_type      : Which rule fired.
    severity         : Operational priority for the suggestion.
    description      : Human-readable explanation of the pattern detected.
    suggested_action : Concrete operator-facing next step.
    context          : Rule-specific key/value evidence (thresholds, counts, etc.).

    Soft references — nullable; present when the signal applies to a specific
    pipeline or tenant scope.
    """

    signal_type: SignalType
    severity: Severity
    description: str
    suggested_action: str
    context: dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[str] = None
    pipeline_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "severity": self.severity,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "context": self.context,
            "tenant_id": self.tenant_id,
            "pipeline_name": self.pipeline_name,
        }
