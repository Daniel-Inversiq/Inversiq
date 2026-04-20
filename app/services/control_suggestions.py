"""
app/services/control_suggestions.py

Deterministic, read-only control suggestions engine.

Accepts normalized signals from the health, trend, and reasoning layers and
returns bounded, explainable control suggestions. No ML, no DB queries,
no persistence — pure function over dicts.

Every suggestion is conceptual only. Nothing is mutated or applied.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Bounded parameter ranges — conservative defaults for v1.
# Actual live values are not read from config; ranges are safe placeholders.
# ---------------------------------------------------------------------------

_THRESHOLD_BOUNDS: dict[str, dict[str, float]] = {
    "review_confidence_threshold": {"min": 0.50, "max": 0.90},
    "fallback_validation_strictness": {"min": 0.60, "max": 0.95},
    "margin_protection_floor": {"min": 0.03, "max": 0.20},
    "review_trigger_sensitivity": {"min": 0.40, "max": 0.85},
}

_CONFIDENCE_WEIGHT: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_degrading(metric_trends: list[dict], name: str, min_severity: str = "low") -> bool:
    """Return True if the named metric is degrading at or above min_severity."""
    weights = {"high": 3, "medium": 2, "low": 1}
    threshold = weights.get(min_severity, 1)
    for m in metric_trends:
        if m["name"] == name and m["direction"] == "degrading":
            sev = m.get("severity") or "low"
            if weights.get(sev, 1) >= threshold:
                return True
    return False


def _is_stable_or_improving(metric_trends: list[dict], name: str) -> bool:
    """Return True if metric is stable/improving, or absent (treated as stable)."""
    for m in metric_trends:
        if m["name"] == name:
            return m["direction"] in ("stable", "improving")
    return True


def _has_signal(signal_counts: dict[str, int], signal_type: str) -> bool:
    return signal_counts.get(signal_type, 0) > 0


# ---------------------------------------------------------------------------
# Suggestion builders — one per category
# ---------------------------------------------------------------------------


def _suggestion_confidence_threshold_tuning() -> dict[str, Any]:
    return {
        "category": "confidence_threshold_tuning",
        "action": "lower_review_threshold",
        "reason": (
            "Review pressure is elevated while execution failure rates remain relatively stable, "
            "suggesting the confidence review threshold may be too sensitive."
        ),
        "proposed_change": {
            "parameter": "review_confidence_threshold",
            "direction": "decrease",
            "suggested_delta": 0.05,
            "bounded_range": _THRESHOLD_BOUNDS["review_confidence_threshold"],
        },
        "expected_effect": [
            "Reduce unnecessary manual reviews triggered by borderline-confidence runs.",
            "Maintain review coverage for clearly low-confidence runs.",
        ],
        "guardrails": [
            "Do not apply if failed_rate is also degrading sharply.",
            "Do not apply if REPEATED_REVIEW_FLAG signal count is rising.",
            "Do not exceed configured threshold bounds.",
        ],
        "confidence": "medium",
    }


def _suggestion_review_trigger_narrowing() -> dict[str, Any]:
    return {
        "category": "review_trigger_narrowing",
        "action": "narrow_review_triggers",
        "reason": (
            "Review backlog or review rate is increasing while execution quality is stable, "
            "indicating over-broad review trigger conditions."
        ),
        "proposed_change": {
            "parameter": "review_trigger_sensitivity",
            "direction": "decrease",
            "suggested_delta": 0.05,
            "bounded_range": _THRESHOLD_BOUNDS["review_trigger_sensitivity"],
        },
        "expected_effect": [
            "Reduce operator review volume for low-risk, high-confidence runs.",
            "Focus review capacity on genuinely ambiguous or risky cases.",
        ],
        "guardrails": [
            "Do not narrow triggers if failed_rate is degrading.",
            "Do not reduce review coverage for high-risk workflow segments.",
            "Reassess after one full comparison window before narrowing further.",
        ],
        "confidence": "medium",
    }


def _suggestion_validation_step_tightening() -> dict[str, Any]:
    return {
        "category": "validation_step_tightening",
        "action": "tighten_input_validation",
        "reason": (
            "Upstream input quality signals are degrading and fallback usage is increasing, "
            "suggesting input validation before processing is too permissive."
        ),
        "proposed_change": {
            "parameter": "fallback_validation_strictness",
            "direction": "increase",
            "suggested_delta": 0.05,
            "bounded_range": _THRESHOLD_BOUNDS["fallback_validation_strictness"],
        },
        "expected_effect": [
            "Catch low-quality inputs earlier, before they trigger fallback paths.",
            "Reduce cascading confidence degradation from poor upstream data.",
        ],
        "guardrails": [
            "Only consider this if failure rates remain stable for the next comparison window.",
            "Ensure validation tightening does not block valid edge-case inputs.",
            "Monitor fallback_rate after applying — do not tighten further if run_count drops sharply.",
        ],
        "confidence": "medium",
    }


def _suggestion_fallback_path_hardening() -> dict[str, Any]:
    return {
        "category": "fallback_path_hardening",
        "action": "harden_fallback_path",
        "reason": (
            "Repeated fallback signals are present and upstream input quality is degrading, "
            "suggesting the fallback path itself needs stronger safeguards."
        ),
        "proposed_change": {
            "parameter": "fallback_validation_strictness",
            "direction": "increase",
            "suggested_delta": 0.08,
            "bounded_range": _THRESHOLD_BOUNDS["fallback_validation_strictness"],
        },
        "expected_effect": [
            "Prevent low-quality fallback outputs from passing through as acceptable results.",
            "Surface upstream root causes more clearly rather than masking them with fallbacks.",
        ],
        "guardrails": [
            "Do not apply if fallback_path is the only valid path for certain input types.",
            "Apply only within pre-approved validation strictness ranges.",
            "Confirm fallback trigger conditions are well-understood before tightening.",
        ],
        "confidence": "medium",
    }


def _suggestion_margin_guardrail_adjustment() -> dict[str, Any]:
    return {
        "category": "margin_guardrail_adjustment",
        "action": "raise_margin_protection_floor",
        "reason": (
            "Pricing calibration signals indicate underpricing patterns, "
            "suggesting the margin protection floor may be set too low."
        ),
        "proposed_change": {
            "parameter": "margin_protection_floor",
            "direction": "increase",
            "suggested_delta": 0.02,
            "bounded_range": _THRESHOLD_BOUNDS["margin_protection_floor"],
        },
        "expected_effect": [
            "Reduce frequency of quotes that fall below sustainable margin thresholds.",
            "Provide a bounded safety net against systematic underpricing.",
        ],
        "guardrails": [
            "Apply only within pre-approved pricing margin ranges.",
            "Do not adjust if deal win rate is already declining — may indicate overpricing risk.",
            "Confirm with pricing team before applying changes to production rules.",
        ],
        "confidence": "medium",
    }


def _suggestion_no_safe_adjustment(health_status: str) -> dict[str, Any]:
    return {
        "category": "no_safe_adjustment",
        "action": "no_action",
        "reason": (
            f"Current signals (health: {health_status}) do not map to a bounded, "
            "deterministic control adjustment at this time."
        ),
        "proposed_change": None,
        "expected_effect": [
            "No change proposed — system appears within acceptable operating parameters "
            "or signals are insufficient for a confident recommendation.",
        ],
        "guardrails": [
            "Continue monitoring trends over the next comparison window.",
            "Re-evaluate if health status degrades or new signal clusters emerge.",
        ],
        "confidence": "low",
    }


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


def _apply_rules(
    *,
    health_status: str,
    metric_trends: list[dict],
    signal_counts: dict[str, int],
    reasoning_categories: list[str],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(s: dict) -> None:
        cat = s["category"]
        if cat not in seen:
            seen.add(cat)
            suggestions.append(s)

    cats = set(reasoning_categories)

    # Rule 1: confidence threshold mismatch + failure not sharply degrading
    if "confidence_threshold_mismatch" in cats and not _is_degrading(
        metric_trends, "failed_rate", min_severity="medium"
    ):
        _add(_suggestion_confidence_threshold_tuning())

    # Rule 2: operator backlog with stable execution → narrow review triggers
    if "operator_backlog" in cats and _is_stable_or_improving(metric_trends, "failed_rate"):
        _add(_suggestion_review_trigger_narrowing())

    # Rule 3: upstream input quality + fallback increasing → tighten validation
    if "upstream_input_quality" in cats and _is_degrading(metric_trends, "fallback_rate"):
        _add(_suggestion_validation_step_tightening())

    # Rule 4: upstream input quality + repeated fallback signal → harden fallback path
    if "upstream_input_quality" in cats and _has_signal(signal_counts, "repeated_fallback"):
        _add(_suggestion_fallback_path_hardening())

    # Rule 5: pricing calibration issue → margin guardrail adjustment
    if "pricing_calibration_issue" in cats:
        _add(_suggestion_margin_guardrail_adjustment())

    # Rule 6: anomaly sensitivity shift or rule coverage gap + review_rate degrading,
    #         but failures not sharply worsening → narrow review triggers
    if (
        "anomaly_sensitivity_shift" in cats or "rule_coverage_gap" in cats
    ) and _is_degrading(metric_trends, "review_rate") and not _is_degrading(
        metric_trends, "failed_rate", min_severity="medium"
    ):
        _add(_suggestion_review_trigger_narrowing())

    return suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_control_suggestions(
    *,
    scope_type: str,
    scope_id: str,
    health_status: str,
    metric_trends: list[dict],
    signal_counts: dict[str, int],
    reasoning_categories: list[str],
) -> dict[str, Any]:
    """
    Compute bounded control suggestions for a single scope.

    Pure function — no DB access, no persistence, no mutations.
    Returns deterministic output for identical inputs.
    """
    suggestions = _apply_rules(
        health_status=health_status,
        metric_trends=metric_trends,
        signal_counts=signal_counts,
        reasoning_categories=reasoning_categories,
    )

    suggestions.sort(key=lambda s: _CONFIDENCE_WEIGHT.get(s["confidence"], 0), reverse=True)

    if not suggestions:
        suggestions = [_suggestion_no_safe_adjustment(health_status)]
        summary = "No bounded control suggestion identified for current signals."
    elif len(suggestions) == 1:
        summary = f"One bounded control suggestion identified: {suggestions[0]['category']}."
    else:
        cats = ", ".join(s["category"] for s in suggestions)
        summary = f"{len(suggestions)} bounded control suggestions identified: {cats}."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "suggestions": suggestions,
        "summary": summary,
    }
