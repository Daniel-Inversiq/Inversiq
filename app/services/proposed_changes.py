"""
app/services/proposed_changes.py

Deterministic, read-only proposed change / approval intent engine (v1).

Accepts control suggestions from the existing control suggestions layer and
transforms them into normalized, reviewable proposed change objects.

This is NOT an execution layer. This is NOT a persistence layer.
This is a structured intent layer for later human approval workflows.

Pure function over dicts — no DB access, no mutations, no ML.
All output is proposal_only. Nothing is applied or stored.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Category → change_type mapping
# ---------------------------------------------------------------------------

_CHANGE_TYPE_MAP: dict[str, str] = {
    "confidence_threshold_tuning": "threshold_adjustment",
    "review_trigger_narrowing": "review_trigger_adjustment",
    "validation_step_tightening": "validation_policy_adjustment",
    "fallback_path_hardening": "fallback_policy_adjustment",
    "margin_guardrail_adjustment": "pricing_guardrail_adjustment",
    "no_safe_adjustment": "no_action_proposed",
}

# ---------------------------------------------------------------------------
# Risk levels per change_type — deterministic defaults
# ---------------------------------------------------------------------------

_RISK_LEVEL: dict[str, str] = {
    "threshold_adjustment": "medium",
    "review_trigger_adjustment": "medium",
    "validation_policy_adjustment": "medium",
    "fallback_policy_adjustment": "medium",
    "pricing_guardrail_adjustment": "high",
    "no_action_proposed": "low",
}

_APPROVAL_TYPE: dict[str, str] = {
    "threshold_adjustment": "operator_confirmation",
    "review_trigger_adjustment": "operator_confirmation",
    "validation_policy_adjustment": "operator_confirmation",
    "fallback_policy_adjustment": "operator_confirmation",
    "pricing_guardrail_adjustment": "senior_review",
    "no_action_proposed": "operator_confirmation",
}

# ---------------------------------------------------------------------------
# Importance ordering for sorting proposals (higher = more important)
# ---------------------------------------------------------------------------

_IMPORTANCE: dict[str, int] = {
    "pricing_guardrail_adjustment": 5,
    "fallback_policy_adjustment": 4,
    "validation_policy_adjustment": 4,
    "threshold_adjustment": 3,
    "review_trigger_adjustment": 2,
    "no_action_proposed": 0,
}

# ---------------------------------------------------------------------------
# Per-category preconditions and rollback hints
# ---------------------------------------------------------------------------

_PRECONDITIONS: dict[str, list[str]] = {
    "confidence_threshold_tuning": [
        "failed_rate must remain stable or only low-severity degrading.",
        "low_confidence_rate must not be worsening sharply.",
        "No active incident or elevated error pattern in the current window.",
    ],
    "review_trigger_narrowing": [
        "failed_rate must be stable or improving.",
        "Operator backlog or review rate must be the primary pressure signal.",
        "No sharp increase in ambiguous or borderline-confidence runs.",
    ],
    "validation_step_tightening": [
        "Repeated fallback or upstream input quality issues must persist across at least one comparison window.",
        "failed_rate must not be sharply degrading before applying.",
        "fallback_rate must continue degrading or remain elevated.",
    ],
    "fallback_path_hardening": [
        "repeated_fallback signal count must remain elevated.",
        "Upstream input quality issues must be confirmed, not transient.",
        "Fallback path must not be the sole valid path for a significant input segment.",
    ],
    "margin_guardrail_adjustment": [
        "Underpricing trend must persist across multiple comparison windows.",
        "win_rate must not already be declining before applying.",
        "Adjustment must remain within pre-approved bounded pricing ranges.",
    ],
    "no_safe_adjustment": [],
}

_ROLLBACK_HINTS: dict[str, list[str]] = {
    "confidence_threshold_tuning": [
        "Revert threshold change if failed_rate worsens measurably in the next comparison window.",
        "Revert if low-confidence escapes increase after the change.",
        "Revert if review volume unexpectedly rises rather than falls.",
    ],
    "review_trigger_narrowing": [
        "Revert trigger narrowing if failed_rate degrades after the change.",
        "Revert if operator escalations increase following the adjustment.",
        "Do not narrow further until the first adjustment has been observed for at least one full window.",
    ],
    "validation_step_tightening": [
        "Revert if run_count drops sharply, indicating valid inputs are being incorrectly rejected.",
        "Revert if failed_rate rises after tightening validation.",
        "Monitor fallback_rate for at least one full comparison window before applying further tightening.",
    ],
    "fallback_path_hardening": [
        "Revert if surfaced failures increase sharply and are not attributable to previously masked inputs.",
        "Revert if throughput drops materially after future implementation.",
        "Monitor repeated_fallback signal count to confirm trend reversal.",
    ],
    "margin_guardrail_adjustment": [
        "Revert if win_rate drops while underpricing normalizes — may indicate overpricing risk.",
        "Revert if deal conversion declines materially within the next comparison window.",
        "Confirm with pricing team before any further adjustments beyond initial bounded delta.",
    ],
    "no_safe_adjustment": [],
}

# ---------------------------------------------------------------------------
# Per-category titles
# ---------------------------------------------------------------------------

_TITLES: dict[str, str] = {
    "confidence_threshold_tuning": "Lower review confidence threshold slightly",
    "review_trigger_narrowing": "Narrow review trigger conditions",
    "validation_step_tightening": "Tighten upstream input validation",
    "fallback_path_hardening": "Harden fallback path safeguards",
    "margin_guardrail_adjustment": "Raise margin protection floor",
    "no_safe_adjustment": "No structured change proposed",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _change_id(scope_type: str, scope_id: str, category: str, parameter: str) -> str:
    """Generate a stable, deterministic change ID."""
    return f"{scope_type}:{scope_id}:{category}:{parameter}"


def _extract_parameter(suggestion: dict[str, Any]) -> str:
    """Extract parameter name from a control suggestion's proposed_change block."""
    pc = suggestion.get("proposed_change")
    if pc and isinstance(pc, dict):
        return pc.get("parameter", "unknown_parameter")
    return "no_parameter"


