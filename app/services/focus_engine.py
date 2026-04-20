"""
app/services/focus_engine.py

Deterministic priority scoring layer on top of health + trend data.

Given a scope's health status, trend direction, and intelligence signal
counts, produces a numeric priority score in [0, 100] and a human-readable
focus item.  All rules are explicit constants — no ML, no randomness.

Scoring formula:
  base         health contribution  (unhealthy=60, watch=30, healthy=5)
  trend_mod    degradation bonus    (worst degrading metric severity drives:
                                     high=+30, medium=+20, low=+10, none=+5;
                                     improving=-5; stable=0)
  signal_bonus signal contribution  (medium=+5/signal, high=+10/signal,
                                     total capped at +20)
  score = clamp(base + trend_mod + signal_bonus, 0, 100)

Priority tiers:
  critical ≥ 75  |  high ≥ 50  |  medium ≥ 25  |  low < 25
"""

from __future__ import annotations

from typing import Any, Optional

from app.intelligence.types import Severity, SignalType

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_HEALTH_BASE: dict[str, int] = {"unhealthy": 60, "watch": 30, "healthy": 5}

# Keyed by worst degrading metric severity (None = degrading but unclassified)
_TREND_DEGRADE_MOD: dict[Optional[str], int] = {
    "high": 30,
    "medium": 20,
    "low": 10,
    None: 5,
}
_TREND_IMPROVING_PENALTY = -5

_SIGNAL_SEVERITY_BONUS: dict[Severity, int] = {
    Severity.HIGH: 10,
    Severity.MEDIUM: 5,
    Severity.LOW: 0,
}
_SIGNAL_BONUS_CAP = 20

# Severity of each intelligence signal type (mirrors detectors.py)
_SIGNAL_TYPE_SEVERITY: dict[str, Severity] = {
    SignalType.LIKELY_UNDERPRICING.value: Severity.MEDIUM,
    SignalType.LIKELY_OVERPRICING.value: Severity.MEDIUM,
    SignalType.REPEATED_LOW_CONFIDENCE.value: Severity.MEDIUM,
    SignalType.REPEATED_FALLBACK.value: Severity.MEDIUM,
    SignalType.REPEATED_REVIEW_FLAG.value: Severity.LOW,
}

_PRIORITY_TIERS: list[tuple[int, str]] = [
    (75, "critical"),
    (50, "high"),
    (25, "medium"),
    (0, "low"),
]

_SEV_ORDER: dict[Optional[str], int] = {"high": 0, "medium": 1, "low": 2, None: 3}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _priority_label(score: int) -> str:
    for threshold, label in _PRIORITY_TIERS:
        if score >= threshold:
            return label
    return "low"


def _worst_degrading_severity(trend_metrics: list[dict[str, Any]]) -> Optional[str]:
    severities = {m["severity"] for m in trend_metrics if m["direction"] == "degrading" and m.get("severity")}
    for sev in ("high", "medium", "low"):
        if sev in severities:
            return sev
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_focus_score(
    health_status: str,
    trend_direction: str,
    trend_metrics: list[dict[str, Any]],
    signal_counts: dict[str, int],
) -> int:
    """Return a deterministic priority score in [0, 100]. Higher = more urgent."""
    base = _HEALTH_BASE.get(health_status, 5)

    if trend_direction == "degrading":
        worst_sev = _worst_degrading_severity(trend_metrics)
        trend_mod = _TREND_DEGRADE_MOD[worst_sev]
    elif trend_direction == "improving":
        trend_mod = _TREND_IMPROVING_PENALTY
    else:
        trend_mod = 0

    sig_bonus = 0
    for sig_type, count in signal_counts.items():
        sev = _SIGNAL_TYPE_SEVERITY.get(sig_type, Severity.LOW)
        sig_bonus += _SIGNAL_SEVERITY_BONUS.get(sev, 0) * count
    sig_bonus = min(sig_bonus, _SIGNAL_BONUS_CAP)

    return max(0, min(100, base + trend_mod + sig_bonus))


