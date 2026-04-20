"""
tests/test_proposed_change_apply_intent.py

Unit tests for the ProposedChangeApplyIntent service layer.

Tests:
  - create_or_update_apply_intent creates a new record
  - create_or_update_apply_intent updates an existing cancelled record
  - cancel_apply_intent marks active intent as cancelled
  - cancel_apply_intent is a no-op if no active intent exists
  - governance snapshot is persisted correctly
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.proposal_apply_intent import (
    cancel_apply_intent,
    create_or_update_apply_intent,
)


def _make_state(**kwargs) -> ProposedChangeReviewState:
    defaults = dict(
        tenant_id="tenant_a",
        change_id="pipeline:pipe1:confidence_threshold_tuning:no_parameter",
        scope_type="pipeline",
        scope_id="pipe1",
        category="confidence_threshold_tuning",
        change_type="threshold_adjustment",
        title="Lower review confidence threshold",
        status="ready_for_apply",
        proposal_payload=None,
    )
    defaults.update(kwargs)
    state = MagicMock(spec=ProposedChangeReviewState)
    for k, v in defaults.items():
        setattr(state, k, v)
    return state


def _make_attestation(**kwargs) -> dict:
    defaults = {
        "attestable": True,
        "approval_readiness_status": "approval_ready",
        "apply_planning_status": "planned",
        "conflict_status": {"has_high_conflict": False, "has_medium_conflict": False},
        "staleness_status": "fresh",
        "attestation_summary": "governance valid",
        "attested_at": "2026-04-18T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# create_or_update_apply_intent — new record
# ---------------------------------------------------------------------------


def test_create_intent_adds_new_record(db):
    state = _make_state()
    attestation = _make_attestation()

    intent = create_or_update_apply_intent(db, state=state, attestation=attestation)
    db.commit()

    assert intent.id is not None
    assert intent.tenant_id == "tenant_a"
    assert intent.change_id == state.change_id
    assert intent.status == "ready_for_apply"
    assert intent.change_type == "threshold_adjustment"
    assert intent.scope_type == "pipeline"

    governance = json.loads(intent.governance_snapshot)
    assert governance["approval_readiness_status"] == "approval_ready"
    assert governance["apply_planning_status"] == "planned"
    assert governance["staleness_status"] == "fresh"
    assert governance["has_high_conflict"] is False
    assert governance["attested_at"] == "2026-04-18T00:00:00+00:00"


def test_create_intent_snapshots_proposal_payload(db):
    payload = json.dumps({"direction": "decrease", "delta": 0.05})
    state = _make_state(proposal_payload=payload)
    attestation = _make_attestation()

    intent = create_or_update_apply_intent(db, state=state, attestation=attestation)
    db.commit()

    assert intent.proposal_payload == payload


# ---------------------------------------------------------------------------
# create_or_update_apply_intent — update existing record
# ---------------------------------------------------------------------------


def test_update_intent_reactivates_cancelled_record(db):
    state = _make_state()
    attest1 = _make_attestation(attested_at="2026-04-17T00:00:00+00:00")

    intent = create_or_update_apply_intent(db, state=state, attestation=attest1)
    db.commit()
    intent.status = "cancelled"
    db.commit()

    assert intent.status == "cancelled"

    attest2 = _make_attestation(attested_at="2026-04-18T00:00:00+00:00")
    updated = create_or_update_apply_intent(db, state=state, attestation=attest2)
    db.commit()

    assert updated.id == intent.id
    assert updated.status == "ready_for_apply"
    gov = json.loads(updated.governance_snapshot)
    assert gov["attested_at"] == "2026-04-18T00:00:00+00:00"


# ---------------------------------------------------------------------------
# cancel_apply_intent
# ---------------------------------------------------------------------------


def test_cancel_intent_marks_as_cancelled(db):
    state = _make_state()
    attestation = _make_attestation()

    create_or_update_apply_intent(db, state=state, attestation=attestation)
    db.commit()

    result = cancel_apply_intent(db, state=state)
    db.commit()

    assert result is not None
    assert result.status == "cancelled"


def test_cancel_intent_returns_none_when_no_active_intent(db):
    state = _make_state(change_id="pipeline:nonexistent:cat:param")
    result = cancel_apply_intent(db, state=state)
    assert result is None


def test_cancel_intent_does_not_cancel_already_cancelled(db):
    state = _make_state(
        change_id="pipeline:pipe_cancel_test:cat:param",
        tenant_id="tenant_cancel",
    )
    create_or_update_apply_intent(db, state=state, attestation=_make_attestation())
    db.commit()

    cancel_apply_intent(db, state=state)
    db.commit()

    # Second cancel attempt — no active intent to cancel
    result = cancel_apply_intent(db, state=state)
    assert result is None


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_intents_are_tenant_isolated(db):
    change_id = "pipeline:shared_scope:cat:param"
    state_a = _make_state(tenant_id="tenant_iso_a", change_id=change_id)
    state_b = _make_state(tenant_id="tenant_iso_b", change_id=change_id)

    intent_a = create_or_update_apply_intent(
        db, state=state_a, attestation=_make_attestation()
    )
    intent_b = create_or_update_apply_intent(
        db, state=state_b, attestation=_make_attestation()
    )
    db.commit()

    assert intent_a.id != intent_b.id
    assert intent_a.tenant_id == "tenant_iso_a"
    assert intent_b.tenant_id == "tenant_iso_b"

    # Cancelling tenant_a's intent should not affect tenant_b's
    cancel_apply_intent(db, state=state_a)
    db.commit()

    db.refresh(intent_b)
    assert intent_b.status == "ready_for_apply"
