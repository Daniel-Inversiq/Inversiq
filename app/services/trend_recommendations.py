"""
app/services/trend_recommendations.py

Maps degrading metric signals to short, actionable operator recommendations.

All mappings are deterministic static rules — no ML, no freeform generation.
The same degrading metric always produces the same recommendation text.

Usage
-----
    from app.services.trend_recommendations import (
        recommendation_for_metric,
        recommendations_for_trends,
    )

    # Inline per-metric recommendation (used when building metric list items)
    rec = recommendation_for_metric("failed_rate")

    # Deduplicated list for the top-level recommendations field
    recs = recommendations_for_trends(metric_trends)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Static recommendation map
# Keys match the metric names produced by metrics_aggregation.aggregate_metrics.
# Values are short imperative operator recommendations.
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[str, str] = {
    "failed_rate": (
        "Investigate recent failures and review error_category and failure_step patterns."
    ),
    "review_rate": (
        "Review confidence thresholds and operator review triggers to reduce manual volume."
    ),
    "avg_confidence": (
        "Check upstream extraction and parsing quality — overall confidence is declining."
    ),
    "low_confidence_rate": (
        "Inspect low-confidence runs for missing input fields or weak data sources."
    ),
    "fallback_rate": (
        "Inspect fallback triggers — repeated fallback use signals a gap in rule coverage."
    ),
    "negative_feedback_rate": (
        "Analyse lost deals for pricing or qualification patterns to reduce loss rate."
    ),
    "underpricing_rate": (
        "Review pricing rule calibration — won deals are consistently below engine estimate."
    ),
    "success_rate": (
        "Investigate what is causing the decline in successful pipeline completions."
    ),
}

# Severity ordering for sorting recommendations (worst first)
_SEVERITY_ORDER: dict[str | None, int] = {"high": 0, "medium": 1, "low": 2, None: 3}


def recommendation_for_metric(metric_name: str) -> str | None:
    """
    Return the recommendation for a single degrading metric, or None if no
    recommendation is defined for this metric name.
    """
    return _RECOMMENDATIONS.get(metric_name)


def recommendations_for_trends(metric_trends: list[dict]) -> list[str]:
    """
    Return a deduplicated, severity-ordered list of recommendations for all
    degrading metrics in the provided trend list.

    Parameters
    ----------
    metric_trends
        List of metric trend dicts as returned by
        trend_engine.compute_scope_trend().

    Returns
    -------
    list[str]
        Recommendations sorted by severity (high → medium → low) then metric
        name.  Each recommendation appears at most once even if multiple
        metrics map to the same text.
    """
    degrading = [t for t in metric_trends if t["direction"] == "degrading"]
    degrading.sort(
        key=lambda t: (_SEVERITY_ORDER.get(t.get("severity"), 3), t["name"])
    )

    seen: set[str] = set()
    result: list[str] = []
    for t in degrading:
        rec = _RECOMMENDATIONS.get(t["name"])
        if rec and rec not in seen:
            seen.add(rec)
            result.append(rec)

    return result
