"""
app/services/trend_engine.py

Deterministic trend comparison engine.

Compares current_metrics vs previous_metrics (both dicts from
metrics_aggregation.aggregate_metrics) and classifies each metric's
direction and severity.  Also computes an aggregate scope-level direction.

All logic is explicit rule-based arithmetic.  No ML, no randomness.

Metric direction semantics
--------------------------
  up_is_good   : success_rate, avg_confidence
  down_is_good : failed_rate, review_rate, low_confidence_rate,
                 negative_feedback_rate, fallback_rate, underpricing_rate

Context-only metrics (run_count, feedback_count) are not classified for
trend direction — they are included in the metrics list with
direction="context_only".

Thresholds
----------
  stable   : |delta| < STABLE_ABS_DELTA
             OR |relative_delta| < STABLE_REL_DELTA
  low      : |relative_delta| < MEDIUM_SEVERITY_REL
  medium   : |relative_delta| < HIGH_SEVERITY_REL
  high     : |relative_delta| >= HIGH_SEVERITY_REL

Aggregate scope trend
---------------------
  degrading   : any high-severity degrading metric  OR  degrading > improving
  improving   : improving > degrading  (no high-severity degrading)
  stable      : tie or all stable / insufficient_data
"""

from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration constants (explicit, not buried in logic)
# ---------------------------------------------------------------------------

# Metrics with trend direction semantics.  Excludes context-only counters.
_TREND_METRICS: tuple[str, ...] = (
    "avg_confidence",
    "failed_rate",
    "fallback_rate",
    "low_confidence_rate",
    "negative_feedback_rate",
    "review_rate",
    "success_rate",
    "underpricing_rate",
)

# Metrics included as context (shown in output but not direction-classified)
_CONTEXT_METRICS: tuple[str, ...] = (
    "feedback_count",
    "run_count",
)

# up_is_good  → increasing delta = improving
# down_is_good → decreasing delta = improving
_METRIC_SEMANTICS: dict[str, str] = {
    "avg_confidence": "up_is_good",
    "failed_rate": "down_is_good",
    "fallback_rate": "down_is_good",
    "low_confidence_rate": "down_is_good",
    "negative_feedback_rate": "down_is_good",
    "review_rate": "down_is_good",
    "success_rate": "up_is_good",
    "underpricing_rate": "down_is_good",
}

# Absolute delta below which a change is always called stable (e.g. 2pp on a rate)
STABLE_ABS_DELTA: float = 0.02

# Relative change fraction below which a change is always called stable (10%)
STABLE_REL_DELTA: float = 0.10

# Severity thresholds based on relative delta magnitude
MEDIUM_SEVERITY_REL: float = 0.25
HIGH_SEVERITY_REL: float = 0.50

# Avoid division by zero when previous value is zero
_EPSILON: float = 1e-9


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_severity(relative_delta: float) -> str:
    abs_rel = abs(relative_delta)
    if abs_rel >= HIGH_SEVERITY_REL:
        return "high"
    if abs_rel >= MEDIUM_SEVERITY_REL:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_metric_trend(
    metric_name: str,
    previous: Optional[float],
    current: Optional[float],
) -> dict[str, Any]:
    """
    Classify the trend for a single metric value pair.

    Returns
    -------
    dict with keys:
      name            str
      previous        float | None
      current         float | None
      delta           float | None
      relative_delta  float | None
      direction       "improving" | "degrading" | "stable" | "insufficient_data"
      severity        "low" | "medium" | "high" | None
    """
    if previous is None or current is None:
        return {
            "name": metric_name,
            "previous": previous,
            "current": current,
            "delta": None,
            "relative_delta": None,
            "direction": "insufficient_data",
            "severity": None,
        }

    delta = current - previous
    relative_delta = delta / max(abs(previous), _EPSILON)

    # Small absolute or small relative change → stable regardless of direction
    if abs(delta) < STABLE_ABS_DELTA or abs(relative_delta) < STABLE_REL_DELTA:
        return {
            "name": metric_name,
            "previous": round(previous, 4),
            "current": round(current, 4),
            "delta": round(delta, 4),
            "relative_delta": round(relative_delta, 4),
            "direction": "stable",
            "severity": None,
        }

    semantics = _METRIC_SEMANTICS.get(metric_name, "up_is_good")
    direction = (
        "improving" if (
            (semantics == "up_is_good" and delta > 0)
            or (semantics == "down_is_good" and delta < 0)
        )
        else "degrading"
    )
    severity = _classify_severity(relative_delta) if direction == "degrading" else None

    return {
        "name": metric_name,
        "previous": round(previous, 4),
        "current": round(current, 4),
        "delta": round(delta, 4),
        "relative_delta": round(relative_delta, 4),
        "direction": direction,
        "severity": severity,
    }


def compute_scope_trend(
    current_metrics: dict[str, Any],
    previous_metrics: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """
    Compare two metrics dicts and produce trend classifications.

    Parameters
    ----------
    current_metrics, previous_metrics
        Dicts as returned by metrics_aggregation.aggregate_metrics().

    Returns
    -------
    aggregate_direction : "improving" | "degrading" | "stable"
    metric_trends       : list of compute_metric_trend() result dicts,
                          one per trend metric (sorted by name) plus
                          context-only entries for run_count / feedback_count.
    """
    metric_trends: list[dict[str, Any]] = []

    # Direction-classified metrics
    for name in _TREND_METRICS:
        prev_val = previous_metrics.get(name)
        curr_val = current_metrics.get(name)
        metric_trends.append(compute_metric_trend(name, prev_val, curr_val))

    # Context-only metrics (no direction classification)
    for name in _CONTEXT_METRICS:
        prev_val = previous_metrics.get(name)
        curr_val = current_metrics.get(name)
        delta = (curr_val - prev_val) if (prev_val is not None and curr_val is not None) else None
        metric_trends.append({
            "name": name,
            "previous": prev_val,
            "current": curr_val,
            "delta": delta,
            "relative_delta": None,
            "direction": "context_only",
            "severity": None,
        })

    # Aggregate direction
    degrading = [t for t in metric_trends if t["direction"] == "degrading"]
    improving = [t for t in metric_trends if t["direction"] == "improving"]

    if any(t["severity"] == "high" for t in degrading):
        aggregate = "degrading"
    elif len(degrading) > len(improving):
        aggregate = "degrading"
    elif len(improving) > len(degrading):
        aggregate = "improving"
    else:
        aggregate = "stable"

    return aggregate, metric_trends
