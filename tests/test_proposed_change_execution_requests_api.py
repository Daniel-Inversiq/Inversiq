"""
tests/test_proposed_change_execution_requests_api.py

Integration tests for:
  POST /api/proposed-change-execution-requests/create
  POST /api/proposed-change-execution-requests/validate
  POST /api/proposed-change-execution-requests/block
  POST /api/proposed-change-execution-requests/cancel
  GET  /api/proposed-change-execution-requests
  GET  /api/proposed-change-execution-requests/{change_id}
"""

from __future__ import annotations

import base64
import uuid
from typing import Any
from unittest.mock import patch

import pytest

EXEC_URL = "/api/proposed-change-execution-requests"
ACTIONS_URL = "/api/proposed-change-actions"
STATE_URL = "/api/proposed-change-state"
AUDIT_URL = "/api/proposed-change-audit"

_ATTEST_MODULE = "app.routers.proposed_change_actions.compute_governance_attestation"
_EXEC_ATTEST_MODULE = "app.routers.proposed_change_execution_requests.compute_governance_attestation"


@pytest.fixture
def api_auth():
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _cid(prefix: str = "pipe") -> str:
    return f"pipeline:{prefix}_{_uid()}:confidence_threshold_tuning:no_parameter"


def _state_payload(tenant_id: str, change_id: str, **overrides) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "change_id": change_id,
        "scope_type": "pipeline",
        "scope_id": "test_pipe",
        "category": "confidence_threshold_tuning",
        "change_type": "threshold_adjustment",
        "title": "Lower review confidence threshold",
        "status": "pending",
        "note": None,
        "proposal_payload": None,
    }
    defaults.update(overrides)
    return defaults


def _attest_ok(change_id: str = "") -> dict[str, Any]:
    return {
        "attestable": True,
        "change_id": change_id,
        "scope_type": "pipeline",
        "scope_id": "test_pipe",
        "approval_readiness_status": "approval_ready",
        "apply_planning_status": "planned",
        "conflict_status": {"has_high_conflict": False, "has_medium_conflict": False},
        "staleness_status": "fresh",
        "attestation_summary": "governance valid",
        "attested_at": "2026-04-18T00:00:00+00:00",
    }


def _attest_blocked(change_id: str = "") -> dict[str, Any]:
    return {
        "attestable": True,
        "change_id": change_id,
        "scope_type": "pipeline",
        "scope_id": "test_pipe",
        "approval_readiness_status": "blocked",
        "apply_planning_status": "blocked_from_planning",
        "conflict_status": {"has_high_conflict": True, "has_medium_conflict": False},
        "staleness_status": "stale",
        "attestation_summary": "governance invalid",
        "attested_at": "2026-04-18T00:00:00+00:00",
    }


def _advance_to_ready(client, api_auth, tenant_id: str, change_id: str) -> None:
    """Create state, approve, and mark ready_for_apply."""
    resp = client.post(STATE_URL, json=_state_payload(tenant_id, change_id), headers=api_auth)
    assert resp.status_code == 200, resp.text

    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text

    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text


def _create_exec_request(client, api_auth, tenant_id: str, change_id: str) -> dict[str, Any]:
    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{EXEC_URL}/create",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_succeeds_when_ready_for_apply(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    data = _create_exec_request(client, api_auth, tid, cid)

    assert data["change_id"] == cid
    assert data["tenant_id"] == tid
    assert data["status"] == "requested"
    assert data["change_type"] == "threshold_adjustment"
    assert data["governance_snapshot"] is not None
    assert data["governance_snapshot"]["apply_planning_status"] == "planned"
    assert data["has_monitoring_plan"] is True


