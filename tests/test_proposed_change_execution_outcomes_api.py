"""
tests/test_proposed_change_execution_outcomes_api.py

Integration tests for:
  POST /api/proposed-change-execution-outcomes/record
  GET  /api/proposed-change-execution-outcomes?tenant_id=...
  GET  /api/proposed-change-execution-outcomes/{change_id}?tenant_id=...
"""

from __future__ import annotations

import base64
import uuid
from typing import Any
from unittest.mock import patch

import pytest

OUTCOMES_URL = "/api/proposed-change-execution-outcomes"
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


def _state_payload(tenant_id: str, change_id: str) -> dict[str, Any]:
    return {
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


def _advance_to_exec_request(client, api_auth, tenant_id: str, change_id: str) -> int:
    """Create state → approve → mark-ready-for-apply → create execution request.
    Returns the execution_request_id."""
    client.post(STATE_URL, json=_state_payload(tenant_id, change_id), headers=api_auth)

    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )

    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )

    with patch(_EXEC_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{EXEC_URL}/create",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _metric(value: float, baseline: float, direction: str = "lower_is_better") -> dict:
    return {"value": value, "baseline": baseline, "direction": direction}


# ---------------------------------------------------------------------------
# POST /record
# ---------------------------------------------------------------------------


def test_record_improved_outcome(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "success",
        "observed_metrics_snapshot": {
            "failed_rate": _metric(0.03, 0.06),
            "review_rate": _metric(0.08, 0.12),
        },
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["tenant_id"] == tid
    assert data["change_id"] == cid
    assert data["outcome_status"] == "success"
    assert data["evaluation_status"] == "improved"
    assert data["rollback_triggered"] is False
    assert data["rollback_reason"] is None
    assert data["deviation_snapshot"] is not None


def test_record_degraded_outcome(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "partial",
        "observed_metrics_snapshot": {
            "failed_rate": _metric(0.053, 0.05),  # 6% worse → degraded (above 5%, below 10%)
        },
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_status"] == "degraded"
    assert data["rollback_triggered"] is False


def test_record_unstable_outcome_triggers_rollback(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "failed",
        "observed_metrics_snapshot": {
            "failed_rate": _metric(0.25, 0.05),  # 400% worse → unstable
        },
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_status"] == "unstable"
    assert data["rollback_triggered"] is True
    assert data["rollback_reason"] is not None


def test_record_neutral_outcome(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "success",
        "observed_metrics_snapshot": {
            "failed_rate": 0.05,  # scalar — no baseline, neutral
        },
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_status"] == "neutral"


def test_record_missing_metrics_handled_gracefully(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    # Empty observed metrics — none of the watched metrics are present
    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "partial",
        "observed_metrics_snapshot": {},
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_status"] == "neutral"
    assert data["rollback_triggered"] is False


def test_record_fails_for_nonexistent_execution_request(client, api_auth):
    tid = f"tenant_{_uid()}"
    payload = {
        "tenant_id": tid,
        "execution_request_id": 999999,
        "outcome_status": "success",
        "observed_metrics_snapshot": {},
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 404


def test_record_fails_for_invalid_outcome_status(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "not_a_valid_status",
        "observed_metrics_snapshot": {},
    }
    resp = client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)
    assert resp.status_code == 422


def test_record_writes_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "success",
        "observed_metrics_snapshot": {"failed_rate": _metric(0.03, 0.06)},
    }
    client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_outcome_recorded" in event_types


def test_record_rollback_writes_rollback_audit_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "failed",
        "observed_metrics_snapshot": {"failed_rate": _metric(0.25, 0.05)},
    }
    client.post(f"{OUTCOMES_URL}/record", json=payload, headers=api_auth)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "rollback_triggered" in event_types


def test_re_recording_overwrites_and_writes_update_event(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    payload_first = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "partial",
        "observed_metrics_snapshot": {"failed_rate": _metric(0.053, 0.05)},  # 6% → degraded
    }
    resp1 = client.post(f"{OUTCOMES_URL}/record", json=payload_first, headers=api_auth)
    first_id = resp1.json()["id"]
    assert resp1.json()["evaluation_status"] == "degraded"

    payload_second = {
        "tenant_id": tid,
        "execution_request_id": exec_id,
        "outcome_status": "success",
        "observed_metrics_snapshot": {"failed_rate": _metric(0.03, 0.06)},
    }
    resp2 = client.post(f"{OUTCOMES_URL}/record", json=payload_second, headers=api_auth)
    assert resp2.json()["id"] == first_id
    assert resp2.json()["evaluation_status"] == "improved"

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    event_types = [e["event_type"] for e in resp.json()]
    assert "execution_outcome_updated" in event_types


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------


def test_list_outcomes(client, api_auth):
    tid = f"tenant_list_{_uid()}"
    cids_and_ids = []
    for _ in range(3):
        cid = _cid("list")
        exec_id = _advance_to_exec_request(client, api_auth, tid, cid)
        cids_and_ids.append((cid, exec_id))

    for cid, exec_id in cids_and_ids:
        client.post(
            f"{OUTCOMES_URL}/record",
            json={
                "tenant_id": tid,
                "execution_request_id": exec_id,
                "outcome_status": "success",
                "observed_metrics_snapshot": {},
            },
            headers=api_auth,
        )

    resp = client.get(f"{OUTCOMES_URL}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tid
    assert data["total"] == 3


def test_list_filter_by_outcome_status(client, api_auth):
    tid = f"tenant_flt_{_uid()}"

    cid_success = _cid("suc")
    exec_success = _advance_to_exec_request(client, api_auth, tid, cid_success)
    client.post(
        f"{OUTCOMES_URL}/record",
        json={
            "tenant_id": tid,
            "execution_request_id": exec_success,
            "outcome_status": "success",
            "observed_metrics_snapshot": {},
        },
        headers=api_auth,
    )

    cid_failed = _cid("fail")
    exec_failed = _advance_to_exec_request(client, api_auth, tid, cid_failed)
    client.post(
        f"{OUTCOMES_URL}/record",
        json={
            "tenant_id": tid,
            "execution_request_id": exec_failed,
            "outcome_status": "failed",
            "observed_metrics_snapshot": {},
        },
        headers=api_auth,
    )

    resp = client.get(
        f"{OUTCOMES_URL}?tenant_id={tid}&outcome_status=success", headers=api_auth
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["outcome_status"] == "success"


def test_list_filter_by_evaluation_status(client, api_auth):
    tid = f"tenant_evl_{_uid()}"

    cid_improved = _cid("imp")
    exec_improved = _advance_to_exec_request(client, api_auth, tid, cid_improved)
    client.post(
        f"{OUTCOMES_URL}/record",
        json={
            "tenant_id": tid,
            "execution_request_id": exec_improved,
            "outcome_status": "success",
            "observed_metrics_snapshot": {"failed_rate": _metric(0.03, 0.06)},
        },
        headers=api_auth,
    )

    cid_unstable = _cid("uns")
    exec_unstable = _advance_to_exec_request(client, api_auth, tid, cid_unstable)
    client.post(
        f"{OUTCOMES_URL}/record",
        json={
            "tenant_id": tid,
            "execution_request_id": exec_unstable,
            "outcome_status": "failed",
            "observed_metrics_snapshot": {"failed_rate": _metric(0.25, 0.05)},
        },
        headers=api_auth,
    )

    resp = client.get(
        f"{OUTCOMES_URL}?tenant_id={tid}&evaluation_status=improved", headers=api_auth
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["evaluation_status"] == "improved"


# ---------------------------------------------------------------------------
# GET /{change_id}
# ---------------------------------------------------------------------------


def test_get_outcome_by_change_id(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()
    exec_id = _advance_to_exec_request(client, api_auth, tid, cid)

    client.post(
        f"{OUTCOMES_URL}/record",
        json={
            "tenant_id": tid,
            "execution_request_id": exec_id,
            "outcome_status": "success",
            "observed_metrics_snapshot": {"failed_rate": _metric(0.03, 0.06)},
        },
        headers=api_auth,
    )

    resp = client.get(f"{OUTCOMES_URL}/{cid}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["change_id"] == cid
    assert data["evaluation_status"] == "improved"
    assert data["deviation_snapshot"] is not None


def test_get_outcome_not_found(client, api_auth):
    resp = client.get(
        f"{OUTCOMES_URL}/pipeline:nonexistent:cat:param?tenant_id=nobody",
        headers=api_auth,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation_record(client, api_auth):
    cid = _cid("iso")
    tid_a = f"tenant_a_{_uid()}"
    tid_b = f"tenant_b_{_uid()}"

    for tid in (tid_a, tid_b):
        exec_id = _advance_to_exec_request(client, api_auth, tid, cid)
        outcome_status = "success" if tid == tid_a else "failed"
        client.post(
            f"{OUTCOMES_URL}/record",
            json={
                "tenant_id": tid,
                "execution_request_id": exec_id,
                "outcome_status": outcome_status,
                "observed_metrics_snapshot": {},
            },
            headers=api_auth,
        )

    resp_a = client.get(f"{OUTCOMES_URL}/{cid}?tenant_id={tid_a}", headers=api_auth)
    resp_b = client.get(f"{OUTCOMES_URL}/{cid}?tenant_id={tid_b}", headers=api_auth)

    assert resp_a.json()["outcome_status"] == "success"
    assert resp_b.json()["outcome_status"] == "failed"


def test_list_is_tenant_scoped(client, api_auth):
    cid = _cid("scoped")
    tid_x = f"tenant_x_{_uid()}"
    tid_y = f"tenant_y_{_uid()}"

    for tid in (tid_x, tid_y):
        exec_id = _advance_to_exec_request(client, api_auth, tid, cid)
        client.post(
            f"{OUTCOMES_URL}/record",
            json={
                "tenant_id": tid,
                "execution_request_id": exec_id,
                "outcome_status": "success",
                "observed_metrics_snapshot": {},
            },
            headers=api_auth,
        )

    resp_x = client.get(f"{OUTCOMES_URL}?tenant_id={tid_x}", headers=api_auth)
    resp_y = client.get(f"{OUTCOMES_URL}?tenant_id={tid_y}", headers=api_auth)

    assert resp_x.json()["total"] == 1
    assert resp_y.json()["total"] == 1
