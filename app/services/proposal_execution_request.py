"""
app/services/proposal_execution_request.py

Persistence logic for ProposedChangeExecutionRequest records.

Provides create/validate/block/cancel operations.  All functions operate
within the caller's DB session — they do NOT commit.  The caller is
responsible for committing (or rolling back) the transaction.

Design:
  - One record per (tenant_id, change_id) — upsert resets to requested.
  - Status machine: requested → validated | blocked; validated → blocked;
    {requested, validated, blocked} → cancelled.
  - Monitoring plans are deterministic and keyed by change_type.
  - No execution side effects.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.models.proposed_change_review_state import ProposedChangeReviewState

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Monitoring plan catalogue — deterministic, keyed by change_type
# ---------------------------------------------------------------------------

_MONITORING_PLANS: dict[str, dict[str, Any]] = {
    "threshold_adjustment": {
        "metrics_to_watch": ["failed_rate", "review_rate", "low_confidence_rate"],
        "rollback_triggers": [
            "failed_rate worsens by more than 5%",
            "review_rate spikes unexpectedly",
            "throughput drops below baseline",
        ],
        "observation_window_hours": 24,
    },
    "pricing_guardrail_adjustment": {
        "metrics_to_watch": ["win_rate", "underpricing_rate", "failed_rate"],
        "rollback_triggers": [
            "win_rate drops unexpectedly",
            "failed_rate worsens",
            "underpricing_rate drops sharply after change",
        ],
        "observation_window_hours": 48,
    },
    "validation_policy_adjustment": {
        "metrics_to_watch": ["failed_rate", "low_confidence_rate", "throughput"],
        "rollback_triggers": [
            "failed_rate worsens",
            "throughput drops more than 10%",
            "low_confidence_rate spikes sharply",
        ],
        "observation_window_hours": 24,
    },
    "fallback_policy_adjustment": {
        "metrics_to_watch": ["failed_rate", "fallback_rate", "review_rate"],
        "rollback_triggers": [
            "failed_rate worsens",
            "fallback_rate increases beyond baseline",
        ],
        "observation_window_hours": 24,
    },
    "review_trigger_adjustment": {
        "metrics_to_watch": ["review_rate", "failed_rate", "low_confidence_rate"],
        "rollback_triggers": [
            "review_rate drops sharply below target",
            "failed_rate worsens",
        ],
        "observation_window_hours": 24,
    },
}

_DEFAULT_MONITORING_PLAN: dict[str, Any] = {
    "metrics_to_watch": ["failed_rate", "review_rate", "low_confidence_rate"],
    "rollback_triggers": [
        "failed_rate worsens",
        "throughput drops below baseline",
    ],
    "observation_window_hours": 24,
}


def build_monitoring_plan(change_type: str) -> dict[str, Any]:
    """Return a deterministic monitoring plan for the given change_type."""
    base = _MONITORING_PLANS.get(change_type, _DEFAULT_MONITORING_PLAN)
    return {
        "change_type": change_type,
        **base,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Internal snapshot helpers
# ---------------------------------------------------------------------------


def _compact_governance_snapshot(attestation: dict[str, Any]) -> dict[str, Any]:
    conflict_status = attestation.get("conflict_status") or {}
    return {
        "attestable": attestation.get("attestable"),
        "approval_readiness_status": attestation.get("approval_readiness_status"),
        "apply_planning_status": attestation.get("apply_planning_status"),
        "staleness_status": attestation.get("staleness_status"),
        "has_high_conflict": conflict_status.get("has_high_conflict"),
        "has_medium_conflict": conflict_status.get("has_medium_conflict"),
        "attestation_summary": attestation.get("attestation_summary"),
        "attested_at": attestation.get("attested_at"),
    }


def _compact_apply_intent_snapshot(intent: ProposedChangeApplyIntent) -> dict[str, Any]:
    return {
        "id": intent.id,
        "status": intent.status,
        "change_type": intent.change_type,
        "has_apply_plan": intent.apply_plan_snapshot is not None,
        "has_preflight": intent.preflight_snapshot is not None,
        "has_rollback": intent.rollback_snapshot is not None,
        "created_at": intent.created_at.isoformat() if intent.created_at else None,
    }


# ---------------------------------------------------------------------------
# Service operations — all do NOT commit
# ---------------------------------------------------------------------------


def create_or_update_execution_request(
    db: Session,
    *,
    state: ProposedChangeReviewState,
    intent: ProposedChangeApplyIntent,
    attestation: dict[str, Any],
) -> ProposedChangeExecutionRequest:
    """
    Persist an execution request backed by an active apply intent.

    If a record already exists for (tenant_id, change_id) it is refreshed with
    current snapshots and reset to status=requested.  Otherwise a new record is
    created.

    Does NOT commit — caller owns the transaction.
    """
    governance_json = json.dumps(_compact_governance_snapshot(attestation))
    apply_intent_json = json.dumps(_compact_apply_intent_snapshot(intent))
    monitoring_json = json.dumps(build_monitoring_plan(state.change_type))
    # Pass apply_plan and preflight snapshots through from the intent
    execution_plan_json = intent.apply_plan_snapshot
    preflight_json = intent.preflight_snapshot

    existing = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.tenant_id == state.tenant_id,
            ProposedChangeExecutionRequest.change_id == state.change_id,
        )
        .first()
    )

    if existing is not None:
        existing.status = "requested"
        existing.apply_intent_id = intent.id
        existing.title = state.title
        existing.proposal_payload = state.proposal_payload
        existing.governance_snapshot = governance_json
        existing.apply_intent_snapshot = apply_intent_json
        existing.execution_plan_snapshot = execution_plan_json
        existing.preflight_snapshot = preflight_json
        existing.monitoring_plan_snapshot = monitoring_json
        existing.blocking_reasons_snapshot = None
        return existing

    req = ProposedChangeExecutionRequest(
        tenant_id=state.tenant_id,
        change_id=state.change_id,
        apply_intent_id=intent.id,
        scope_type=state.scope_type,
        scope_id=state.scope_id,
        status="requested",
        change_type=state.change_type,
        title=state.title,
        proposal_payload=state.proposal_payload,
        governance_snapshot=governance_json,
        apply_intent_snapshot=apply_intent_json,
        execution_plan_snapshot=execution_plan_json,
        preflight_snapshot=preflight_json,
        monitoring_plan_snapshot=monitoring_json,
        blocking_reasons_snapshot=None,
    )
    db.add(req)
    return req


def validate_execution_request(
    db: Session,
    *,
    request: ProposedChangeExecutionRequest,
    attestation: dict[str, Any],
) -> ProposedChangeExecutionRequest:
    """
    Transition an execution request from requested → validated.

    Refreshes the governance snapshot with the current attestation.
    Does NOT commit — caller owns the transaction.
    """
    request.status = "validated"
    request.governance_snapshot = json.dumps(_compact_governance_snapshot(attestation))
    request.blocking_reasons_snapshot = None
    return request


def block_execution_request(
    db: Session,
    *,
    request: ProposedChangeExecutionRequest,
    blocking_reasons: Optional[list[str]] = None,
) -> ProposedChangeExecutionRequest:
    """
    Transition an execution request to blocked.

    Captures optional blocking_reasons as a snapshot.
    Does NOT commit — caller owns the transaction.
    """
    request.status = "blocked"
    if blocking_reasons:
        request.blocking_reasons_snapshot = json.dumps({"reasons": blocking_reasons})
    return request


def cancel_execution_request(
    db: Session,
    *,
    request: ProposedChangeExecutionRequest,
) -> ProposedChangeExecutionRequest:
    """
    Transition an execution request to cancelled.

    Does NOT commit — caller owns the transaction.
    """
    request.status = "cancelled"
    return request
