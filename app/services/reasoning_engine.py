"""
app/services/reasoning_engine.py

Deterministic, read-only reasoning engine.

Accepts normalized signals from the health, trend, and intelligence layers
and returns structured root-cause reasoning with explicit, inspectable rules.

No ML, no DB queries, no persistence — pure function over dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Recommendation catalogue — static, explicit
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[str, list[str]] = {
    "upstream_input_quality": [
        "Inspect upstream extraction and parsing outputs for recent changes.",
        "Review fallback trigger conditions and fallback output quality.",
        "Compare recent input patterns with prior stable runs.",
    ],
    "confidence_threshold_mismatch": [
        "Review confidence thresholds — they may be too sensitive.",
        "Inspect steps producing low-confidence outputs most frequently.",
        "Verify whether review triggers are firing on acceptable runs.",
    ],
    "pricing_calibration_issue": [
        "Inspect pricing rules and margin protection constraints.",
        "Compare quoted prices against actual deal outcomes.",
        "Review recent underpricing patterns by deal type or vertical.",
    ],
    "rule_coverage_gap": [
        "Identify steps with persistent fallback usage.",
        "Expand or recalibrate rule coverage for low-confidence steps.",
        "Review whether fallback outputs meet minimum quality standards.",
    ],
    "operator_backlog": [
        "Review inbox throughput — prioritise unresolved high-severity items.",
        "Check whether review triggers are too broad.",
        "Consider adjusting review thresholds to reduce noise.",
    ],
    "anomaly_sensitivity_shift": [
        "Review anomaly detector thresholds for recent tuning changes.",
        "Compare anomaly volume with prior stable baseline periods.",
        "Confirm whether new anomaly patterns reflect real execution issues.",
    ],
    "workflow_structure_inefficiency": [
        "Review pipeline step order and dependency structure.",
        "Identify steps with consistently low confidence output.",
        "Check whether step configurations are appropriate for current inputs.",
    ],
    "mixed_or_unclear": [
        "Review the full set of degrading metrics for patterns.",
        "Inspect recent run samples to identify common failure modes.",
        "Check for any recent configuration or upstream changes.",
    ],
}

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _degrading(metrics: list[dict], name: str) -> Optional[dict]:
    for m in metrics:
        if m["name"] == name and m["direction"] == "degrading":
            return m
    return None


def _improving(metrics: list[dict], name: str) -> bool:
    return any(m["name"] == name and m["direction"] == "improving" for m in metrics)


def _metric_severity(m: Optional[dict]) -> int:
    if m is None:
        return 0
    return _SEVERITY_WEIGHT.get(m.get("severity") or "", 1)


def _has_signal(signal_counts: dict, signal_type: str) -> bool:
    return signal_counts.get(signal_type, 0) > 0


def _evidence_label(m: dict) -> str:
    sev = m.get("severity")
    label = f"{m['name']} is degrading"
    if sev:
        label += f" ({sev} severity)"
    return label


# ---------------------------------------------------------------------------
# Reasoning item dataclass
# ---------------------------------------------------------------------------


@dataclass
class _ReasoningItem:
    category: str
    root_cause: str
    confidence: str  # "high" | "medium" | "low"
    evidence: list[str]
    recommendations: list[str]
    _weight: int = field(default=0, repr=False)


# ---------------------------------------------------------------------------
# Rule functions — each returns a _ReasoningItem or None
# ---------------------------------------------------------------------------


def _rule_upstream_input_quality(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    failed = _degrading(metrics, "failed_rate")
    fallback = _degrading(metrics, "fallback_rate")
    confidence = _degrading(metrics, "avg_confidence")
    has_repeated_fallback = _has_signal(signals, "REPEATED_FALLBACK")

    if not failed:
        return None
    if not (fallback or confidence or has_repeated_fallback):
        return None

    evidence = [_evidence_label(failed)]
    if fallback:
        evidence.append(_evidence_label(fallback))
    if confidence:
        evidence.append(_evidence_label(confidence))
    if has_repeated_fallback:
        evidence.append("REPEATED_FALLBACK signal detected across multiple runs")

    sev = _metric_severity(failed) + _metric_severity(fallback)
    conf = "high" if sev >= 4 else "medium" if sev >= 2 else "low"

    return _ReasoningItem(
        category="upstream_input_quality",
        root_cause="Likely degraded extraction or parsing quality causing run failures.",
        confidence=conf,
        evidence=evidence,
        recommendations=list(_RECOMMENDATIONS["upstream_input_quality"]),
        _weight=sev + 10,
    )


def _rule_confidence_threshold_mismatch(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    review = _degrading(metrics, "review_rate")
    confidence = _degrading(metrics, "avg_confidence")
    low_conf = _degrading(metrics, "low_confidence_rate")
    has_repeated_low_conf = _has_signal(signals, "REPEATED_LOW_CONFIDENCE")

    if not review:
        return None
    if not (confidence or low_conf or has_repeated_low_conf):
        return None

    evidence = [_evidence_label(review)]
    if confidence:
        evidence.append(_evidence_label(confidence))
    if low_conf:
        evidence.append(_evidence_label(low_conf))
    if has_repeated_low_conf:
        evidence.append("REPEATED_LOW_CONFIDENCE signal detected on specific steps")

    sev = _metric_severity(review) + _metric_severity(confidence or low_conf)
    conf = "high" if sev >= 4 else "medium"

    return _ReasoningItem(
        category="confidence_threshold_mismatch",
        root_cause=(
            "Confidence thresholds may be miscalibrated or input quality has degraded,"
            " driving excessive review routing."
        ),
        confidence=conf,
        evidence=evidence,
        recommendations=list(_RECOMMENDATIONS["confidence_threshold_mismatch"]),
        _weight=sev + 8,
    )


def _rule_pricing_calibration_issue(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    underpricing = _degrading(metrics, "underpricing_rate")
    neg_feedback = _degrading(metrics, "negative_feedback_rate")
    has_underpricing = _has_signal(signals, "LIKELY_UNDERPRICING")
    has_overpricing = _has_signal(signals, "LIKELY_OVERPRICING")

    if not (underpricing or has_underpricing or has_overpricing):
        return None

    evidence = []
    if underpricing:
        evidence.append(_evidence_label(underpricing))
    if has_underpricing:
        evidence.append("LIKELY_UNDERPRICING signal: won deals have actual price below estimate")
    if has_overpricing:
        evidence.append("LIKELY_OVERPRICING signal: high loss rate suggests systematic overpricing")
    if neg_feedback:
        evidence.append(_evidence_label(neg_feedback))

    root = (
        "Pricing calibration issue — systematic underpricing is eroding margins."
        if (underpricing or has_underpricing)
        else "Pricing calibration issue — systematic overpricing is causing deal losses."
    )
    sev = _metric_severity(underpricing) + (2 if (has_underpricing or has_overpricing) else 0)
    conf = "high" if sev >= 3 else "medium"

    return _ReasoningItem(
        category="pricing_calibration_issue",
        root_cause=root,
        confidence=conf,
        evidence=evidence,
        recommendations=list(_RECOMMENDATIONS["pricing_calibration_issue"]),
        _weight=sev + 6,
    )


def _rule_rule_coverage_gap(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    fallback = _degrading(metrics, "fallback_rate")
    low_conf = _degrading(metrics, "low_confidence_rate")
    failed = _degrading(metrics, "failed_rate")
    has_repeated_fallback = _has_signal(signals, "REPEATED_FALLBACK")
    has_repeated_low_conf = _has_signal(signals, "REPEATED_LOW_CONFIDENCE")

    if not (fallback or has_repeated_fallback):
        return None
    if failed:
        return None  # upstream_input_quality is the more specific match
    if not (low_conf or has_repeated_low_conf):
        return None

    evidence = []
    if fallback:
        evidence.append(_evidence_label(fallback))
    if has_repeated_fallback:
        evidence.append("REPEATED_FALLBACK signal on specific steps")
    if low_conf:
        evidence.append(_evidence_label(low_conf))
    if has_repeated_low_conf:
        evidence.append("REPEATED_LOW_CONFIDENCE signal on specific steps")

    sev = _metric_severity(fallback) + _metric_severity(low_conf)
    conf = "medium" if sev >= 2 else "low"

    return _ReasoningItem(
        category="rule_coverage_gap",
        root_cause=(
            "Pipeline rules are falling back frequently with low confidence"
            " — likely incomplete rule coverage for current input patterns."
        ),
        confidence=conf,
        evidence=evidence,
        recommendations=list(_RECOMMENDATIONS["rule_coverage_gap"]),
        _weight=sev + 4,
    )


def _rule_operator_backlog(
    metrics: list[dict], signals: dict, health_status: str
) -> Optional[_ReasoningItem]:
    review = _degrading(metrics, "review_rate")
    has_review_flag = _has_signal(signals, "REPEATED_REVIEW_FLAG")

    if not (review or has_review_flag):
        return None
    if health_status == "healthy" and not has_review_flag:
        return None  # Not strong enough signal without health context

    evidence = []
    if review:
        evidence.append(_evidence_label(review))
    if has_review_flag:
        evidence.append("REPEATED_REVIEW_FLAG signal: pipeline repeatedly enters review state")
    if health_status in ("watch", "unhealthy"):
        evidence.append(f"Health status is {health_status}")

    sev = _metric_severity(review) + (2 if has_review_flag else 0)
    conf = "medium" if sev >= 2 else "low"

    return _ReasoningItem(
        category="operator_backlog",
        root_cause=(
            "Review volume is elevated — likely operator backlog or overly broad review triggers."
        ),
        confidence=conf,
        evidence=evidence,
        recommendations=list(_RECOMMENDATIONS["operator_backlog"]),
        _weight=sev + 3,
    )


def _rule_anomaly_sensitivity_shift(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    failed = _degrading(metrics, "failed_rate")
    review = _degrading(metrics, "review_rate")
    has_review_flag = _has_signal(signals, "REPEATED_REVIEW_FLAG")

    if failed or review:
        return None  # More specific rules will fire
    if not has_review_flag:
        return None

    return _ReasoningItem(
        category="anomaly_sensitivity_shift",
        root_cause=(
            "Anomaly volume is elevated but execution metrics are stable"
            " — likely a monitoring sensitivity change, not real degradation."
        ),
        confidence="low",
        evidence=[
            "REPEATED_REVIEW_FLAG signal present despite stable failed_rate and review_rate",
            "Pattern suggests sensitivity tuning rather than execution issues",
        ],
        recommendations=list(_RECOMMENDATIONS["anomaly_sensitivity_shift"]),
        _weight=2,
    )


def _rule_workflow_structure_inefficiency(
    metrics: list[dict], signals: dict
) -> Optional[_ReasoningItem]:
    low_conf = _degrading(metrics, "low_confidence_rate")
    failed = _degrading(metrics, "failed_rate")
    fallback = _degrading(metrics, "fallback_rate")
    review = _degrading(metrics, "review_rate")

    if not low_conf:
        return None
    if failed or fallback or review:
        return None  # Covered by more specific rules

    sev = _metric_severity(low_conf)

    return _ReasoningItem(
        category="workflow_structure_inefficiency",
        root_cause=(
            "Low confidence is increasing without failures or fallbacks"
            " — likely workflow structure or step configuration issues."
        ),
        confidence="low",
        evidence=[_evidence_label(low_conf)],
        recommendations=list(_RECOMMENDATIONS["workflow_structure_inefficiency"]),
        _weight=sev + 1,
    )


# Ordered rule list — each function has signature (metrics, signals) -> Optional[_ReasoningItem]
# Operator_backlog wraps the three-arg variant below.
_RULES = [
    _rule_upstream_input_quality,
    _rule_confidence_threshold_mismatch,
    _rule_pricing_calibration_issue,
    _rule_rule_coverage_gap,
    _rule_anomaly_sensitivity_shift,
    _rule_workflow_structure_inefficiency,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_reasoning(
    *,
    scope_type: str,
    scope_id: str,
    health_status: str,
    metric_trends: list[dict],
    signal_counts: dict,
) -> dict[str, Any]:
    """
    Deterministic root-cause reasoning over normalized pipeline signals.

    Parameters
    ----------
    scope_type:    "pipeline" or "vertical"
    scope_id:      pipeline_name or vertical_id
    health_status: "healthy" | "watch" | "unhealthy" (from health summary)
    metric_trends: list of metric trend dicts from compute_scope_trend()
    signal_counts: dict mapping signal_type -> count (from health summary)

    Returns structured reasoning with category, root_cause, confidence,
    evidence, and deduplicated recommendations — ordered by severity.
    """
    candidates: list[_ReasoningItem] = []

    for rule_fn in _RULES:
        result = rule_fn(metric_trends, signal_counts)
        if result is not None:
            candidates.append(result)

    # operator_backlog needs health_status — call separately
    ob = _rule_operator_backlog(metric_trends, signal_counts, health_status)
    if ob is not None:
        candidates.append(ob)

    # Deduplicate recommendations globally across all items
    seen: set[str] = set()
    for item in candidates:
        deduped = []
        for rec in item.recommendations:
            if rec not in seen:
                deduped.append(rec)
                seen.add(rec)
        item.recommendations = deduped

    candidates.sort(key=lambda x: -x._weight)

    if not candidates:
        candidates = [
            _ReasoningItem(
                category="mixed_or_unclear",
                root_cause="Insufficient or contradictory signals — no clear root cause identified.",
                confidence="low",
                evidence=_degrading_evidence(metric_trends, signal_counts),
                recommendations=list(_RECOMMENDATIONS["mixed_or_unclear"]),
            )
        ]

    reasoning = [
        {
            "category": item.category,
            "root_cause": item.root_cause,
            "confidence": item.confidence,
            "evidence": item.evidence,
            "recommendations": item.recommendations,
        }
        for item in candidates
    ]

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "health_status": health_status,
        "reasoning": reasoning,
        "summary": _summary(candidates, health_status),
    }


def _degrading_evidence(metric_trends: list[dict], signal_counts: dict) -> list[str]:
    evidence = [_evidence_label(m) for m in metric_trends if m["direction"] == "degrading"]
    for sig, count in signal_counts.items():
        if count > 0:
            evidence.append(f"{sig} signal detected ({count} occurrence(s))")
    return evidence or ["No significant degrading signals detected."]


def _summary(candidates: list[_ReasoningItem], health_status: str) -> str:
    if not candidates:
        return "No significant issues detected."
    top = candidates[0]
    conf_label = {"high": "strong", "medium": "moderate", "low": "weak"}.get(top.confidence, "")
    prefix = (
        "Performance degradation is"
        if health_status in ("watch", "unhealthy")
        else "Analysis shows performance is"
    )
    category_label = top.category.replace("_", " ")
    return f"{prefix} most likely driven by {category_label} ({conf_label} confidence)."
