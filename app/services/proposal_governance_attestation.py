"""
app/services/proposal_governance_attestation.py

Server-side governance attestation service.

Given a tenant_id + change_id, recomputes the current governance state for
that specific proposal by running the full deterministic governance chain.

Used by workflow action endpoints (approve, mark-ready-for-apply) to enforce
server-side governance rather than trusting caller-supplied values.

Design:
  - Deterministic and read-only
  - No persistence, no caching
  - Reuses existing governance service functions
  - Returns a clean "unattestable" result when the proposal cannot be located
    in the current governance output (scope not in health summaries, or change
    not emitted by the current governance chain for the given scope)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.health.summary import pipeline_health_summaries, vertical_health_summaries
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.control_suggestions import compute_control_suggestions
from app.services.metrics_aggregation import aggregate_metrics
from app.services.proposal_apply_planning import compute_apply_planning
from app.services.proposal_approval_readiness import evaluate_proposal_approval_readiness
from app.services.proposal_conflicts import detect_proposal_conflicts
from app.services.proposal_staleness import detect_proposal_staleness
from app.services.proposed_changes import compute_proposed_changes
from app.services.reasoning_engine import run_reasoning
from app.services.simulation_preview import compute_simulation_preview
from app.services.trend_engine import compute_scope_trend


def compute_governance_attestation(
    db: Session,
    *,
    tenant_id: str,
    change_id: str,
    window_days: int = 7,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """
    Recompute current governance state for a specific proposal.

    Returns an attestation dict with ``attestable=True`` and current governance
    statuses, or ``attestable=False`` with a reason if the proposal cannot be
    located in the current governance output.

    Output shape (attestable=True):
        {
            "attestable": True,
            "change_id": "...",
            "scope_type": "pipeline",
            "scope_id": "...",
            "approval_readiness_status": "approval_ready" | "blocked_with_warnings" | "blocked",
            "apply_planning_status": "planned" | "requires_combined_plan" | "blocked_from_planning",
            "conflict_status": {"has_high_conflict": bool, "has_medium_conflict": bool},
            "staleness_status": "fresh" | "aging" | "stale" | "superseded",
            "attestation_summary": "...",
            "attested_at": "ISO timestamp",
        }

    Output shape (attestable=False):
        {
            "attestable": False,
            "change_id": "...",
            "scope_type": None,
            "scope_id": None,
            "approval_readiness_status": None,
            "apply_planning_status": None,
            "conflict_status": None,
            "staleness_status": None,
            "attestation_summary": "<reason>",
            "attested_at": None,
        }
    """
    # Parse change_id: expected format scope_type:scope_id:category:parameter
    parts = change_id.split(":", 3)
    if len(parts) != 4:
        return _unattestable(
            change_id,
            "change_id does not match expected format "
            "scope_type:scope_id:category:parameter",
        )

    scope_type, scope_id = parts[0], parts[1]

    if scope_type not in ("pipeline", "vertical"):
        return _unattestable(change_id, f"Unknown scope_type '{scope_type}'")

    # Locate health summary for this scope
    if scope_type == "pipeline":
        health_items = pipeline_health_summaries(
            db, tenant_id=tenant_id, lookback_days=lookback_days
        )
        health = next(
            (h for h in health_items if h.pipeline_name == scope_id), None
        )
    else:
        health_items = vertical_health_summaries(
            db, tenant_id=tenant_id, lookback_days=lookback_days
        )
        health = next(
            (h for h in health_items if h.vertical_id == scope_id), None
        )

    if health is None:
        return _unattestable(
            change_id,
            f"Scope '{scope_type}:{scope_id}' not found in current health summaries",
        )

    # Run full governance chain for this scope
    now = datetime.now(timezone.utc)
    current_end = now
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    current_metrics = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=current_start,
        end=current_end,
        tenant_id=tenant_id,
    )
    previous_metrics = aggregate_metrics(
        db,
        scope_type=scope_type,
        scope_key=scope_id,
        start=previous_start,
        end=current_start,
        tenant_id=tenant_id,
    )
    _, metric_trends = compute_scope_trend(current_metrics, previous_metrics)

    reasoning = run_reasoning(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health.health_status,
        metric_trends=metric_trends,
        signal_counts=health.signal_counts,
    )
    reasoning_categories = [r["category"] for r in reasoning.get("reasoning", [])]

    control = compute_control_suggestions(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health.health_status,
        metric_trends=metric_trends,
        signal_counts=health.signal_counts,
        reasoning_categories=reasoning_categories,
    )
    control_categories = [s["category"] for s in control.get("suggestions", [])]

    proposed = compute_proposed_changes(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=control["suggestions"],
        reasoning_categories=reasoning_categories,
        metric_trends=metric_trends,
        signal_counts=health.signal_counts,
    )
    changes = proposed["proposed_changes"]

    # Verify the specific change is present in the current governance output
    change = next((c for c in changes if c["change_id"] == change_id), None)
    if change is None:
        return _unattestable(
            change_id,
            f"Proposal '{change_id}' is not present in the current governance "
            f"output for scope '{scope_type}:{scope_id}'",
        )

    change_ids = [c["change_id"] for c in changes]

    # Conflict detection
    conflict_result = detect_proposal_conflicts(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
    )
    conflicts = conflict_result.get("conflicts", [])

    # Review states (used by staleness)
    review_states = _load_review_states(db, change_ids, tenant_id=tenant_id)

    # Staleness detection
    staleness_result = detect_proposal_staleness(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
        review_states=review_states,
        current_reasoning_categories=reasoning_categories,
        current_control_categories=control_categories,
        now=now,
    )
    staleness = staleness_result.get("staleness", [])

    # Simulation preview
    preview_result = compute_simulation_preview(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=control["suggestions"],
    )
    previews = preview_result.get("previews", [])

    # Approval readiness
    readiness_result = evaluate_proposal_approval_readiness(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
        review_states=review_states,
        conflicts=conflicts,
        staleness=staleness,
        reasoning_categories=reasoning_categories,
        control_categories=control_categories,
        simulation_previews=previews,
    )
    approval_readiness = readiness_result.get("approval_readiness", [])

    # Apply planning
    planning_result = compute_apply_planning(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
        approval_readiness=approval_readiness,
        conflicts=conflicts,
        staleness=staleness,
    )
    apply_plans = planning_result.get("apply_plans", [])

    # Extract per-change statuses
    readiness_entry = next(
        (r for r in approval_readiness if r["change_id"] == change_id), None
    )
    plan_entry = next(
        (p for p in apply_plans if p["change_id"] == change_id), None
    )
    staleness_entry = next(
        (s for s in staleness if s["change_id"] == change_id), None
    )

    # Conflict summary for this specific change
    change_conflicts = [
        c for c in conflicts if change_id in c.get("proposal_ids", [])
    ]
    has_high_conflict = any(c["severity"] == "high" for c in change_conflicts)
    has_medium_conflict = any(c["severity"] == "medium" for c in change_conflicts)

    approval_readiness_status: str = (
        readiness_entry["status"] if readiness_entry else "blocked"
    )
    apply_planning_status: str = (
        plan_entry["status"] if plan_entry else "blocked_from_planning"
    )
    staleness_status: str = (
        staleness_entry["status"] if staleness_entry else "unknown"
    )

    # Build attestation summary
    governance_valid = (
        approval_readiness_status == "approval_ready"
        and apply_planning_status == "planned"
        and not has_high_conflict
        and staleness_status in ("fresh", "aging")
    )

    if governance_valid:
        attestation_summary = (
            "Proposal remains governance-valid for approval and guarded apply intent."
        )
    else:
        reasons: list[str] = []
        if approval_readiness_status != "approval_ready":
            reasons.append(
                f"approval_readiness is '{approval_readiness_status}'"
            )
        if apply_planning_status != "planned":
            reasons.append(f"apply_planning is '{apply_planning_status}'")
        if has_high_conflict:
            reasons.append("proposal has a high-severity conflict")
        if staleness_status == "stale":
            reasons.append("proposal is stale")
        attestation_summary = (
            "Proposal is not governance-valid: " + "; ".join(reasons) + "."
        )

    return {
        "attestable": True,
        "change_id": change_id,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "approval_readiness_status": approval_readiness_status,
        "apply_planning_status": apply_planning_status,
        "conflict_status": {
            "has_high_conflict": has_high_conflict,
            "has_medium_conflict": has_medium_conflict,
        },
        "staleness_status": staleness_status,
        "attestation_summary": attestation_summary,
        "attested_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_review_states(
    db: Session,
    change_ids: list[str],
    *,
    tenant_id: str,
) -> dict[str, dict[str, Any]]:
    if not change_ids:
        return {}
    rows = (
        db.query(ProposedChangeReviewState)
        .filter(
            ProposedChangeReviewState.tenant_id == tenant_id,
            ProposedChangeReviewState.change_id.in_(change_ids),
        )
        .all()
    )
    return {
        r.change_id: {
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "persisted": True,
        }
        for r in rows
    }


def _unattestable(change_id: str, reason: str) -> dict[str, Any]:
    return {
        "attestable": False,
        "change_id": change_id,
        "scope_type": None,
        "scope_id": None,
        "approval_readiness_status": None,
        "apply_planning_status": None,
        "conflict_status": None,
        "staleness_status": None,
        "attestation_summary": reason,
        "attested_at": None,
    }
