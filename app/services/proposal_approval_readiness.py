"""
app/services/proposal_approval_readiness.py

Deterministic proposal approval readiness evaluation (v1).

Accepts proposals plus their governance context and returns approval-readiness
annotations. Pure function — no DB access, no state mutations, no ML.

Each proposal is evaluated against explicit blocking and warning rules.
Output is stable: identical inputs always produce identical output.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Readiness status constants
# ---------------------------------------------------------------------------

APPROVAL_READY = "approval_ready"
BLOCKED_WITH_WARNINGS = "blocked_with_warnings"
BLOCKED = "blocked"

# ---------------------------------------------------------------------------
# Rule tables
# ---------------------------------------------------------------------------

_TERMINAL_REVIEW_STATES: frozenset[str] = frozenset({"rejected", "archived"})
_STALE_BLOCK_STATUSES: frozenset[str] = frozenset({"stale", "superseded"})
_STALE_WARN_STATUSES: frozenset[str] = frozenset({"aging"})

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


def _preview_for_category(category: str, previews: list[dict[str, Any]]) -> dict[str, Any] | None:
    for p in previews:
        if p.get("category") == category:
            return p
    return None


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Per-proposal evaluation
# ---------------------------------------------------------------------------


def _evaluate_change(
    change: dict[str, Any],
    *,
    review_state: dict[str, Any] | None,
    change_conflicts: list[dict[str, Any]],
    staleness_entry: dict[str, Any] | None,
    preview: dict[str, Any] | None,
    reasoning_categories: list[str],
    control_categories: list[str],
) -> dict[str, Any]:
    change_id = change.get("change_id", "")
    category = change.get("category", "")
    risk_level = (change.get("approval_intent") or {}).get("risk_level", "")

    blocking_reasons: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    # --- Hard-block rules ---

    # Defensive: missing structural fields
    if not change.get("target") or not change.get("proposed_change"):
        blocking_reasons.append(
            "Proposal is missing required 'target' or 'proposed_change' fields."
        )
        required_actions.append(
            "Inspect proposal generation — this change cannot be evaluated safely."
        )

    # Review state: terminal blocking status
    review_status = (review_state or {}).get("status", "pending")
    if review_status in _TERMINAL_REVIEW_STATES:
        blocking_reasons.append(f"Proposal review state is '{review_status}'.")
        required_actions.append(
            "Do not approve a proposal that has been rejected or archived."
        )

    # Staleness: hard-block statuses
    staleness_status = (staleness_entry or {}).get("status", "fresh")
    if staleness_status in _STALE_BLOCK_STATUSES:
        blocking_reasons.append(f"Proposal is {staleness_status}.")
        if staleness_status == "superseded":
            required_actions.append(
                "A newer proposal targets the same parameter — approve the newer one instead."
            )
        else:
            required_actions.append(
                "Regenerate or re-review this proposal before approval."
            )

    # Conflicts: any high-severity
    high_conflicts = [c for c in change_conflicts if c.get("severity") == "high"]
    if high_conflicts:
        count = len(high_conflicts)
        blocking_reasons.append(
            f"Proposal is involved in {count} high-severity conflict(s)."
        )
        required_actions.append("Resolve proposal conflicts before approval.")

    # Control suggestion category no longer active
    if category and control_categories is not None and category not in control_categories:
        blocking_reasons.append(
            "The control suggestion category backing this proposal is no longer active."
        )
        required_actions.append("Reconfirm root-cause evidence before approval.")

    # Reasoning has disappeared entirely (no categories remain)
    if reasoning_categories is not None and len(reasoning_categories) == 0 and category:
        blocking_reasons.append(
            "No active reasoning categories — supporting evidence cannot be confirmed."
        )
        required_actions.append("Reconfirm root-cause evidence before approval.")

    # --- Warning-only rules ---

    # Staleness: aging
    if staleness_status in _STALE_WARN_STATUSES:
        warnings.append(
            "Proposal is aging — last confirmed signals may no longer reflect current state."
        )
        required_actions.append(
            "Perform a fresh review of reasoning and simulation before approval."
        )

    # Conflicts: medium-severity only (no high)
    medium_conflicts = [c for c in change_conflicts if c.get("severity") == "medium"]
    if medium_conflicts and not high_conflicts:
        count = len(medium_conflicts)
        warnings.append(f"Proposal is involved in {count} medium-severity conflict(s).")
        required_actions.append("Review conflict context before approving.")

    # Simulation preview: low confidence
    if preview and preview.get("confidence") == "low":
        warnings.append("Simulation preview confidence is low.")
        required_actions.append(
            "Perform a fresh review of reasoning and simulation before approval."
        )

    # Risk level: high
    if risk_level == "high":
        warnings.append("Proposal risk level is high — requires senior review before approval.")

    # --- Determine overall status ---

    if blocking_reasons:
        status = BLOCKED
        severity = "high"
        summary = "Proposal must not be approved — one or more blocking conditions are present."
        recommendation = "Do not approve until all blocking conditions are cleared."
    elif warnings:
        status = BLOCKED_WITH_WARNINGS
        severity = "medium"
        summary = "Proposal requires caution — warnings must be reviewed before approval."
        recommendation = "Review all warnings carefully before proceeding to human approval."
    else:
        status = APPROVAL_READY
        severity = "low"
        summary = "Proposal is currently ready for human approval."
        recommendation = "Proposal is currently ready for human approval."

    return {
        "change_id": change_id,
        "status": status,
        "severity": severity,
        "summary": summary,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "required_actions": _deduplicate(required_actions),
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_proposal_approval_readiness(
    *,
    scope_type: str,
    scope_id: str,
    proposed_changes: list[dict[str, Any]],
    review_states: dict[str, dict[str, Any]],
    conflicts: list[dict[str, Any]],
    staleness: list[dict[str, Any]],
    reasoning_categories: list[str],
    control_categories: list[str],
    simulation_previews: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Evaluate approval readiness for a set of proposed changes.

    Pure function — no DB access, no mutations, no ML.
    Returns deterministic output for identical inputs.

    Args:
        scope_type: "pipeline" or "vertical"
        scope_id: pipeline_name or vertical_id
        proposed_changes: freshly computed proposed change dicts
        review_states: mapping of change_id → {status, created_at, updated_at, persisted}
        conflicts: conflict annotation list from detect_proposal_conflicts
        staleness: staleness annotation list from detect_proposal_staleness
        reasoning_categories: active reasoning category strings
        control_categories: active control suggestion category strings
        simulation_previews: preview dicts from compute_simulation_preview
    """
    readiness: list[dict[str, Any]] = []

    for change in proposed_changes:
        change_id = change.get("change_id", "")
        category = change.get("category", "")

        entry = _evaluate_change(
            change,
            review_state=review_states.get(change_id),
            change_conflicts=_conflicts_for_change(change_id, conflicts),
            staleness_entry=_staleness_for_change(change_id, staleness),
            preview=_preview_for_category(category, simulation_previews),
            reasoning_categories=reasoning_categories,
            control_categories=control_categories,
        )
        readiness.append(entry)

    blocked_count = sum(1 for r in readiness if r["status"] == BLOCKED)
    warnings_count = sum(1 for r in readiness if r["status"] == BLOCKED_WITH_WARNINGS)
    ready_count = sum(1 for r in readiness if r["status"] == APPROVAL_READY)

    if not readiness:
        summary = "No proposals to evaluate."
    elif blocked_count > 0:
        summary = (
            f"{blocked_count} proposal(s) blocked; "
            f"{warnings_count} with warnings; "
            f"{ready_count} approval-ready."
        )
    elif warnings_count > 0:
        summary = f"{warnings_count} proposal(s) have warnings; {ready_count} approval-ready."
    else:
        summary = f"All {ready_count} proposal(s) are approval-ready."

    return {
        "scope": scope_type,
        "scope_id": scope_id,
        "proposal_count": len(proposed_changes),
        "blocked_count": blocked_count,
        "warnings_count": warnings_count,
        "ready_count": ready_count,
        "summary": summary,
        "approval_readiness": readiness,
    }