def extract_key_issues(
    health_status: str,
    failed_rate: float,
    needs_review_rate: float,
    low_confidence_rate: float,
    trend_metrics: list[dict[str, Any]],
    signal_counts: dict[str, int],
) -> list[str]:
    """Ordered list of issues driving this item's priority (worst first, max 6)."""
    from app.health.types import (
        UNHEALTHY_FAILED_RATE,
        UNHEALTHY_LOW_CONFIDENCE_RATE,
        UNHEALTHY_NEEDS_REVIEW_RATE,
        WATCH_FAILED_RATE,
        WATCH_LOW_CONFIDENCE_RATE,
        WATCH_NEEDS_REVIEW_RATE,
    )

    issues: list[str] = []

    if health_status in ("unhealthy", "watch"):
        if failed_rate >= WATCH_FAILED_RATE:
            tier = "unhealthy" if failed_rate >= UNHEALTHY_FAILED_RATE else "watch"
            issues.append(f"failed_rate {failed_rate:.0%} [{tier}]")
        if needs_review_rate >= WATCH_NEEDS_REVIEW_RATE:
            tier = "unhealthy" if needs_review_rate >= UNHEALTHY_NEEDS_REVIEW_RATE else "watch"
            issues.append(f"needs_review_rate {needs_review_rate:.0%} [{tier}]")
        if low_confidence_rate >= WATCH_LOW_CONFIDENCE_RATE:
            tier = "unhealthy" if low_confidence_rate >= UNHEALTHY_LOW_CONFIDENCE_RATE else "watch"
            issues.append(f"low_confidence_rate {low_confidence_rate:.0%} [{tier}]")

    degrading = sorted(
        [m for m in trend_metrics if m["direction"] == "degrading"],
        key=lambda m: _SEV_ORDER[m.get("severity")],
    )
    for m in degrading:
        sev = f" [{m['severity']}]" if m.get("severity") else ""
        delta = m.get("delta")
        delta_str = f" (Δ{delta:+.0%})" if delta is not None else ""
        issues.append(f"{m['name']} degrading{sev}{delta_str}")

    for sig_type, count in signal_counts.items():
        if count > 0:
            issues.append(f"signal: {sig_type} (×{count})")

    return issues[:6]


def build_reason(
    health_status: str,
    trend_direction: str,
    trend_metrics: list[dict[str, Any]],
    signal_counts: dict[str, int],
    priority_score: int,
) -> str:
    """One-sentence explanation of the priority score."""
    parts: list[str] = [f"health={health_status}", f"trend={trend_direction}"]

    worst_sev = _worst_degrading_severity(trend_metrics)
    if worst_sev is not None:
        degrading = sorted(
            [m for m in trend_metrics if m["direction"] == "degrading"],
            key=lambda m: _SEV_ORDER[m.get("severity")],
        )
        parts.append(f"worst degrading metric: {degrading[0]['name']} [{worst_sev}]")

    active = [t for t, c in signal_counts.items() if c > 0]
    if active:
        parts.append(f"active signals: {', '.join(active)}")

    return f"Score {priority_score}: {'; '.join(parts)}."


def build_focus_item(
    scope_type: str,
    scope_id: str,
    health_status: str,
    failed_rate: float,
    needs_review_rate: float,
    low_confidence_rate: float,
    signal_counts: dict[str, int],
    health_recommendation: str,
    trend_item: dict[str, Any],
) -> dict[str, Any]:
    """Combine health + trend data into a single prioritized focus item."""
    trend_direction = trend_item.get("trend", "stable")
    trend_metrics = trend_item.get("metrics", [])
    trend_recs = trend_item.get("recommendations", [])

    priority_score = compute_focus_score(
        health_status, trend_direction, trend_metrics, signal_counts
    )
    key_issues = extract_key_issues(
        health_status, failed_rate, needs_review_rate, low_confidence_rate,
        trend_metrics, signal_counts,
    )
    recommendation = trend_recs[0] if trend_recs else health_recommendation
    reason = build_reason(
        health_status, trend_direction, trend_metrics, signal_counts, priority_score
    )

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "priority_score": priority_score,
        "severity": _priority_label(priority_score),
        "health_status": health_status,
        "trend": trend_direction,
        "key_issues": key_issues,
        "recommendation": recommendation,
        "reason": reason,
    }
