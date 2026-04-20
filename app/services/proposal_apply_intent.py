"""
app/services/proposal_apply_intent.py

Persistence logic for ProposedChangeApplyIntent records.

Provides create/update and cancel operations. All functions operate within
the caller's DB session — they do NOT commit. The caller is responsible for
committing (or rolling back) the transaction.

Design:
  - One active record per (tenant_id, change_id).
  - mark-ready-for-apply → create or reactivate record with status=ready_for_apply.
  - cancel-ready-for-apply → mark existing active record as cancelled.
  - Snapshots are captured deterministically from the state and attestation
    objects that are already in scope at transition time.
  - No execution side effects.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_review_state import ProposedChangeReviewState

_log = logging.getLogger(__name__)


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


def create_or_update_apply_intent(
    db: Session,
    *,
    state: ProposedChangeReviewState,
    attestation: dict[str, Any],
) -> ProposedChangeApplyIntent:
    """
    Persist an apply intent for a proposal entering ready_for_apply.

    If a record already exists for (tenant_id, change_id), it is reactivated
    with a fresh governance snapshot. Otherwise a new record is created.

    Does NOT commit — caller owns the transaction.
    """
    existing = (
        db.query(ProposedChangeApplyIntent)
        .filter(
            ProposedChangeApplyIntent.tenant_id == state.tenant_id,
            ProposedChangeApplyIntent.change_id == state.change_id,
        )
        .first()
    )

    governance_json = json.dumps(_compact_governance_snapshot(attestation))

    if existing is not None:
        existing.status = "ready_for_apply"
        existing.governance_snapshot = governance_json
        existing.title = state.title
        existing.proposal_payload = state.proposal_payload
        return existing

    intent = ProposedChangeApplyIntent(
        tenant_id=state.tenant_id,
        change_id=state.change_id,
        scope_type=state.scope_type,
        scope_id=state.scope_id,
        status="ready_for_apply",
        change_type=state.change_type,
        title=state.title,
        proposal_payload=state.proposal_payload,
        governance_snapshot=governance_json,
        apply_plan_snapshot=None,
        preflight_snapshot=None,
        rollback_snapshot=None,
    )
    db.add(intent)
    return intent


def cancel_apply_intent(
    db: Session,
    *,
    state: ProposedChangeReviewState,
) -> Optional[ProposedChangeApplyIntent]:
    """
    Mark the active apply intent for a proposal as cancelled.

    Returns the updated record, or None if no active intent exists.
    Does NOT commit — caller owns the transaction.
    """
    existing = (
        db.query(ProposedChangeApplyIntent)
        .filter(
            ProposedChangeApplyIntent.tenant_id == state.tenant_id,
            ProposedChangeApplyIntent.change_id == state.change_id,
            ProposedChangeApplyIntent.status == "ready_for_apply",
        )
        .first()
    )

    if existing is None:
        _log.warning(
            "cancel_apply_intent: no active intent found for change_id=%s tenant_id=%s",
            state.change_id,
            state.tenant_id,
        )
        return None

    existing.status = "cancelled"
    return existing
