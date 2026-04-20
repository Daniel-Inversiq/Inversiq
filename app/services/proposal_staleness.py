"""
app/services/proposal_staleness.py

Deterministic, read-only proposal staleness detection layer (v1).

Accepts proposed changes with their current review context and returns
staleness annotations per proposal — one annotation per change.

Staleness statuses:
  - fresh:      recently created/updated and still aligned with current context
  - aging:      pending for more than AGING_DAYS, should be rechecked soon
  - stale:      pending too long OR supporting context has disappeared
  - superseded: a newer pending proposal targets the same parameter

Pure function over dicts — no DB access, no mutations, no ML.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

AGING_DAYS = 7
STALE_DAYS = 14

_SEVERITY: dict[str, str] = {
    "fresh": "low",
    "aging": "medium",
    "stale": "high",
    "superseded": "medium",
}

_RECOMMENDATIONS: dict[str, str] = {
    "fresh": "Proposal remains current.",
    "aging": "Re-check reasoning and trend context before approval.",
    "stale": "Regenerate or re-review this proposal before taking action.",
    "superseded": "Review the newer overlapping proposal and archive this one if no longer needed.",
}

_SUMMARIES: dict[str, str] = {
    "fresh": "This proposal is current and ready for review.",
    "aging": "This proposal is aging and should be re-reviewed before approval.",
    "stale": "This proposal is stale and should be regenerated or re-reviewed before action.",
    "superseded": "This proposal may have been superseded by a newer overlapping proposal.",
}

_REASONS: dict[str, str] = {
    "fresh": "The proposal is recent and its supporting context appears current.",
    "aging": "The proposal remains pending and its supporting signals have not been re-confirmed recently.",
    "stale": "The proposal has remained pending too long or its supporting context has weakened.",
    "superseded": "A newer proposal targeting the same parameter was created more recently.",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parameter(change: dict[str, Any]) -> str:
    return (change.get("target") or {}).get("parameter", "unknown_parameter")


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _age_days(dt: datetime, now: datetime) -> float:
    return (now - _ensure_utc(dt)).total_seconds() / 86400


def _build_superseded_ids(
    proposed_changes: list[dict[str, Any]],
    review_states: dict[str, dict[str, Any]],
) -> set[str]:
    """
    For each target parameter with multiple pending persisted proposals,
    mark the older-created ones as superseded by the most recently created one.
    Only considers proposals that are persisted and pending.
    """
    param_entries: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for change in proposed_changes:
        cid = change["change_id"]
        rs = review_states.get(cid, {})
        if (
            rs.get("persisted")
            and rs.get("status") == "pending"
            and rs.get("created_at") is not None
        ):
            param_entries[_parameter(change)].append((cid, _ensure_utc(rs["created_at"])))

    superseded: set[str] = set()
    for entries in param_entries.values():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda x: x[1])
        for cid, _ in entries[:-1]:
            superseded.add(cid)
    return superseded


def _build_annotation(
    change_id: str,
    staleness: str,
    signals: list[str],
) -> dict[str, Any]:
    return {
        "change_id": change_id,
        "status": staleness,
        "severity": _SEVERITY[staleness],
        "summary": _SUMMARIES[staleness],
        "reason": _REASONS[staleness],
        "signals": signals,
        "recommendation": _RECOMMENDATIONS[staleness],
    }


def _annotate_one(
    change: dict[str, Any],
    review_state: dict[str, Any],
    current_control_categories: set[str],
    is_superseded: bool,
    now: datetime,
) -> dict[str, Any]:
    change_id = change["change_id"]
    category = change.get("category", "")

    status_val = review_state.get("status", "pending")
    persisted = review_state.get("persisted", False)
    created_at: Optional[datetime] = review_state.get("created_at")
    updated_at: Optional[datetime] = review_state.get("updated_at")

    signals: list[str] = []

    # Terminal states — no longer pending, nothing to flag
    if status_val in ("approved", "rejected", "archived"):
        signals.append(f"proposal is {status_val}")
        return _build_annotation(change_id, "fresh", signals)

    # Not persisted — freshly computed, no review history to age against
    if not persisted:
        signals.append("proposal is newly computed, no review history")
        return _build_annotation(change_id, "fresh", signals)

    # All remaining paths: pending + persisted
    signals.append("proposal still pending")

    age = _age_days(created_at, now) if created_at else None

    # Superseded check (before stale — more specific about why)
    if is_superseded:
        signals.append("a newer proposal targets the same parameter")
        return _build_annotation(change_id, "superseded", signals)

    # Stale conditions
    stale_signals: list[str] = []

    if age is not None and age >= STALE_DAYS:
        stale_signals.append(f"proposal has been pending for more than {STALE_DAYS} days")

    if category and category not in current_control_categories:
        stale_signals.append("supporting control suggestion category is no longer active")

    if stale_signals:
        signals.extend(stale_signals)
        return _build_annotation(change_id, "stale", signals)

    # Aging check
    if age is not None and age >= AGING_DAYS:
        signals.append(f"proposal created more than {AGING_DAYS} days ago")
        last_change = updated_at or created_at
        if last_change and _age_days(last_change, now) >= AGING_DAYS:
            signals.append("no recent state change")
        return _build_annotation(change_id, "aging", signals)

    # Default: fresh
    if category and category in current_control_categories:
        signals.append("supporting control suggestion category still active")
    return _build_annotation(change_id, "fresh", signals)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_proposal_staleness(
    *,
    scope_type: str,
    scope_id: str,
    proposed_changes: list[dict[str, Any]],
    review_states: dict[str, dict[str, Any]],
    current_reasoning_categories: list[str],
    current_control_categories: list[str],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Analyze proposed changes and return staleness annotations per proposal.

    Pure function — no DB access, no mutations, no ML.
    Returns deterministic output for identical inputs.

    Args:
        scope_type: "pipeline" or "vertical"
        scope_id: pipeline_name or vertical_id
        proposed_changes: list of proposed change dicts from compute_proposed_changes
        review_states: mapping of change_id → {status, created_at, updated_at, persisted}
        current_reasoning_categories: active reasoning categories from run_reasoning
        current_control_categories: active suggestion categories from compute_control_suggestions
        now: optional override for current time (enables deterministic tests)

    Returns:
        Dict with scope metadata and one staleness annotation per proposal.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    control_cats = set(current_control_categories)
    superseded_ids = _build_superseded_ids(proposed_changes, review_states)

    annotations = []
    for change in proposed_changes:
        change_id = change["change_id"]
        rs = review_states.get(
            change_id,
            {"status": "pending", "persisted": False, "created_at": None, "updated_at": None},
        )
        annotations.append(
            _annotate_one(
                change=change,
                review_state=rs,
                current_control_categories=control_cats,
                is_superseded=change_id in superseded_ids,
                now=now,
            )
        )

    status_counts: dict[str, int] = {}
    for a in annotations:
        s = a["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    stale_count = status_counts.get("stale", 0)
    aging_count = status_counts.get("aging", 0)
    superseded_count = status_counts.get("superseded", 0)

    if not annotations:
        summary = "No proposals to evaluate."
    elif stale_count > 0:
        summary = f"{stale_count} stale proposal(s) require attention before approval."
    elif aging_count > 0:
        summary = f"{aging_count} proposal(s) are aging and should be rechecked."
    elif superseded_count > 0:
        summary = f"{superseded_count} proposal(s) may be superseded."
    else:
        summary = "All proposals appear current."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "proposal_count": len(proposed_changes),
        "stale_count": stale_count,
        "aging_count": aging_count,
        "summary": summary,
        "staleness": annotations,
    }
