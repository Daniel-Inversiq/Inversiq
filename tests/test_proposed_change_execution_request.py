"""
tests/test_proposed_change_execution_request.py

Unit tests for the proposal_execution_request service layer.

Tests:
  - create_or_update_execution_request creates a new record
  - create_or_update_execution_request refreshes an existing record
  - validate_execution_request transitions to validated
  - block_execution_request transitions to blocked with reasons
  - cancel_execution_request transitions to cancelled
  - build_monitoring_plan returns correct structure per change_type
  - snapshot fields are persisted correctly
  - tenant isolation
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.models.proposed_change_review_state import ProposedChangeReviewState
from app.services.proposal_execution_request import (
    block_execution_request,
    build_monitoring_plan,
    cancel_execution_request,
    create_or_update_execution_request,
    validate_execution_request,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


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


def _make_intent(id_: int = 1, **kwargs) -> ProposedChangeApplyIntent:
    defaults = dict(
        id=id_,
        tenant_id="tenant_a",
        change_id="pipeline:pipe1:confidence_threshold_tuning:no_parameter",
        scope_type="pipeline",
        scope_id="pipe1",
        status="ready_for_apply",
        change_type="threshold_adjustment",
        title="Lower review confidence threshold",
        apply_plan_snapshot=None,
        preflight_snapshot=None,
        rollback_snapshot=None,
        created_at=None,
    )
    defaults.update(kwargs)
    intent = MagicMock(spec=ProposedChangeApplyIntent)
    for k, v in defaults.items():
        setattr(intent, k, v)
    return intent


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
# create_or_update_execution_request — new record
# ---------------------------------------------------------------------------


def test_create_new_execution_request(db):
    state = _make_state()
    intent = _make_intent()
    attestation = _make_attestation()

    req = create_or_update_execution_request(db, state=state, intent=intent, attestation=attestation)
    db.commit()

    assert req.id is not None
    assert req.tenant_id == "tenant_a"
    assert req.change_id == state.change_id
    assert req.status == "requested"
    assert req.apply_intent_id == 1
    assert req.scope_type == "pipeline"
    assert req.scope_id == "pipe1"
    assert req.change_type == "threshold_adjustment"


def test_create_persists_governance_snapshot(db):
    state = _make_state(change_id="pipeline:pipe_gov:cat:param")
    intent = _make_intent()
    attestation = _make_attestation()

    req = create_or_update_execution_request(db, state=state, intent=intent, attestation=attestation)
    db.commit()

    gov = json.loads(req.governance_snapshot)
    assert gov["approval_readiness_status"] == "approval_ready"
    assert gov["apply_planning_status"] == "planned"
    assert gov["has_high_conflict"] is False
    assert gov["attested_at"] == "2026-04-18T00:00:00+00:00"


def test_create_persists_monitoring_plan(db):
    state = _make_state(change_id="pipeline:pipe_mon:cat:param")
    intent = _make_intent()
    attestation = _make_attestation()

    req = create_or_update_execution_request(db, state=state, intent=intent, attestation=attestation)
    db.commit()

    plan = json.loads(req.monitoring_plan_snapshot)
    assert plan["change_type"] == "threshold_adjustment"
    assert "metrics_to_watch" in plan
    assert "rollback_triggers" in plan
    assert plan["observation_window_hours"] == 24


def test_create_passes_through_apply_plan_snapshot(db):
    apply_plan = json.dumps({"steps": ["step1"], "status": "planned"})
    preflight = json.dumps({"checks": ["check1"]})
    intent = _make_intent(apply_plan_snapshot=apply_plan, preflight_snapshot=preflight)
    state = _make_state(change_id="pipeline:pipe_plan:cat:param")

    req = create_or_update_execution_request(db, state=state, intent=intent, attestation=_make_attestation())
    db.commit()

    assert req.execution_plan_snapshot == apply_plan
    assert req.preflight_snapshot == preflight


# ---------------------------------------------------------------------------
# create_or_update_execution_request — update existing record
# ---------------------------------------------------------------------------


def test_update_refreshes_existing_record(db):
    cid = "pipeline:pipe_refresh:cat:param"
    state = _make_state(change_id=cid)
    intent1 = _make_intent(id_=10)
    attest1 = _make_attestation(attested_at="2026-04-17T00:00:00+00:00")

    req = create_or_update_execution_request(db, state=state, intent=intent1, attestation=attest1)
    db.commit()
    first_id = req.id

    # Simulate re-creation (e.g., after cancel + re-activate)
    intent2 = _make_intent(id_=20)
    attest2 = _make_attestation(attested_at="2026-04-18T00:00:00+00:00")
    updated = create_or_update_execution_request(db, state=state, intent=intent2, attestation=attest2)
    db.commit()

    assert updated.id == first_id
    assert updated.status == "requested"
    assert updated.apply_intent_id == 20
    gov = json.loads(updated.governance_snapshot)
    assert gov["attested_at"] == "2026-04-18T00:00:00+00:00"
    assert updated.blocking_reasons_snapshot is None


# ---------------------------------------------------------------------------
# validate_execution_request
# ---------------------------------------------------------------------------


def test_validate_transitions_to_validated(db):
    state = _make_state(change_id="pipeline:pipe_val:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    assert req.status == "requested"
    validate_execution_request(db, request=req, attestation=_make_attestation())
    db.commit()

    assert req.status == "validated"
    assert req.blocking_reasons_snapshot is None


def test_validate_updates_governance_snapshot(db):
    cid = "pipeline:pipe_val_gov:cat:param"
    state = _make_state(change_id=cid)
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation(attested_at="old"))
    db.commit()

    validate_execution_request(db, request=req, attestation=_make_attestation(attested_at="new"))
    db.commit()

    gov = json.loads(req.governance_snapshot)
    assert gov["attested_at"] == "new"


# ---------------------------------------------------------------------------
# block_execution_request
# ---------------------------------------------------------------------------


def test_block_transitions_to_blocked(db):
    state = _make_state(change_id="pipeline:pipe_blk:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    block_execution_request(db, request=req, blocking_reasons=["approval_readiness is 'blocked'"])
    db.commit()

    assert req.status == "blocked"
    reasons = json.loads(req.blocking_reasons_snapshot)
    assert reasons["reasons"] == ["approval_readiness is 'blocked'"]


def test_block_without_reasons(db):
    state = _make_state(change_id="pipeline:pipe_blk2:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    block_execution_request(db, request=req)
    db.commit()

    assert req.status == "blocked"


def test_block_from_validated(db):
    state = _make_state(change_id="pipeline:pipe_blk3:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    validate_execution_request(db, request=req, attestation=_make_attestation())
    db.commit()
    assert req.status == "validated"

    block_execution_request(db, request=req, blocking_reasons=["governance drifted"])
    db.commit()
    assert req.status == "blocked"


# ---------------------------------------------------------------------------
# cancel_execution_request
# ---------------------------------------------------------------------------


def test_cancel_from_requested(db):
    state = _make_state(change_id="pipeline:pipe_cnl:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    cancel_execution_request(db, request=req)
    db.commit()

    assert req.status == "cancelled"


def test_cancel_from_validated(db):
    state = _make_state(change_id="pipeline:pipe_cnl2:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()
    validate_execution_request(db, request=req, attestation=_make_attestation())
    db.commit()

    cancel_execution_request(db, request=req)
    db.commit()
    assert req.status == "cancelled"


def test_cancel_from_blocked(db):
    state = _make_state(change_id="pipeline:pipe_cnl3:cat:param")
    req = create_or_update_execution_request(db, state=state, intent=_make_intent(), attestation=_make_attestation())
    db.commit()
    block_execution_request(db, request=req)
    db.commit()

    cancel_execution_request(db, request=req)
    db.commit()
    assert req.status == "cancelled"


# ---------------------------------------------------------------------------
# build_monitoring_plan
# ---------------------------------------------------------------------------


def test_monitoring_plan_threshold_adjustment():
    plan = build_monitoring_plan("threshold_adjustment")
    assert plan["change_type"] == "threshold_adjustment"
    assert "failed_rate" in plan["metrics_to_watch"]
    assert "review_rate" in plan["metrics_to_watch"]
    assert len(plan["rollback_triggers"]) > 0
    assert plan["observation_window_hours"] == 24
    assert "generated_at" in plan


def test_monitoring_plan_pricing_guardrail():
    plan = build_monitoring_plan("pricing_guardrail_adjustment")
    assert "win_rate" in plan["metrics_to_watch"]
    assert plan["observation_window_hours"] == 48


def test_monitoring_plan_unknown_change_type():
    plan = build_monitoring_plan("unknown_type")
    assert plan["change_type"] == "unknown_type"
    assert "failed_rate" in plan["metrics_to_watch"]
    assert "generated_at" in plan


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_execution_requests_are_tenant_isolated(db):
    change_id = "pipeline:shared:cat:param"
    state_a = _make_state(tenant_id="tenant_iso_a", change_id=change_id)
    state_b = _make_state(tenant_id="tenant_iso_b", change_id=change_id)

    req_a = create_or_update_execution_request(db, state=state_a, intent=_make_intent(), attestation=_make_attestation())
    req_b = create_or_update_execution_request(db, state=state_b, intent=_make_intent(), attestation=_make_attestation())
    db.commit()

    assert req_a.id != req_b.id
    assert req_a.tenant_id == "tenant_iso_a"
    assert req_b.tenant_id == "tenant_iso_b"

    cancel_execution_request(db, request=req_a)
    db.commit()

    db.refresh(req_b)
    assert req_b.status == "requested"
