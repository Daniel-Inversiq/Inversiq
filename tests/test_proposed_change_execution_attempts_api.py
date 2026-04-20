"""
tests/test_proposed_change_execution_attempts_api.py

Integration tests for the /api/proposed-change-execution-attempts endpoints.

Tests:
  - create attempt from validated execution request
  - create blocked when request not validated
  - create blocked when active attempt exists
  - start passes with clean preflight
  - start fails when preflight fails (request not validated)
  - complete transitions running -> succeeded
  - fail transitions running -> failed
  - cancel transitions queued -> cancelled
  - rollback transitions running -> rolled_back
  - rollback transitions failed -> rolled_back
  - invalid transitions rejected with 422
  - multiple attempts increment attempt_number
  - list endpoint returns attempts for tenant
  - get by change_id returns all attempts
  - tenant isolation
  - audit events written
  - preflight snapshot persisted
"""

from __future__ import annotations

import base64
import json

import pytest

from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_TENANT = "api_test_tenant_attempts"
_OTHER_TENANT = "api_test_tenant_other_attempts"


@pytest.fixture
def api_auth():
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _make_validated_request(
    db,
    *,
    tenant_id: str = _TENANT,
    change_id: str,
    status: str = "validated",
    execution_plan: str | None = '{"steps": []}',
    monitoring_plan: str | None = '{"metrics_to_watch": ["failed_rate"]}',
    governance: str | None = None,
    blocking_reasons: str | None = None,
) -> ProposedChangeExecutionRequest:
    if governance is None:
        governance = json.dumps({"attestable": True, "attestation_summary": "ok"})
    req = ProposedChangeExecutionRequest(
        tenant_id=tenant_id,
        change_id=change_id,
        scope_type="pipeline",
        scope_id="pipe1",
        status=status,
        change_type="threshold_adjustment",
        title="Test proposal",
        execution_plan_snapshot=execution_plan,
        monitoring_plan_snapshot=monitoring_plan,
        governance_snapshot=governance,
        blocking_reasons_snapshot=blocking_reasons,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_api_create_attempt_from_validated_request(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_create1:cat:p")
    resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "queued"
    assert data["attempt_number"] == 1
    assert data["execution_request_id"] == req.id
    assert data["tenant_id"] == _TENANT


def test_api_create_blocked_when_request_not_validated(client, db, api_auth):
    req = _make_validated_request(
        db, change_id="pipe:api_create_blk:cat:p", status="requested"
    )
    resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert resp.status_code == 422
    assert "validated" in resp.json()["detail"]


def test_api_create_blocked_when_active_attempt_exists(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_active:cat:p")
    # Create first attempt
    r1 = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert r1.status_code == 200

    # Second create should fail (active attempt exists)
    r2 = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert r2.status_code == 422
    assert "active" in r2.json()["detail"]


def test_api_create_not_found_when_request_missing(client, api_auth):
    resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": 999999},
        headers=api_auth,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


def test_api_start_transitions_to_running(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_start1:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    resp = client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "running"
    assert data["started_at"] is not None
    assert data["has_preflight_result"] is True
    preflight = data["preflight_result_snapshot"]
    assert preflight["passed"] is True


def test_api_start_fails_preflight_when_request_not_validated(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_startfail:cat:p", status="validated")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    # Flip request to blocked to make preflight fail
    req.status = "blocked"
    req.blocking_reasons_snapshot = json.dumps({"reasons": ["governance drifted"]})
    db.commit()

    resp = client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422
    assert "preflight" in resp.json()["detail"].lower()


def test_api_start_rejected_from_non_queued(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_startstate:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    # Start it (queued -> running)
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    # Try to start again (running -> running is invalid)
    resp = client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------


def test_api_complete_transitions_to_succeeded(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_complete1:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/complete",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "succeeded"
    assert data["has_execution_result"] is True
    assert data["completed_at"] is not None


def test_api_complete_accepts_custom_result(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_complete_custom:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    custom_result = {"outcome": "real_success", "applied_fields": ["confidence_threshold"]}
    resp = client.post(
        "/api/proposed-change-execution-attempts/complete",
        json={
            "tenant_id": _TENANT,
            "attempt_id": attempt_id,
            "execution_result_snapshot": custom_result,
        },
        headers=api_auth,
    )
    assert resp.status_code == 200
    result = resp.json()["execution_result_snapshot"]
    assert result["outcome"] == "real_success"


def test_api_complete_rejected_from_queued(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_complete_rej:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    resp = client.post(
        "/api/proposed-change-execution-attempts/complete",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# fail
# ---------------------------------------------------------------------------


def test_api_fail_transitions_to_failed(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_fail1:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/fail",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id, "failure_reason": "timeout"},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "failed"
    assert data["failure_reason"] == "timeout"


def test_api_fail_rejected_from_queued(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_fail_rej:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    resp = client.post(
        "/api/proposed-change-execution-attempts/fail",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


def test_api_cancel_transitions_to_cancelled(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_cancel1:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    resp = client.post(
        "/api/proposed-change-execution-attempts/cancel",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"


def test_api_cancel_rejected_from_running(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_cancel_rej:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/cancel",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


def test_api_rollback_from_running(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_rb_run:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/rollback",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rolled_back"
    assert resp.json()["has_rollback_snapshot"] is True


def test_api_rollback_from_failed(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_rb_fail:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    client.post(
        "/api/proposed-change-execution-attempts/fail",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/rollback",
        json={
            "tenant_id": _TENANT,
            "attempt_id": attempt_id,
            "rollback_snapshot": {"reason": "metric degraded"},
        },
        headers=api_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rolled_back"
    rb = resp.json()["rollback_snapshot"]
    assert rb["reason"] == "metric degraded"


def test_api_rollback_rejected_from_queued(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_rb_rej:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    resp = client.post(
        "/api/proposed-change-execution-attempts/rollback",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


def test_api_rollback_rejected_from_succeeded(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_rb_succ:cat:p")
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    client.post(
        "/api/proposed-change-execution-attempts/complete",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )

    resp = client.post(
        "/api/proposed-change-execution-attempts/rollback",
        json={"tenant_id": _TENANT, "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Multiple attempts
# ---------------------------------------------------------------------------


def test_api_multiple_attempts_increment_number(client, db, api_auth):
    req = _make_validated_request(db, change_id="pipe:api_multi:cat:p")

    # First attempt: create, cancel (so it's no longer active)
    r1 = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert r1.json()["attempt_number"] == 1
    client.post(
        "/api/proposed-change-execution-attempts/cancel",
        json={"tenant_id": _TENANT, "attempt_id": r1.json()["id"]},
        headers=api_auth,
    )

    # Second attempt
    r2 = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": _TENANT, "execution_request_id": req.id},
        headers=api_auth,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["attempt_number"] == 2


# ---------------------------------------------------------------------------
# List and get endpoints
# ---------------------------------------------------------------------------


def test_api_list_returns_attempts_for_tenant(client, db, api_auth):
    req = _make_validated_request(
        db, tenant_id="tenant_list_atts", change_id="pipe:api_list:cat:p"
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_list_atts", "execution_request_id": req.id},
        headers=api_auth,
    )

    resp = client.get(
        "/api/proposed-change-execution-attempts",
        params={"tenant_id": "tenant_list_atts"},
        headers=api_auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == "tenant_list_atts"
    assert data["total"] >= 1


def test_api_list_filters_by_execution_request_id(client, db, api_auth):
    req = _make_validated_request(
        db, tenant_id="tenant_list_filter", change_id="pipe:api_list_f:cat:p"
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_list_filter", "execution_request_id": req.id},
        headers=api_auth,
    )

    resp = client.get(
        "/api/proposed-change-execution-attempts",
        params={"tenant_id": "tenant_list_filter", "execution_request_id": req.id},
        headers=api_auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["execution_request_id"] == req.id for i in data["items"])


def test_api_get_by_change_id_returns_all_attempts(client, db, api_auth):
    req = _make_validated_request(
        db, tenant_id="tenant_get_cid", change_id="pipe:api_getcid:cat:p"
    )
    r1 = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_get_cid", "execution_request_id": req.id},
        headers=api_auth,
    )
    # Cancel first attempt so a second can be created
    client.post(
        "/api/proposed-change-execution-attempts/cancel",
        json={"tenant_id": "tenant_get_cid", "attempt_id": r1.json()["id"]},
        headers=api_auth,
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_get_cid", "execution_request_id": req.id},
        headers=api_auth,
    )

    resp = client.get(
        "/api/proposed-change-execution-attempts/pipe:api_getcid:cat:p",
        params={"tenant_id": "tenant_get_cid"},
        headers=api_auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["change_id"] == "pipe:api_getcid:cat:p"
    assert data["total"] == 2
    # Ordered by attempt_number ascending
    assert data["items"][0]["attempt_number"] == 1
    assert data["items"][1]["attempt_number"] == 2


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_api_tenant_isolation_on_list(client, db, api_auth):
    req_a = _make_validated_request(
        db, tenant_id="tenant_iso_a_att", change_id="pipe:iso_a:cat:p"
    )
    req_b = _make_validated_request(
        db, tenant_id="tenant_iso_b_att", change_id="pipe:iso_b:cat:p"
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_iso_a_att", "execution_request_id": req_a.id},
        headers=api_auth,
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_iso_b_att", "execution_request_id": req_b.id},
        headers=api_auth,
    )

    resp_a = client.get(
        "/api/proposed-change-execution-attempts",
        params={"tenant_id": "tenant_iso_a_att"},
        headers=api_auth,
    )
    resp_b = client.get(
        "/api/proposed-change-execution-attempts",
        params={"tenant_id": "tenant_iso_b_att"},
        headers=api_auth,
    )

    ids_a = {i["id"] for i in resp_a.json()["items"]}
    ids_b = {i["id"] for i in resp_b.json()["items"]}
    assert ids_a.isdisjoint(ids_b)


def test_api_tenant_isolation_on_action(client, db, api_auth):
    req = _make_validated_request(
        db, tenant_id="tenant_iso_owner", change_id="pipe:iso_owner:cat:p"
    )
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_iso_owner", "execution_request_id": req.id},
        headers=api_auth,
    )
    attempt_id = create_resp.json()["id"]

    # Attempt to cancel using wrong tenant
    resp = client.post(
        "/api/proposed-change-execution-attempts/cancel",
        json={"tenant_id": "tenant_iso_other", "attempt_id": attempt_id},
        headers=api_auth,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


def test_api_create_writes_audit_event(client, db, api_auth):
    from app.models.proposed_change_audit_event import ProposedChangeAuditEvent

    req = _make_validated_request(
        db, tenant_id="tenant_audit_att", change_id="pipe:audit_att:cat:p"
    )
    client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_audit_att", "execution_request_id": req.id},
        headers=api_auth,
    )

    events = (
        db.query(ProposedChangeAuditEvent)
        .filter(
            ProposedChangeAuditEvent.tenant_id == "tenant_audit_att",
            ProposedChangeAuditEvent.change_id == "pipe:audit_att:cat:p",
            ProposedChangeAuditEvent.event_type == "execution_attempt_created",
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].new_status == "queued"


def test_api_start_writes_audit_event(client, db, api_auth):
    from app.models.proposed_change_audit_event import ProposedChangeAuditEvent

    req = _make_validated_request(
        db, tenant_id="tenant_audit_start", change_id="pipe:audit_start:cat:p"
    )
    create_resp = client.post(
        "/api/proposed-change-execution-attempts/create",
        json={"tenant_id": "tenant_audit_start", "execution_request_id": req.id},
        headers=api_auth,
    )
    client.post(
        "/api/proposed-change-execution-attempts/start",
        json={"tenant_id": "tenant_audit_start", "attempt_id": create_resp.json()["id"]},
        headers=api_auth,
    )

    events = (
        db.query(ProposedChangeAuditEvent)
        .filter(
            ProposedChangeAuditEvent.tenant_id == "tenant_audit_start",
            ProposedChangeAuditEvent.event_type == "execution_attempt_started",
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].previous_status == "queued"
    assert events[0].new_status == "running"
