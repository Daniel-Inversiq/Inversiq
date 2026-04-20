"""
app/services/proposal_execution_outcome.py

Persistence and deterministic evaluation logic for post-apply outcome records.

Design:
  - One outcome record per (tenant_id, execution_request_id) — re-recording
    overwrites the previous record.  This models "latest known observation"
    rather than an append-only audit log.
  - evaluation_status is always server-computed; callers supply outcome_status
    and observed_metrics_snapshot.
  - All classification logic is deterministic and threshold-based.  No ML,
    no probabilistic scoring.

Evaluation model:
  Each metric in observed_metrics_snapshot may be:
    - A scalar (e.g. {"failed_rate": 0.08}) — comparison not possible; skipped.
    - A structured object:
        {
          "value":     <float>,    # observed value
          "baseline":  <float>,    # expected / prior value
          "direction": "lower_is_better" | "higher_is_better"
        }

  Delta is computed as signed_degradation:
    lower_is_better  → (value - baseline) / |baseline|   positive = bad
    higher_is_better → (baseline - value) / |baseline|   positive = bad

  Classification thresholds:
    IMPROVED_THRESHOLD  = 0.02  (2% improvement needed to count as "improved")
    DEGRADED_THRESHOLD  = 0.05  (5% worsening → degraded)
    UNSTABLE_THRESHOLD  = 0.10  (10% worsening → unstable + rollback triggered)

  Final evaluation_status:
    unstable  — any metric has signed_degradation ≥ UNSTABLE_THRESHOLD
    degraded  — any metric has signed_degradation ≥ DEGRADED_THRESHOLD
    improved  — all evaluable metrics have signed_degradation ≤ −IMPROVED_THRESHOLD
                (i.e., meaningful improvement) and none are degraded
    neutral   — otherwise (no clear signal or changes within noise)

All service functions operate within the caller's DB session and do NOT commit.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.proposed_change_execution_outcome import ProposedChangeExecutionOutcome
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification thresholds
# ---------------------------------------------------------------------------

_IMPROVED_THRESHOLD = 0.02
_DEGRADED_THRESHOLD = 0.05
_UNSTABLE_THRESHOLD = 0.10

_VALID_OUTCOME_STATUSES = {"success", "partial", "failed"}
_VALID_EVALUATION_STATUSES = {"improved", "neutral", "degraded", "unstable"}


# ---------------------------------------------------------------------------
# Deterministic evaluation
# ---------------------------------------------------------------------------


def evaluate_execution_outcome(
    *,
    monitoring_plan_snapshot: dict[str, Any],
    observed_metrics_snapshot: dict[str, Any],
    expected_metrics_snapshot: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Evaluate observed metrics against the monitoring plan deterministically.

    Returns a dict with:
      - evaluation_status: improved | neutral | degraded | unstable
      - deviation_snapshot: per-metric analysis
      - rollback_triggered: bool
      - rollback_reason: str | None
    """
    metrics_to_watch: list[str] = monitoring_plan_snapshot.get("metrics_to_watch", [])

    deviations: dict[str, Any] = {}
    degraded_metrics: list[str] = []
    unstable_metrics: list[str] = []
    improved_metrics: list[str] = []
    evaluable_count = 0

    for metric in metrics_to_watch:
        raw = observed_metrics_snapshot.get(metric)
        if raw is None:
            deviations[metric] = {"verdict": "missing"}
            continue

        if not isinstance(raw, dict):
            deviations[metric] = {"value": raw, "verdict": "no_baseline"}
            continue

        value = raw.get("value")
        baseline = raw.get("baseline")
        direction = raw.get("direction")

        if value is None or baseline is None or direction is None:
            deviations[metric] = {"raw": raw, "verdict": "incomplete"}
            continue

        if baseline == 0:
            deviations[metric] = {
                "value": value,
                "baseline": baseline,
                "direction": direction,
                "verdict": "zero_baseline",
            }
            continue

        evaluable_count += 1

        if direction == "lower_is_better":
            signed_degradation = (value - baseline) / abs(baseline)
        else:
            signed_degradation = (baseline - value) / abs(baseline)

        delta_pct = round(signed_degradation * 100, 2)

        if signed_degradation >= _UNSTABLE_THRESHOLD:
            verdict = "unstable"
            unstable_metrics.append(metric)
        elif signed_degradation >= _DEGRADED_THRESHOLD:
            verdict = "degraded"
            degraded_metrics.append(metric)
        elif signed_degradation <= -_IMPROVED_THRESHOLD:
            verdict = "improved"
            improved_metrics.append(metric)
        else:
            verdict = "neutral"

        deviations[metric] = {
            "value": value,
            "baseline": baseline,
            "direction": direction,
            "delta_pct": delta_pct,
            "verdict": verdict,
        }

    # Determine rollback
    rollback_triggered = len(unstable_metrics) > 0
    rollback_reason: Optional[str] = None
    if rollback_triggered:
        worst = unstable_metrics[0]
        info = deviations[worst]
        rollback_reason = (
            f"{worst} worsened by {info['delta_pct']:.1f}% "
            f"(rollback threshold: {_UNSTABLE_THRESHOLD * 100:.0f}%)"
        )

    # Classify evaluation_status
    if unstable_metrics:
        evaluation_status = "unstable"
    elif degraded_metrics:
        evaluation_status = "degraded"
    elif evaluable_count > 0 and len(improved_metrics) == evaluable_count:
        evaluation_status = "improved"
    else:
        evaluation_status = "neutral"

    return {
        "evaluation_status": evaluation_status,
        "deviation_snapshot": deviations,
        "rollback_triggered": rollback_triggered,
        "rollback_reason": rollback_reason,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def record_execution_outcome(
    db: Session,
    *,
    execution_request: ProposedChangeExecutionRequest,
    outcome_status: str,
    observed_metrics_snapshot: dict[str, Any],
    expected_metrics_snapshot: Optional[dict[str, Any]] = None,
) -> ProposedChangeExecutionOutcome:
    """
    Persist (or overwrite) an outcome observation for an execution request.

    One record per (tenant_id, execution_request_id) — re-recording replaces
    the previous observation.  evaluation_status is server-computed.

    Does NOT commit — caller owns the transaction.
    """
    if outcome_status not in _VALID_OUTCOME_STATUSES:
        raise ValueError(
            f"Invalid outcome_status '{outcome_status}'. "
            f"Must be one of: {sorted(_VALID_OUTCOME_STATUSES)}"
        )

    monitoring_plan: dict[str, Any] = {}
    if execution_request.monitoring_plan_snapshot:
        try:
            monitoring_plan = json.loads(execution_request.monitoring_plan_snapshot)
        except (json.JSONDecodeError, TypeError):
            _log.warning(
                "Could not parse monitoring_plan_snapshot for request id=%s",
                execution_request.id,
            )

    evaluation = evaluate_execution_outcome(
        monitoring_plan_snapshot=monitoring_plan,
        observed_metrics_snapshot=observed_metrics_snapshot,
        expected_metrics_snapshot=expected_metrics_snapshot,
    )

    observed_json = json.dumps(observed_metrics_snapshot)
    expected_json = json.dumps(expected_metrics_snapshot) if expected_metrics_snapshot else None
    deviation_json = json.dumps(evaluation["deviation_snapshot"])

    existing = (
        db.query(ProposedChangeExecutionOutcome)
        .filter(
            ProposedChangeExecutionOutcome.tenant_id == execution_request.tenant_id,
            ProposedChangeExecutionOutcome.execution_request_id == execution_request.id,
        )
        .first()
    )

    if existing is not None:
        existing.outcome_status = outcome_status
        existing.evaluation_status = evaluation["evaluation_status"]
        existing.observed_metrics_snapshot = observed_json
        existing.expected_metrics_snapshot = expected_json
        existing.deviation_snapshot = deviation_json
        existing.rollback_triggered = evaluation["rollback_triggered"]
        existing.rollback_reason = evaluation["rollback_reason"]
        return existing

    outcome = ProposedChangeExecutionOutcome(
        tenant_id=execution_request.tenant_id,
        execution_request_id=execution_request.id,
        change_id=execution_request.change_id,
        scope_type=execution_request.scope_type,
        scope_id=execution_request.scope_id,
        outcome_status=outcome_status,
        evaluation_status=evaluation["evaluation_status"],
        observed_metrics_snapshot=observed_json,
        expected_metrics_snapshot=expected_json,
        deviation_snapshot=deviation_json,
        rollback_triggered=evaluation["rollback_triggered"],
        rollback_reason=evaluation["rollback_reason"],
    )
    db.add(outcome)
    return outcome
