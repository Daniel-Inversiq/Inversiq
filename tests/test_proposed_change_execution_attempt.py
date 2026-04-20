"""
tests/test_proposed_change_execution_attempt.py

Unit tests for the proposal_execution_runner service layer.

Tests:
  - create_execution_attempt creates a new queued record
  - attempt_number auto-increments across multiple attempts
  - run_preflight_checks returns correct structure
  - run_preflight_checks fails when request not validated
  - run_preflight_checks fails when blocking reasons present
  - run_preflight_checks fails when governance not attestable
  - run_preflight_checks fails when execution plan absent
  - run_preflight_checks fails when monitoring plan absent
  - start_execution_attempt transitions queued -> running
  - complete_execution_attempt transitions running -> succeeded
  - fail_execution_attempt transitions running -> failed
  - cancel_execution_attempt transitions queued -> cancelled
  - rollback_execution_attempt transitions running -> rolled_back
  - rollback_execution_attempt transitions failed -> rolled_back
  - _assert_transition rejects invalid transitions
  - preflight snapshot persisted on start
  - execution result snapshot persisted on complete
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.models.proposed_change_execution_attempt import ProposedChangeExecutionAttempt
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.services.proposal_execution_runner import (
    _assert_transition,
    cancel_execution_attempt,
    complete_execution_attempt,
    create_execution_attempt,
    fail_execution_attempt,
    fail_preflight,
    rollback_execution_attempt,
    run_preflight_checks,
    start_execution_attempt,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_UNSET = object()


def _make_request(
    *,
    id_: int = 1,
    tenant_id: str = "tenant_a",
    change_id: str = "pipeline:pipe1:cat:param",
    status: str = "validated",
    execution_plan_snapshot: str | None = '{"steps": []}',
    monitoring_plan_snapshot: str | None = '{"metrics_to_watch": ["failed_rate"]}',
    blocking_reasons_snapshot: str | None = None,
    governance_snapshot: object = _UNSET,
) -> MagicMock:
    if governance_snapshot is _UNSET:
        governance_snapshot = json.dumps({"attestable": True, "attestation_summary": "ok"})
    req = MagicMock(spec=ProposedChangeExecutionRequest)
    req.id = id_
    req.tenant_id = tenant_id
    req.change_id = change_id
    req.scope_type = "pipeline"
    req.scope_id = "pipe1"
    req.status = status
    req.execution_plan_snapshot = execution_plan_snapshot
    req.monitoring_plan_snapshot = monitoring_plan_snapshot
    req.blocking_reasons_snapshot = blocking_reasons_snapshot
    req.governance_snapshot = governance_snapshot
    return req


def _make_attempt(
    *,
    id_: int = 1,
    tenant_id: str = "tenant_a",
    execution_request_id: int = 1,
    change_id: str = "pipeline:pipe1:cat:param",
    status: str = "queued",
    attempt_number: int = 1,
) -> ProposedChangeExecutionAttempt:
    attempt = ProposedChangeExecutionAttempt(
        id=id_,
        tenant_id=tenant_id,
        execution_request_id=execution_request_id,
        change_id=change_id,
        scope_type="pipeline",
        scope_id="pipe1",
        status=status,
        attempt_number=attempt_number,
    )
    return attempt


# ---------------------------------------------------------------------------
# create_execution_attempt
# ---------------------------------------------------------------------------


def test_create_attempt_new_record(db):
    req = _make_request(id_=100, tenant_id="tenant_create1", change_id="pipe:c1:cat:p")
    # Persist a real execution request for the FK logic
    real_req = ProposedChangeExecutionRequest(
        id=100,
        tenant_id="tenant_create1",
        change_id="pipe:c1:cat:p",
        scope_type="pipeline",
        scope_id="pipe1",
        status="validated",
        change_type="threshold_adjustment",
        title="Test",
    )
    db.add(real_req)
    db.commit()

    attempt = create_execution_attempt(db, request=real_req)
    db.commit()

    assert attempt.id is not None
    assert attempt.status == "queued"
    assert attempt.attempt_number == 1
    assert attempt.execution_request_id == real_req.id
    assert attempt.tenant_id == "tenant_create1"


def test_create_attempt_increments_attempt_number(db):
    real_req = ProposedChangeExecutionRequest(
        tenant_id="tenant_create2",
        change_id="pipe:c2:cat:p",
        scope_type="pipeline",
        scope_id="pipe1",
        status="validated",
        change_type="threshold_adjustment",
        title="Test",
    )
    db.add(real_req)
    db.commit()

    attempt1 = create_execution_attempt(db, request=real_req)
    db.commit()
    assert attempt1.attempt_number == 1

    attempt2 = create_execution_attempt(db, request=real_req)
    db.commit()
    assert attempt2.attempt_number == 2

    attempt3 = create_execution_attempt(db, request=real_req)
    db.commit()
    assert attempt3.attempt_number == 3


# ---------------------------------------------------------------------------
# run_preflight_checks
# ---------------------------------------------------------------------------


def test_preflight_passes_with_clean_request():
    req = _make_request()
    result = run_preflight_checks(req)
    assert result["passed"] is True
    assert result["summary"] == "All preflight checks passed."
    assert len(result["checks"]) == 5
    assert all(c["passed"] for c in result["checks"])
    assert "evaluated_at" in result


def test_preflight_fails_when_not_validated():
    req = _make_request(status="requested")
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "request_validated" in names


def test_preflight_fails_when_blocking_reasons_present():
    req = _make_request(
        blocking_reasons_snapshot=json.dumps({"reasons": ["governance drifted"]})
    )
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "has_no_blocking_reasons" in names


def test_preflight_fails_when_governance_not_attestable():
    req = _make_request(
        governance_snapshot=json.dumps({"attestable": False, "attestation_summary": "drift"})
    )
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "governance_attestable" in names


def test_preflight_fails_when_execution_plan_absent():
    req = _make_request(execution_plan_snapshot=None)
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "has_execution_plan" in names


def test_preflight_fails_when_monitoring_plan_absent():
    req = _make_request(monitoring_plan_snapshot=None)
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "has_monitoring_plan" in names


def test_preflight_fails_when_governance_snapshot_absent():
    req = _make_request(governance_snapshot=None)
    result = run_preflight_checks(req)
    assert result["passed"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "governance_attestable" in names


# ---------------------------------------------------------------------------
# State transitions — service layer
# ---------------------------------------------------------------------------


def test_start_transitions_queued_to_running(db):
    attempt = _make_attempt(status="queued")
    preflight = {"passed": True, "checks": [], "summary": "ok", "evaluated_at": "now"}
    start_execution_attempt(db, attempt=attempt, preflight_result=preflight)
    assert attempt.status == "running"
    assert attempt.started_at is not None
    assert json.loads(attempt.preflight_result_snapshot)["passed"] is True


def test_complete_transitions_running_to_succeeded(db):
    attempt = _make_attempt(status="running")
    complete_execution_attempt(db, attempt=attempt)
    assert attempt.status == "succeeded"
    assert attempt.completed_at is not None
    result = json.loads(attempt.execution_result_snapshot)
    assert result["outcome"] == "stub_success"


def test_complete_accepts_custom_result(db):
    attempt = _make_attempt(status="running")
    custom = {"outcome": "real_success", "applied": True}
    complete_execution_attempt(db, attempt=attempt, execution_result=custom)
    assert attempt.status == "succeeded"
    stored = json.loads(attempt.execution_result_snapshot)
    assert stored["outcome"] == "real_success"


def test_fail_transitions_running_to_failed(db):
    attempt = _make_attempt(status="running")
    fail_execution_attempt(db, attempt=attempt, failure_reason="timeout")
    assert attempt.status == "failed"
    assert attempt.failure_reason == "timeout"
    assert attempt.completed_at is not None


def test_fail_default_reason(db):
    attempt = _make_attempt(status="running")
    fail_execution_attempt(db, attempt=attempt)
    assert attempt.failure_reason == "Execution failed."


def test_cancel_transitions_queued_to_cancelled(db):
    attempt = _make_attempt(status="queued")
    cancel_execution_attempt(db, attempt=attempt)
    assert attempt.status == "cancelled"
    assert attempt.completed_at is not None


def test_rollback_transitions_running_to_rolled_back(db):
    attempt = _make_attempt(status="running")
    rollback_execution_attempt(db, attempt=attempt)
    assert attempt.status == "rolled_back"
    assert attempt.rollback_snapshot is not None


def test_rollback_transitions_failed_to_rolled_back(db):
    attempt = _make_attempt(status="failed")
    rollback_execution_attempt(db, attempt=attempt, rollback_snapshot={"note": "manual"})
    assert attempt.status == "rolled_back"
    stored = json.loads(attempt.rollback_snapshot)
    assert stored["note"] == "manual"


def test_fail_preflight_transitions_queued_to_failed(db):
    attempt = _make_attempt(status="queued")
    preflight = {"passed": False, "checks": [], "summary": "Preflight failed: X.", "evaluated_at": "now"}
    fail_preflight(db, attempt=attempt, preflight_result=preflight)
    assert attempt.status == "failed"
    assert "Preflight failed" in attempt.failure_reason


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


def test_assert_transition_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        _assert_transition("succeeded", "running")


def test_assert_transition_rejects_cancel_from_running():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        _assert_transition("running", "cancelled")


def test_assert_transition_rejects_complete_from_queued():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        _assert_transition("queued", "succeeded")


def test_assert_transition_rejects_rollback_from_queued():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        _assert_transition("queued", "rolled_back")


def test_assert_transition_rejects_start_from_succeeded():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        _assert_transition("succeeded", "running")
