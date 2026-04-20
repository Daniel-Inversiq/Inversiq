"""
app/services/simulation_preview.py

Deterministic simulation preview engine (v1).

Accepts control suggestions and returns structured, bounded previews of expected
operational effects. Read-only — no DB access, no mutations, no ML.

Every preview is template-driven and directional only. No numeric forecasts.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Template definitions — one per supported suggestion category
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, Any]] = {
    "confidence_threshold_tuning": {
        "simulation_summary": (
            "Lowering the review confidence threshold would likely reduce manual review pressure "
            "while keeping execution quality stable, provided failure metrics remain flat."
        ),
        "expected_impacts": [
            {
                "metric": "review_rate",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Narrower review triggering reduces unnecessary manual review volume for borderline-confidence runs.",
            },
            {
                "metric": "operator_throughput",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Fewer triggered reviews free operator capacity for higher-priority cases.",
            },
            {
                "metric": "failed_rate",
                "direction": "stable",
                "magnitude": "low",
                "rationale": "No direct execution-path change is proposed; failure behavior should remain unchanged.",
            },
        ],
        "risks": [
            "Reduced review coverage if input quality worsens after the change.",
            "Should not be considered if failed_rate is already degrading.",
        ],
        "assumptions": [
            "Current confidence degradation remains mild.",
            "No major input-pattern shift occurs in the next comparison window.",
        ],
        "safety_checks": [
            "Re-check failed_rate before applying.",
            "Re-check low_confidence_rate before applying.",
            "Verify review_rate trend over the next window after any implementation.",
        ],
        "confidence": "medium",
    },
    "review_trigger_narrowing": {
        "simulation_summary": (
            "Narrowing review trigger conditions would likely reduce operator review volume "
            "for low-risk runs while preserving coverage for genuinely ambiguous cases."
        ),
        "expected_impacts": [
            {
                "metric": "review_rate",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Fewer low-risk runs would trigger review, directly reducing overall review volume.",
            },
            {
                "metric": "operator_throughput",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Reduced review volume concentrates operator effort where it matters most.",
            },
            {
                "metric": "failed_rate",
                "direction": "stable",
                "magnitude": "low",
                "rationale": "Review narrowing does not alter execution logic; failure rate should be unaffected.",
            },
        ],
        "risks": [
            "Legitimate edge-case runs may slip through if trigger narrowing is too aggressive.",
            "Should not proceed if failed_rate is degrading — review coverage may be needed.",
        ],
        "assumptions": [
            "Current execution quality is stable or improving.",
            "Operator backlog is driven by over-broad triggers, not by genuine quality issues.",
        ],
        "safety_checks": [
            "Re-check failed_rate before applying.",
            "Monitor review_rate after one full comparison window.",
            "Do not narrow further until the first adjustment has been observed.",
        ],
        "confidence": "medium",
    },
    "validation_step_tightening": {
        "simulation_summary": (
            "Tightening upstream input validation would likely catch low-quality inputs earlier, "
            "reducing downstream fallback pressure. A mild throughput reduction is possible."
        ),
        "expected_impacts": [
            {
                "metric": "fallback_rate",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Stricter early gating prevents low-quality inputs from reaching fallback paths.",
            },
            {
                "metric": "downstream_quality",
                "direction": "improving",
                "magnitude": "low",
                "rationale": "Cleaner upstream inputs reduce cascading confidence degradation.",
            },
            {
                "metric": "run_count",
                "direction": "stable",
                "magnitude": "low",
                "rationale": "Some edge-case inputs may be rejected earlier; net throughput impact expected to be minor.",
            },
        ],
        "risks": [
            "Stricter validation may increase early-stage rejections for borderline valid inputs.",
            "Throughput may dip slightly if a meaningful share of inputs are currently borderline.",
        ],
        "assumptions": [
            "Upstream input patterns remain broadly stable.",
            "Fallback pressure is primarily driven by input quality, not downstream logic.",
        ],
        "safety_checks": [
            "Monitor run_count after implementation to detect unexpected throughput drops.",
            "Monitor failed_rate after implementation — do not tighten further if it rises.",
            "Re-check fallback_rate trend before applying.",
        ],
        "confidence": "medium",
    },
    "fallback_path_hardening": {
        "simulation_summary": (
            "Hardening fallback path safeguards would likely reduce repeated fallback pressure "
            "and surface upstream root causes more clearly rather than masking them."
        ),
        "expected_impacts": [
            {
                "metric": "fallback_rate",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Stronger fallback safeguards prevent low-quality outputs from passing as acceptable results.",
            },
            {
                "metric": "execution_resilience",
                "direction": "improving",
                "magnitude": "low",
                "rationale": "Clearer fallback boundaries make upstream failure patterns more visible.",
            },
            {
                "metric": "failed_rate",
                "direction": "stable",
                "magnitude": "low",
                "rationale": "Hardening is expected to surface failures rather than create new ones.",
            },
        ],
        "risks": [
            "Possible increase in surfaced failures in the short term as previously masked issues become visible.",
            "Complexity in fallback handling may increase if safeguards require new conditional logic.",
        ],
        "assumptions": [
            "Repeated fallback signals reflect genuine input quality issues, not routing logic bugs.",
            "Fallback path is not the sole valid path for a significant input segment.",
        ],
        "safety_checks": [
            "Verify fallback-related failures separately from general failed_rate.",
            "Re-check repeated_fallback signal counts before applying.",
            "Monitor failed_rate after implementation for unexpected increases.",
        ],
        "confidence": "medium",
    },
    "margin_guardrail_adjustment": {
        "simulation_summary": (
            "Raising the margin protection floor would likely reduce underpricing exposure "
            "and improve margin protection, with a possible mild conversion pressure."
        ),
        "expected_impacts": [
            {
                "metric": "underpricing_rate",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "A higher protection floor directly constrains quotes that fall below sustainable margin thresholds.",
            },
            {
                "metric": "margin_protection",
                "direction": "improving",
                "magnitude": "moderate",
                "rationale": "Bounded guardrail tightening reduces systematic underpricing risk.",
            },
            {
                "metric": "win_rate",
                "direction": "stable",
                "magnitude": "low",
                "rationale": "Minor floor adjustments within bounds are unlikely to materially affect competitive win rate.",
            },
        ],
        "risks": [
            "More aggressive pricing floor may reduce win rate if market sensitivity is high.",
            "Should not proceed if win_rate is already declining — may indicate overpricing risk.",
        ],
        "assumptions": [
            "Current underpricing is driven by too-low floor settings, not by external competitive pressure.",
            "Adjustment remains within pre-approved bounded pricing ranges.",
        ],
        "safety_checks": [
            "Compare win_rate and underpricing signals together before applying.",
            "Re-check underpricing_rate trend before applying.",
            "Confirm adjustment stays within bounded_range from the control suggestion.",
        ],
        "confidence": "medium",
    },
    "no_safe_adjustment": {
        "simulation_summary": (
            "No safe simulation preview is available. Current signals do not map to a "
            "bounded, deterministic adjustment at this time."
        ),
        "expected_impacts": [],
        "risks": [
            "No adjustment is proposed — continuing to monitor is the appropriate stance.",
        ],
        "assumptions": [
            "System is within acceptable operating parameters or signals are insufficient.",
        ],
        "safety_checks": [
            "Continue monitoring trends over the next comparison window.",
            "Re-evaluate if health status degrades or new signal clusters emerge.",
        ],
        "confidence": "low",
    },
}

# Weight for ordering previews by importance (higher = shown first)
_CONFIDENCE_WEIGHT: dict[str, int] = {"medium": 2, "low": 1}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _preview_for_suggestion(suggestion: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic preview entry for a single control suggestion."""
    category = suggestion.get("category", "no_safe_adjustment")
    action = suggestion.get("action", "no_action")
    template = _TEMPLATES.get(category, _TEMPLATES["no_safe_adjustment"])

    return {
        "category": category,
        "action": action,
        "simulation_summary": template["simulation_summary"],
        "expected_impacts": list(template["expected_impacts"]),
        "risks": list(template["risks"]),
        "assumptions": list(template["assumptions"]),
        "safety_checks": list(template["safety_checks"]),
        "confidence": template["confidence"],
    }


def _deduplicate_safety_checks(previews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact-duplicate safety check strings within each preview."""
    for preview in previews:
        seen: set[str] = set()
        deduped: list[str] = []
        for check in preview["safety_checks"]:
            if check not in seen:
                seen.add(check)
                deduped.append(check)
        preview["safety_checks"] = deduped
    return previews


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_simulation_preview(
    *,
    scope_type: str,
    scope_id: str,
    suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute deterministic simulation previews for a set of control suggestions.

    Pure function — no DB access, no persistence, no mutations.
    Returns deterministic output for identical inputs.
    """
    previews: list[dict[str, Any]] = [_preview_for_suggestion(s) for s in suggestions]
    previews = _deduplicate_safety_checks(previews)
    previews.sort(key=lambda p: _CONFIDENCE_WEIGHT.get(p["confidence"], 0), reverse=True)

    count = len(previews)
    if count == 0:
        summary = "No simulation previews generated."
    elif count == 1:
        summary = f"One deterministic simulation preview generated: {previews[0]['category']}."
    else:
        cats = ", ".join(p["category"] for p in previews)
        summary = f"{count} deterministic simulation previews generated: {cats}."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "previews": previews,
        "summary": summary,
    }
