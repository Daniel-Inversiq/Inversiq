"""
app/services/proposal_conflicts.py

Deterministic, read-only proposal conflict detection layer (v1).

Accepts a list of proposed change objects (as produced by compute_proposed_changes)
and returns structured conflict annotations for the same scope.

This is NOT an auto-resolution layer. Nothing is merged, rejected, or modified.
Detection + structured explanation only.

Pure function over dicts — no DB access, no mutations, no ML.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Policy-area groupings — parameters that share a policy domain
# ---------------------------------------------------------------------------

_POLICY_AREAS: dict[str, str] = {
    "review_confidence_threshold": "review_policy",
    "review_trigger_threshold": "review_policy",
    "review_rate_target": "review_policy",
    "fallback_threshold": "fallback_policy",
    "fallback_rate_limit": "fallback_policy",
    "fallback_retry_limit": "fallback_policy",
    "validation_strictness": "validation_policy",
    "validation_confidence_floor": "validation_policy",
    "margin_floor": "pricing_policy",
    "margin_guardrail": "pricing_policy",
    "underpricing_threshold": "pricing_policy",
}

# ---------------------------------------------------------------------------
# Severity ordering for sorting (higher number = shown first)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

# ---------------------------------------------------------------------------
# High-risk change types — two or more in the same scope triggers escalation
# ---------------------------------------------------------------------------

_HIGH_RISK_CHANGE_TYPES = {"pricing_guardrail_adjustment", "fallback_policy_adjustment"}

# ---------------------------------------------------------------------------
# Conflict type → severity mapping
# ---------------------------------------------------------------------------

_CONFLICT_SEVERITY: dict[str, str] = {
    "opposite_direction_conflict": "high",
    "high_risk_combination": "high",
    "duplicate_proposal": "medium",
    "same_target_overlap": "medium",
    "policy_area_overlap": "low",
}

# ---------------------------------------------------------------------------
# Conflict type → recommendation mapping
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[str, str] = {
    "opposite_direction_conflict": "Do not approve independently; resolve parameter direction first.",
    "high_risk_combination": "Escalate for combined approval review.",
    "duplicate_proposal": "Archive or reject the duplicate proposal after review.",
    "same_target_overlap": "Review these proposals together before approval.",
    "policy_area_overlap": "Consider reviewing these proposals together; they affect a shared policy area.",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _conflict_id(scope_type: str, scope_id: str, key: str, conflict_type: str) -> str:
    """Generate a stable, deterministic conflict ID."""
    return f"{scope_type}:{scope_id}:{key}:{conflict_type}"


def _target(change: dict[str, Any]) -> dict[str, Any]:
    return change.get("target") or {}


def _parameter(change: dict[str, Any]) -> str:
    return _target(change).get("parameter", "unknown_parameter")


def _direction(change: dict[str, Any]) -> str | None:
    pc = change.get("proposed_change")
    if not pc or not isinstance(pc, dict):
        return None
    return pc.get("direction")


def _change_type(change: dict[str, Any]) -> str:
    return change.get("change_type", "")


def _risk_level(change: dict[str, Any]) -> str:
    return (change.get("approval_intent") or {}).get("risk_level", "low")


def _actionable(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out no_action_proposed changes — they can't meaningfully conflict."""
    return [c for c in changes if _change_type(c) != "no_action_proposed"]


# ---------------------------------------------------------------------------
# Individual conflict detectors
# ---------------------------------------------------------------------------


