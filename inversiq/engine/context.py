# aether/engine/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict
import uuid
import time


# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------

def confidence_label(score: float) -> str:
    """Derive a human-readable label from a 0–1 confidence score.

    Thresholds align with needs_review.py (needs_review_from_output):
      < 0.45  → "low"    (same as confidence_low soft signal)
      < 0.65  → "medium" (same as confidence_medium soft signal)
      >= 0.65 → "high"
    """
    if score < 0.45:
        return "low"
    if score < 0.65:
        return "medium"
    return "high"


@dataclass(frozen=True)
class ConfidenceResult:
    """Optional confidence annotation a step may attach to its result.

    Steps are never required to provide this; the runner persists it when
    present and propagates an overall score to the PipelineRun.

    Fields:
      score   — 0.0 (no confidence) to 1.0 (fully confident)
      label   — auto-derived from score via confidence_label(); not a constructor arg
      reason  — optional plain-text explanation (e.g. "fallback rule used")

    Usage::
        ConfidenceResult(score=0.72)
        ConfidenceResult(score=0.38, reason="fallback rule used")
    """
    score: float                      # 0.0–1.0
    reason: Optional[str] = None
    # label is intentionally excluded from __init__ and derived from score
    # in __post_init__ so that score/label can never disagree.
    label: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", confidence_label(self.score))


class StepContract(TypedDict, total=False):
    """
    Lightweight contract declaration for a pipeline step.

    Attach to a step function as ``fn.__step_contract__ = StepContract(...)``.
    The runner reads it after each execution and warns (never blocks) when a
    declared ``produces`` key is missing from the step output.

    Fields:
      produces  — result.data keys this step must populate on success.
                  A warning is logged for every missing key; the pipeline
                  continues regardless (contracts are advisory, not hard gates).
      version   — semantic version of this step implementation
                  (e.g. "1.0", "2.1").  Persisted on PipelineStepRun for
                  reproducibility queries.

    Example::

        step_estimate_v1.__step_contract__ = StepContract(
            produces=["estimate_json"],
            version="1.0",
        )
    """

    produces: List[str]   # required keys in result.data on OK/NEEDS_REVIEW
    version: str          # semantic version of this step implementation


@dataclass(frozen=True)
class EngineContext:
    tenant_id: str
    vertical_id: str
    lead_id: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    branch_id: Optional[str] = None  # v1.5 roadmap: tenant/branch context
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass
class StepResult:
    status: str  # "OK" | "NEEDS_REVIEW" | "FAILED"
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    # Optional — steps that have natural confidence information may populate this.
    # Steps that don't provide it leave it as None; the runner skips it silently.
    confidence: Optional[ConfidenceResult] = None


@dataclass
class PipelineState:
    """
    Mutable state bag during one run.
    Keep it JSON-serializable (store in DB per step if you want).
    """

    context: EngineContext
    data: Dict[str, Any] = field(default_factory=dict)  # evolving payload
    logs: list[dict] = field(default_factory=list)  # structured log events
    status: str = "RUNNING"  # RUNNING | SUCCEEDED | NEEDS_REVIEW | FAILED
    failure_step: Optional[str] = None
