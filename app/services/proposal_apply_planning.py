"""
app/services/proposal_apply_planning.py

Deterministic apply planning layer (v1).

Accepts proposals plus their governance context and returns guarded execution
planning objects. Pure function — no DB access, no state mutations, no ML.

Each proposal is evaluated against explicit planning rules to determine:
- whether it can enter apply planning
- what preflight checks must pass
- what execution sequence to follow
- what rollback guidance applies
- what dependencies or blockers remain

Output is stable: identical inputs always produce identical output.
This is NOT execution. This is NOT approval. It is a guarded planning layer.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Planning status constants
# ---------------------------------------------------------------------------

PLANNED = "planned"
BLOCKED_FROM_PLANNING = "blocked_from_planning"
REQUIRES_COMBINED_PLAN = "requires_combined_plan"

# ---------------------------------------------------------------------------
# Rule tables
# ---------------------------------------------------------------------------

_HARD_BLOCK_STALENESS: frozenset[str] = frozenset({"stale", "superseded"})
_COMBINED_PLAN_CONFLICT_TYPES: frozenset[str] = frozenset(
    {"same_target_overlap", "policy_area_overlap", "high_risk_combination"}
)

# ---------------------------------------------------------------------------
# Preflight check mappings per change_type
# ---------------------------------------------------------------------------

_BASE_PREFLIGHT: list[str] = [
    "Confirm proposal approval_readiness is approval_ready.",
    "Confirm no high-severity conflicts are present.",
    "Confirm staleness status is fresh.",
]

_PREFLIGHT_BY_CHANGE_TYPE: dict[str, list[str]] = {
    "threshold_adjustment": [
        *_BASE_PREFLIGHT,
        "Confirm failed_rate is stable.",
        "Confirm low_confidence_rate is not sharply worsening.",
        "Confirm threshold bounds are available.",
    ],
    "pricing_guardrail_adjustment": [
        *_BASE_PREFLIGHT,
        "Confirm underpricing signal is still active.",
        "Confirm conversion/win-rate is not already degrading sharply.",
        "Confirm margin bounds remain valid.",
    ],
    "validation_policy_adjustment": [
        *_BASE_PREFLIGHT,
        "Confirm upstream_input_quality reasoning is still present.",
        "Confirm fallback pressure remains elevated.",
        "Confirm throughput risk is acknowledged.",
    ],
    "fallback_policy_adjustment": [
        *_BASE_PREFLIGHT,
        "Confirm repeated fallback signal is still active.",
        "Confirm fallback-related failures are separately understood.",
    ],
    "review_trigger_adjustment": [
        *_BASE_PREFLIGHT,
        "Confirm review pressure remains elevated.",
        "Confirm failure metrics remain stable.",
        "Confirm low-risk workflow scope.",
    ],
}

_DEFAULT_PREFLIGHT: list[str] = [
    *_BASE_PREFLIGHT,
    "Confirm proposal fields are complete and bounded_range is present.",
]

# ---------------------------------------------------------------------------
# Rollback plan mappings per change_type
# ---------------------------------------------------------------------------

_ROLLBACK_BY_CHANGE_TYPE: dict[str, list[str]] = {
    "threshold_adjustment": [
        "Revert if failed_rate worsens in the next comparison window.",
        "Revert if low-confidence escapes increase.",
    ],
    "pricing_guardrail_adjustment": [
        "Revert if win_rate drops materially while underpricing normalizes.",
    ],
    "validation_policy_adjustment": [
        "Revert if throughput drops too sharply.",
        "Revert if early validation rejects spike unexpectedly.",
    ],
    "fallback_policy_adjustment": [
        "Revert if fallback resilience does not improve.",
        "Revert if new failure patterns emerge.",
    ],
    "review_trigger_adjustment": [
        "Revert if review queue pressure worsens.",
        "Revert if failure rate climbs following the trigger change.",
    ],
}

_DEFAULT_ROLLBACK: list[str] = [
    "Revert if primary outcome metrics worsen following the change.",
]

# ---------------------------------------------------------------------------
# Execution sequence mappings per change_type
# ---------------------------------------------------------------------------

_EXECUTION_SEQUENCE_BY_CHANGE_TYPE: dict[str, list[str]] = {
    "threshold_adjustment": [
        "Review proposal metadata and supporting simulation preview.",
        "Verify current failed_rate remains stable.",
        "Prepare threshold adjustment change request.",
        "Schedule guarded rollout review.",
        "Define post-change monitoring checks.",
    ],
    "pricing_guardrail_adjustment": [
        "Review underpricing evidence and margin bounds.",
        "Verify conversion/win-rate trajectory.",
        "Prepare pricing guardrail change request.",
        "Schedule guarded rollout review.",
        "Define post-change monitoring checks.",
    ],
    "validation_policy_adjustment": [
        "Review upstream input quality reasoning.",
        "Verify fallback pressure and throughput risk.",
        "Prepare validation policy change request.",
        "Schedule guarded rollout review.",
        "Define post-change monitoring checks.",
    ],
    "fallback_policy_adjustment": [
        "Review repeated fallback signal and failure evidence.",
        "Verify fallback-related failure scope.",
        "Prepare fallback policy change request.",
        "Schedule guarded rollout review.",
        "Define post-change monitoring checks.",
    ],
    "review_trigger_adjustment": [
        "Review review pressure and failure evidence.",
        "Verify low-risk workflow scope.",
        "Prepare review trigger change request.",
        "Schedule guarded rollout review.",
        "Define post-change monitoring checks.",
    ],
}

_DEFAULT_EXECUTION_SEQUENCE: list[str] = [
    "Review proposal metadata and supporting evidence.",
    "Verify current supporting metrics remain stable.",
    "Prepare bounded change request.",
    "Schedule guarded rollout review.",
    "Define post-change monitoring checks.",
]

# ---------------------------------------------------------------------------
# Safety note mappings per change_type
# ---------------------------------------------------------------------------

_SAFETY_NOTES_BY_CHANGE_TYPE: dict[str, list[str]] = {
    "threshold_adjustment": [
        "Apply only within the bounded threshold range.",
    ],
    "pricing_guardrail_adjustment": [
        "Apply only within validated margin bounds.",
    ],
    "validation_policy_adjustment": [
        "Ensure throughput risk is understood before applying.",
    ],
    "fallback_policy_adjustment": [
        "Apply only if fallback signal is clearly isolated.",
    ],
    "review_trigger_adjustment": [
        "Limit scope to the low-risk workflow identified.",
    ],
}

_DEFAULT_SAFETY_NOTES: list[str] = [
    "Apply only within bounded parameters defined in the proposal.",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _conflicts_for_change(change_id: str, conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in conflicts if change_id in c.get("proposal_ids", [])]


def _staleness_for_change(change_id: str, staleness: list[dict[str, Any]]) -> dict[str, Any] | None:
    for s in staleness:
        if s.get("change_id") == change_id:
            return s
    return None


def _readiness_for_change(change_id: str, readiness: list[dict[str, Any]]) -> dict[str, Any] | None:
    for r in readiness:
        if r.get("change_id") == change_id:
            return r
    return None


def _combined_plan_peers(
    change_id: str,
    change_conflicts: list[dict[str, Any]],
) -> list[str]:
    """Return sibling change IDs that should be planned together with this change."""
    peers: list[str] = []
    for c in change_conflicts:
        if c.get("severity") == "medium" and c.get("conflict_type") in _COMBINED_PLAN_CONFLICT_TYPES:
            for pid in c.get("proposal_ids", []):
                if pid != change_id and pid not in peers:
                    peers.append(pid)
    return peers


def _has_missing_required_fields(change: dict[str, Any]) -> bool:
    if not change.get("target") or not change.get("proposed_change"):
        return True
    bounded_range = (change.get("proposed_change") or {}).get("bounded_range")
    if not bounded_range:
        return True
    return False


# ---------------------------------------------------------------------------
# Per-proposal planning
# ---------------------------------------------------------------------------


def _plan_change(
    change: dict[str, Any],
    *,
    readiness_entry: dict[str, Any] | None,
    change_conflicts: list[dict[str, Any]],
    staleness_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    change_id = change.get("change_id", "")
    change_type = change.get("change_type", "")

    blocking_reasons: list[str] = []

    # --- Hard-block rules ---

    if _has_missing_required_fields(change):
        blocking_reasons.append(
            "Proposal is missing required 'target', 'proposed_change', or 'bounded_range' fields."
        )

    readiness_status = (readiness_entry or {}).get("status", "")
    if readiness_status == "blocked":
        blocking_reasons.append("Proposal approval_readiness is 'blocked'.")

    staleness_status = (staleness_entry or {}).get("status", "fresh")
    if staleness_status in _HARD_BLOCK_STALENESS:
        blocking_reasons.append(f"Proposal staleness is '{staleness_status}'.")

    high_conflicts = [c for c in change_conflicts if c.get("severity") == "high"]
    if high_conflicts:
        count = len(high_conflicts)
        blocking_reasons.append(
            f"Proposal is involved in {count} high-severity conflict(s)."
        )

    if blocking_reasons:
        status = BLOCKED_FROM_PLANNING
        severity = "high"
        summary = "Proposal cannot enter apply planning — one or more blocking conditions are present."
        recommendation = "Resolve all blocking conditions before this proposal can be planned."
        dependencies: list[str] = []
    else:
        # --- requires_combined_plan rules ---
        peers = _combined_plan_peers(change_id, change_conflicts)
        if peers:
            status = REQUIRES_COMBINED_PLAN
            severity = "medium"
            summary = (
                "Proposal requires a combined plan with related proposals before it can be safely planned."
            )
            recommendation = (
                "Plan this proposal together with its conflicting peers before proceeding."
            )
            dependencies = peers
        else:
            status = PLANNED
            severity = "low"
            summary = "Proposal is suitable for guarded apply planning."
            recommendation = "Proposal can proceed to a future guarded apply workflow."
            dependencies = []

    preflight_checks = _PREFLIGHT_BY_CHANGE_TYPE.get(change_type, _DEFAULT_PREFLIGHT)
    rollback_plan = _ROLLBACK_BY_CHANGE_TYPE.get(change_type, _DEFAULT_ROLLBACK)
    execution_sequence = _EXECUTION_SEQUENCE_BY_CHANGE_TYPE.get(
        change_type, _DEFAULT_EXECUTION_SEQUENCE
    )
    safety_notes = _SAFETY_NOTES_BY_CHANGE_TYPE.get(change_type, _DEFAULT_SAFETY_NOTES)

    return {
        "change_id": change_id,
        "status": status,
        "severity": severity,
        "summary": summary,
        "execution_readiness": status,
        "preflight_checks": list(preflight_checks),
        "dependencies": dependencies,
        "execution_sequence": list(execution_sequence),
        "rollback_plan": list(rollback_plan),
        "safety_notes": list(safety_notes),
        "blocking_reasons": blocking_reasons,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_apply_planning(
    *,
    scope_type: str,
    scope_id: str,
    proposed_changes: list[dict[str, Any]],
    approval_readiness: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    staleness: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute guarded execution plans for a set of proposed changes.

    Pure function — no DB access, no mutations, no ML.
    Returns deterministic output for identical inputs.

    Args:
        scope_type: "pipeline" or "vertical"
        scope_id: pipeline_name or vertical_id
        proposed_changes: freshly computed proposed change dicts
        approval_readiness: readiness annotation list from evaluate_proposal_approval_readiness
        conflicts: conflict annotation list from detect_proposal_conflicts
        staleness: staleness annotation list from detect_proposal_staleness
    """
    apply_plans: list[dict[str, Any]] = []

    for change in proposed_changes:
        change_id = change.get("change_id", "")

        plan = _plan_change(
            change,
            readiness_entry=_readiness_for_change(change_id, approval_readiness),
            change_conflicts=_conflicts_for_change(change_id, conflicts),
            staleness_entry=_staleness_for_change(change_id, staleness),
        )
        apply_plans.append(plan)

    planned_count = sum(1 for p in apply_plans if p["status"] == PLANNED)
    combined_count = sum(1 for p in apply_plans if p["status"] == REQUIRES_COMBINED_PLAN)
    blocked_count = sum(1 for p in apply_plans if p["status"] == BLOCKED_FROM_PLANNING)

    if not apply_plans:
        summary = "No proposals to plan."
    elif blocked_count > 0:
        summary = (
            f"{blocked_count} proposal(s) blocked from planning; "
            f"{combined_count} require combined plan; "
            f"{planned_count} planned."
        )
    elif combined_count > 0:
        summary = (
            f"{combined_count} proposal(s) require combined plan; "
            f"{planned_count} planned."
        )
    else:
        summary = f"All {planned_count} proposal(s) have a guarded execution plan."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "proposal_count": len(proposed_changes),
        "planned_count": planned_count,
        "combined_count": combined_count,
        "blocked_count": blocked_count,
        "summary": summary,
        "apply_plans": apply_plans,
    }