def test_create_fails_when_not_ready_for_apply(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    # Only create state in pending — do not advance
    client.post(STATE_URL, json=_state_payload(tid, cid), headers=api_auth)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        resp = client.post(
            f"{EXEC_URL}/create",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 422
    assert "ready_for_apply" in resp.json()["detail"]


def test_create_fails_when_no_apply_intent(client, api_auth):
    """State exists and is ready_for_apply but no intent (should not happen in
    normal flow, covered defensively via the intent loader)."""
    tid = f"tenant_{_uid()}"
    cid = _cid()

    # Advance state to ready_for_apply
    _advance_to_ready(client, api_auth, tid, cid)

    # Cancel the apply intent so it no longer has status=ready_for_apply
    with patch(_ATTEST_MODULE, return_value=_attest_ok(cid)):
        client.post(
            f"{ACTIONS_URL}/cancel-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )

    # Now state is back to 'approved' — create should fail with 422
    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        resp = client.post(
            f"{EXEC_URL}/create",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 422


def test_create_fails_when_governance_not_clean(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_blocked(cid)):
        resp = client.post(
            f"{EXEC_URL}/create",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 422
    assert "governance" in resp.json()["detail"].lower()


def test_create_refreshes_existing_request(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    first = _create_exec_request(client, api_auth, tid, cid)

    # Create again — should refresh, not error
    second = _create_exec_request(client, api_auth, tid, cid)
    assert second["id"] == first["id"]
    assert second["status"] == "requested"


def test_create_writes_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_request_created" in event_types


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_moves_requested_to_validated(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        resp = client.post(
            f"{EXEC_URL}/validate",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "validated"


def test_validate_blocks_when_governance_drifted(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_blocked(cid)):
        resp = client.post(
            f"{EXEC_URL}/validate",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "blocked"
    assert data["blocking_reasons_snapshot"] is not None


def test_validate_fails_when_status_not_requested(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    # Cancel it first
    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        resp = client.post(
            f"{EXEC_URL}/validate",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
    assert resp.status_code == 422
    assert "requested" in resp.json()["detail"]


def test_validate_writes_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        client.post(f"{EXEC_URL}/validate", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_request_validated" in event_types


# ---------------------------------------------------------------------------
# block
# ---------------------------------------------------------------------------


def test_block_from_requested(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    resp = client.post(
        f"{EXEC_URL}/block",
        json={"tenant_id": tid, "change_id": cid, "blocking_reasons": ["manual hold"]},
        headers=api_auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "blocked"
    assert data["blocking_reasons_snapshot"]["reasons"] == ["manual hold"]


def test_block_from_validated(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        client.post(f"{EXEC_URL}/validate", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.post(
        f"{EXEC_URL}/block",
        json={"tenant_id": tid, "change_id": cid, "blocking_reasons": ["late blocker"]},
        headers=api_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


def test_block_fails_from_cancelled(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)
    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.post(
        f"{EXEC_URL}/block",
        json={"tenant_id": tid, "change_id": cid},
        headers=api_auth,
    )
    assert resp.status_code == 422


def test_block_writes_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)
    client.post(f"{EXEC_URL}/block", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_request_blocked" in event_types


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


def test_cancel_from_requested(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    resp = client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_from_validated(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(cid)):
        client.post(f"{EXEC_URL}/validate", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_from_blocked(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)
    client.post(f"{EXEC_URL}/block", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_fails_when_already_cancelled(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)
    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
    assert resp.status_code == 422


def test_cancel_writes_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)
    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_request_cancelled" in event_types


# ---------------------------------------------------------------------------
# list endpoint
# ---------------------------------------------------------------------------


def test_list_execution_requests(client, api_auth):
    tid = f"tenant_list_{_uid()}"
    cids = [_cid("list") for _ in range(3)]

    for cid in cids:
        _advance_to_ready(client, api_auth, tid, cid)
        _create_exec_request(client, api_auth, tid, cid)

    resp = client.get(f"{EXEC_URL}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tid
    assert data["total"] == 3
    returned_ids = {i["change_id"] for i in data["items"]}
    for cid in cids:
        assert cid in returned_ids


def test_list_filter_by_status(client, api_auth):
    tid = f"tenant_flt_{_uid()}"
    cid_active = _cid("active")
    cid_cancelled = _cid("cancelled")

    for cid in (cid_active, cid_cancelled):
        _advance_to_ready(client, api_auth, tid, cid)
        _create_exec_request(client, api_auth, tid, cid)

    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid, "change_id": cid_cancelled}, headers=api_auth)

    resp = client.get(f"{EXEC_URL}?tenant_id={tid}&status=requested", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["change_id"] == cid_active


# ---------------------------------------------------------------------------
# get endpoint
# ---------------------------------------------------------------------------


def test_get_execution_request_returns_snapshots(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _advance_to_ready(client, api_auth, tid, cid)
    _create_exec_request(client, api_auth, tid, cid)

    resp = client.get(f"{EXEC_URL}/{cid}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["change_id"] == cid
    assert "monitoring_plan_snapshot" in data
    assert data["monitoring_plan_snapshot"] is not None
    assert data["monitoring_plan_snapshot"]["change_type"] == "threshold_adjustment"


def test_get_execution_request_not_found(client, api_auth):
    resp = client.get(
        f"{EXEC_URL}/pipeline:nonexistent:cat:param?tenant_id=nobody",
        headers=api_auth,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation(client, api_auth):
    cid = _cid("iso")
    tid_a = f"tenant_a_{_uid()}"
    tid_b = f"tenant_b_{_uid()}"

    for tid in (tid_a, tid_b):
        _advance_to_ready(client, api_auth, tid, cid)
        _create_exec_request(client, api_auth, tid, cid)

    # Cancel for tenant_a only
    client.post(f"{EXEC_URL}/cancel", json={"tenant_id": tid_a, "change_id": cid}, headers=api_auth)

    resp_a = client.get(f"{EXEC_URL}/{cid}?tenant_id={tid_a}", headers=api_auth)
    resp_b = client.get(f"{EXEC_URL}/{cid}?tenant_id={tid_b}", headers=api_auth)

    assert resp_a.json()["status"] == "cancelled"
    assert resp_b.json()["status"] == "requested"


def test_list_is_tenant_scoped(client, api_auth):
    cid = _cid("scoped")
    tid_x = f"tenant_x_{_uid()}"
    tid_y = f"tenant_y_{_uid()}"

    for tid in (tid_x, tid_y):
        _advance_to_ready(client, api_auth, tid, cid)
        _create_exec_request(client, api_auth, tid, cid)

    resp_x = client.get(f"{EXEC_URL}?tenant_id={tid_x}", headers=api_auth)
    assert resp_x.json()["total"] == 1

    resp_y = client.get(f"{EXEC_URL}?tenant_id={tid_y}", headers=api_auth)
    assert resp_y.json()["total"] == 1