def _extract_proposed_change_block(suggestion: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the numeric change details from a control suggestion."""
    pc = suggestion.get("proposed_change")
    if not pc or not isinstance(pc, dict):
        return None
    return {
        "direction": pc.get("direction", "none"),
        "suggested_delta": pc.get("suggested_delta"),
        "bounded_range": pc.get("bounded_range"),
    }


def _build_evidence(
    category: str,
    reasoning_categories: list[str],
    metric_trends: list[dict],
    signal_counts: dict[str, int],
) -> list[str]:
    """Build a deterministic evidence list from input signals."""
    evidence: list[str] = []

    if category in reasoning_categories:
        evidence.append(f"{category} reasoning category present.")

    trend_map = {m["name"]: m for m in metric_trends}

    if category == "confidence_threshold_tuning":
        if "review_rate" in trend_map and trend_map["review_rate"]["direction"] == "degrading":
            evidence.append("review_rate is degrading in the current window.")
        if "failed_rate" in trend_map and trend_map["failed_rate"]["direction"] != "degrading":
            evidence.append("failed_rate is not strongly degrading.")

    elif category == "review_trigger_narrowing":
        if "review_rate" in trend_map and trend_map["review_rate"]["direction"] == "degrading":
            evidence.append("review_rate is degrading in the current window.")
        if "failed_rate" in trend_map and trend_map["failed_rate"]["direction"] in ("stable", "improving"):
            evidence.append("failed_rate is stable or improving.")

    elif category == "validation_step_tightening":
        if "fallback_rate" in trend_map and trend_map["fallback_rate"]["direction"] == "degrading":
            evidence.append("fallback_rate is degrading in the current window.")
        if "upstream_input_quality" in reasoning_categories:
            evidence.append("upstream_input_quality reasoning category triggered.")

    elif category == "fallback_path_hardening":
        rc = signal_counts.get("repeated_fallback", 0)
        if rc > 0:
            evidence.append(f"repeated_fallback signal count: {rc}.")
        if "upstream_input_quality" in reasoning_categories:
            evidence.append("upstream_input_quality reasoning category triggered.")

    elif category == "margin_guardrail_adjustment":
        if "pricing_calibration_issue" in reasoning_categories:
            evidence.append("pricing_calibration_issue reasoning category triggered.")
        if "underpricing_rate" in trend_map and trend_map["underpricing_rate"]["direction"] == "degrading":
            evidence.append("underpricing_rate is degrading in the current window.")

    return evidence if evidence else ["No specific trend evidence captured for this proposal."]


def _build_approval_intent(change_type: str) -> dict[str, Any]:
    risk = _RISK_LEVEL.get(change_type, "medium")
    return {
        "requires_human_review": True,
        "risk_level": risk,
        "approval_type": _APPROVAL_TYPE.get(change_type, "operator_confirmation"),
    }


def _build_proposed_change(
    *,
    scope_type: str,
    scope_id: str,
    suggestion: dict[str, Any],
    reasoning_categories: list[str],
    metric_trends: list[dict],
    signal_counts: dict[str, int],
) -> dict[str, Any]:
    """Transform a single control suggestion into a formal proposed change object."""
    category = suggestion.get("category", "no_safe_adjustment")
    change_type = _CHANGE_TYPE_MAP.get(category, "no_action_proposed")
    parameter = _extract_parameter(suggestion)
    title = _TITLES.get(category, "No change proposed")

    return {
        "change_id": _change_id(scope_type, scope_id, category, parameter),
        "category": category,
        "title": title,
        "change_type": change_type,
        "target": {
            "parameter": parameter,
            "scope_type": scope_type,
            "scope_id": scope_id,
        },
        "proposed_change": _extract_proposed_change_block(suggestion),
        "reason": suggestion.get("reason", ""),
        "expected_effect": list(suggestion.get("expected_effect", [])),
        "preconditions": list(_PRECONDITIONS.get(category, [])),
        "approval_intent": _build_approval_intent(change_type),
        "rollback_hint": list(_ROLLBACK_HINTS.get(category, [])),
        "evidence": _build_evidence(
            category,
            reasoning_categories=reasoning_categories,
            metric_trends=metric_trends,
            signal_counts=signal_counts,
        ),
        "status": "proposal_only",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_proposed_changes(
    *,
    scope_type: str,
    scope_id: str,
    suggestions: list[dict[str, Any]],
    reasoning_categories: list[str],
    metric_trends: list[dict],
    signal_counts: dict[str, int],
) -> dict[str, Any]:
    """
    Transform control suggestions into formal proposed change objects.

    Pure function — no DB access, no persistence, no mutations.
    Returns deterministic output for identical inputs.

    All returned change objects carry status='proposal_only'.
    Nothing is applied, stored, or approved by this function.
    """
    seen_ids: set[str] = set()
    proposed: list[dict[str, Any]] = []

    for suggestion in suggestions:
        obj = _build_proposed_change(
            scope_type=scope_type,
            scope_id=scope_id,
            suggestion=suggestion,
            reasoning_categories=reasoning_categories,
            metric_trends=metric_trends,
            signal_counts=signal_counts,
        )
        cid = obj["change_id"]
        if cid not in seen_ids:
            seen_ids.add(cid)
            proposed.append(obj)

    proposed.sort(
        key=lambda p: _IMPORTANCE.get(p["change_type"], 0),
        reverse=True,
    )

    count = len(proposed)
    if count == 0:
        summary = "No structured proposed changes generated."
    elif count == 1:
        summary = f"One structured proposed change generated: {proposed[0]['category']}."
    else:
        cats = ", ".join(p["category"] for p in proposed)
        summary = f"{count} structured proposed changes generated: {cats}."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "proposed_changes": proposed,
        "summary": summary,
    }