def _detect_same_target_overlap(
    scope_type: str,
    scope_id: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Multiple proposals affecting the same target parameter."""
    by_param: dict[str, list[dict]] = {}
    for c in changes:
        p = _parameter(c)
        by_param.setdefault(p, []).append(c)

    conflicts = []
    for param, group in by_param.items():
        if len(group) < 2:
            continue
        proposal_ids = [c["change_id"] for c in group]
        cid = _conflict_id(scope_type, scope_id, param, "same_target_overlap")
        conflicts.append({
            "conflict_id": cid,
            "conflict_type": "same_target_overlap",
            "severity": _CONFLICT_SEVERITY["same_target_overlap"],
            "proposal_ids": proposal_ids,
            "target": {
                "parameter": param,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            "summary": "Multiple proposals target the same parameter and should be reviewed together.",
            "reason": "Independent approval may produce overlapping behavior changes.",
            "recommendation": _RECOMMENDATIONS["same_target_overlap"],
        })
    return conflicts


def _detect_opposite_direction(
    scope_type: str,
    scope_id: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Same target parameter but opposing directions (increase vs decrease)."""
    by_param: dict[str, list[dict]] = {}
    for c in changes:
        p = _parameter(c)
        by_param.setdefault(p, []).append(c)

    conflicts = []
    for param, group in by_param.items():
        if len(group) < 2:
            continue
        directions = {_direction(c) for c in group if _direction(c) not in (None, "none")}
        if "increase" in directions and "decrease" in directions:
            proposal_ids = [c["change_id"] for c in group]
            cid = _conflict_id(scope_type, scope_id, param, "opposite_direction_conflict")
            conflicts.append({
                "conflict_id": cid,
                "conflict_type": "opposite_direction_conflict",
                "severity": _CONFLICT_SEVERITY["opposite_direction_conflict"],
                "proposal_ids": proposal_ids,
                "target": {
                    "parameter": param,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                },
                "summary": f"Proposals conflict on direction for parameter '{param}'.",
                "reason": "One proposal increases and another decreases the same parameter.",
                "recommendation": _RECOMMENDATIONS["opposite_direction_conflict"],
            })
    return conflicts


def _detect_duplicate_proposals(
    scope_type: str,
    scope_id: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Multiple proposals with the same change_type and parameter (same category family)."""
    by_key: dict[str, list[dict]] = {}
    for c in changes:
        key = f"{_change_type(c)}::{_parameter(c)}"
        by_key.setdefault(key, []).append(c)

    conflicts = []
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        # Only a duplicate if change_ids differ (not the exact same entry twice)
        unique_ids = {c["change_id"] for c in group}
        if len(unique_ids) < 2:
            continue
        param = _parameter(group[0])
        cid = _conflict_id(scope_type, scope_id, key.replace("::", "_"), "duplicate_proposal")
        conflicts.append({
            "conflict_id": cid,
            "conflict_type": "duplicate_proposal",
            "severity": _CONFLICT_SEVERITY["duplicate_proposal"],
            "proposal_ids": list(unique_ids),
            "target": {
                "parameter": param,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            "summary": "Multiple proposals represent the same intended change.",
            "reason": "Proposals share the same change_type and target parameter.",
            "recommendation": _RECOMMENDATIONS["duplicate_proposal"],
        })
    return conflicts


def _detect_policy_area_overlap(
    scope_type: str,
    scope_id: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Proposals affecting closely related policy areas."""
    by_area: dict[str, list[dict]] = {}
    for c in changes:
        param = _parameter(c)
        area = _POLICY_AREAS.get(param)
        if area:
            by_area.setdefault(area, []).append(c)

    conflicts = []
    for area, group in by_area.items():
        if len(group) < 2:
            continue
        # Only flag if the group spans more than one distinct parameter
        distinct_params = {_parameter(c) for c in group}
        if len(distinct_params) < 2:
            continue
        proposal_ids = [c["change_id"] for c in group]
        cid = _conflict_id(scope_type, scope_id, area, "policy_area_overlap")
        conflicts.append({
            "conflict_id": cid,
            "conflict_type": "policy_area_overlap",
            "severity": _CONFLICT_SEVERITY["policy_area_overlap"],
            "proposal_ids": proposal_ids,
            "target": {
                "parameter": area,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            "summary": f"Multiple proposals affect the '{area}' policy area.",
            "reason": "Proposals targeting related parameters may produce compounded or unpredictable effects.",
            "recommendation": _RECOMMENDATIONS["policy_area_overlap"],
        })
    return conflicts


def _detect_high_risk_combination(
    scope_type: str,
    scope_id: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Two or more medium/high-risk proposals in the same scope, especially pricing + anything."""
    risky = [
        c for c in changes
        if _risk_level(c) in ("medium", "high")
    ]
    if len(risky) < 2:
        return []

    # Escalate specifically when a pricing_guardrail_adjustment is present alongside others
    has_pricing = any(_change_type(c) == "pricing_guardrail_adjustment" for c in risky)
    has_other_high_risk = any(
        _change_type(c) in _HIGH_RISK_CHANGE_TYPES and _change_type(c) != "pricing_guardrail_adjustment"
        for c in risky
    )

    if not (has_pricing or has_other_high_risk):
        return []

    proposal_ids = [c["change_id"] for c in risky]
    cid = _conflict_id(scope_type, scope_id, "high_risk_combination", "high_risk_combination")
    return [{
        "conflict_id": cid,
        "conflict_type": "high_risk_combination",
        "severity": _CONFLICT_SEVERITY["high_risk_combination"],
        "proposal_ids": proposal_ids,
        "target": {
            "parameter": "multiple",
            "scope_type": scope_type,
            "scope_id": scope_id,
        },
        "summary": "Multiple high-risk proposals are present in the same scope.",
        "reason": "Approving high-risk proposals independently increases the chance of compound effects.",
        "recommendation": _RECOMMENDATIONS["high_risk_combination"],
    }]


# ---------------------------------------------------------------------------
# Deduplication — remove lower-priority conflicts subsumed by higher ones
# ---------------------------------------------------------------------------


def _deduplicate(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove same_target_overlap entries whose proposal_ids are already fully
    covered by an opposite_direction_conflict for the same parameter — the
    higher-severity conflict supersedes.
    """
    opposite_ids: set[frozenset] = set()
    for c in conflicts:
        if c["conflict_type"] == "opposite_direction_conflict":
            opposite_ids.add(frozenset(c["proposal_ids"]))

    result = []
    for c in conflicts:
        if c["conflict_type"] == "same_target_overlap":
            if frozenset(c["proposal_ids"]) in opposite_ids:
                continue
        result.append(c)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_proposal_conflicts(
    *,
    scope_type: str,
    scope_id: str,
    proposed_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Analyze a list of proposed change objects for conflicts within the same scope.

    Pure function — no DB access, no persistence, no mutations.
    Returns deterministic output for identical inputs.

    Conflict detection order (highest priority first):
      1. opposite_direction_conflict
      2. high_risk_combination
      3. duplicate_proposal
      4. same_target_overlap
      5. policy_area_overlap

    same_target_overlap entries superseded by opposite_direction_conflict
    for the same parameter pair are suppressed to avoid redundancy.
    """
    changes = _actionable(proposed_changes)

    all_conflicts: list[dict[str, Any]] = []
    all_conflicts.extend(_detect_opposite_direction(scope_type, scope_id, changes))
    all_conflicts.extend(_detect_high_risk_combination(scope_type, scope_id, changes))
    all_conflicts.extend(_detect_duplicate_proposals(scope_type, scope_id, changes))
    all_conflicts.extend(_detect_same_target_overlap(scope_type, scope_id, changes))
    all_conflicts.extend(_detect_policy_area_overlap(scope_type, scope_id, changes))

    all_conflicts = _deduplicate(all_conflicts)

    all_conflicts.sort(
        key=lambda c: _SEVERITY_ORDER.get(c["severity"], 0),
        reverse=True,
    )

    conflict_count = len(all_conflicts)
    if conflict_count == 0:
        summary = "No proposal conflicts detected."
    elif conflict_count == 1:
        ct = all_conflicts[0]["conflict_type"]
        summary = f"1 conflict detected: {ct}."
    else:
        types = ", ".join(c["conflict_type"] for c in all_conflicts)
        summary = f"{conflict_count} conflicts detected: {types}."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "proposal_count": len(proposed_changes),
        "conflict_count": conflict_count,
        "summary": summary,
        "conflicts": all_conflicts,
    }
