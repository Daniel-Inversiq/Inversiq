"""
tests/test_proposed_change_apply_intents_api.py

Integration tests for:
  GET /api/proposed-change-apply-intents
  GET /api/proposed-change-apply-intents/{change_id}

Also covers mark-ready-for-apply → apply intent created, and
cancel-ready-for-apply → apply intent cancelled via action endpoints.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any
from unittest.mock import patch

import pytest

ACTIONS_URL = "/api/proposed-change-actions"
STATE_URL = "/api/proposed-change-state"
AUDIT_URL = "/api/proposed-change-audit"
INTENTS_URL = "/api/proposed-change-apply-intents"

_ATTEST_MODULE = "app.routers.proposed_change_actions.compute_governance_attestation"


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
        "title": "Lower review confidence threshold slightly",
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


def _create_state(client, api_auth, tenant_id: str, change_id: str, status: str = "pending") -> dict:
    resp = client.post(
        STATE_URL,
        json=_state_payload(tenant_id, change_id, status=status),
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _advance_to_approved(client, api_auth, tenant_id: str, change_id: str) -> None:
    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text


def _advance_to_ready(client, api_auth, tenant_id: str, change_id: str) -> dict:
    with patch(_ATTEST_MODULE, return_value=_attest_ok(change_id)):
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tenant_id, "change_id": change_id},
            headers=api_auth,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# mark-ready-for-apply creates apply intent
# ---------------------------------------------------------------------------


def test_mark_ready_creates_apply_intent(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _create_state(client, api_auth, tid, cid)
    _advance_to_approved(client, api_auth, tid, cid)
    _advance_to_ready(client, api_auth, tid, cid)

    resp = client.get(f"{INTENTS_URL}/{cid}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()

    assert data["change_id"] == cid
    assert data["tenant_id"] == tid
    assert data["status"] == "ready_for_apply"
    assert data["change_type"] == "threshold_adjustment"
    assert data["governance_snapshot"] is not None
    assert data["governance_snapshot"]["apply_planning_status"] == "planned"
    assert data["governance_snapshot"]["approval_readiness_status"] == "approval_ready"


def test_mark_ready_writes_apply_intent_created_audit(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _create_state(client, api_auth, tid, cid)
    _advance_to_approved(client, api_auth, tid, cid)
    _advance_to_ready(client, api_auth, tid, cid)

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    events = resp.json()
    event_types = [e["event_type"] for e in events]
    assert "apply_intent_created" in event_types


# ---------------------------------------------------------------------------
# cancel-ready-for-apply cancels apply intent
# ---------------------------------------------------------------------------


def test_cancel_ready_cancels_apply_intent(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _create_state(client, api_auth, tid, cid)
    _advance_to_approved(client, api_auth, tid, cid)
    _advance_to_ready(client, api_auth, tid, cid)

    resp = client.post(
        f"{ACTIONS_URL}/cancel-ready-for-apply",
        json={"tenant_id": tid, "change_id": cid},
        headers=api_auth,
    )
    assert resp.status_code == 200

    intent_resp = client.get(f"{INTENTS_URL}/{cid}?tenant_id={tid}", headers=api_auth)
    assert intent_resp.status_code == 200
    assert intent_resp.json()["status"] == "cancelled"


def test_cancel_ready_writes_apply_intent_cancelled_audit(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _create_state(client, api_auth, tid, cid)
    _advance_to_approved(client, api_auth, tid, cid)
    _advance_to_ready(client, api_auth, tid, cid)

    client.post(
        f"{ACTIONS_URL}/cancel-ready-for-apply",
        json={"tenant_id": tid, "change_id": cid},
        headers=api_auth,
    )

    resp = client.get(f"{AUDIT_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth)
    events = resp.json()
    event_types = [e["event_type"] for e in events]
    assert "apply_intent_cancelled" in event_types


# ---------------------------------------------------------------------------
# Repeated mark-ready-for-apply updates existing intent
# ---------------------------------------------------------------------------


def test_repeated_mark_ready_updates_intent(client, api_auth):
    tid = f"tenant_{_uid()}"
    cid = _cid()

    _create_state(client, api_auth, tid, cid)
    _advance_to_approved(client, api_auth, tid, cid)
    _advance_to_ready(client, api_auth, tid, cid)

    # Cancel and re-approve, then mark ready again
    client.post(
        f"{ACTIONS_URL}/cancel-ready-for-apply",
        json={"tenant_id": tid, "change_id": cid},
        headers=api_auth,
    )
    _advance_to_ready(client, api_auth, tid, cid)

    resp = client.get(f"{INTENTS_URL}/{cid}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready_for_apply"


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------


def test_list_apply_intents(client, api_auth):
    tid = f"tenant_list_{_uid()}"
    cids = [_cid("list") for _ in range(3)]

    for cid in cids:
        _create_state(client, api_auth, tid, cid)
        _advance_to_approved(client, api_auth, tid, cid)
        _advance_to_ready(client, api_auth, tid, cid)

    resp = client.get(f"{INTENTS_URL}?tenant_id={tid}", headers=api_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tid
    assert data["total"] == 3
    returned_ids = {i["change_id"] for i in data["items"]}
    for cid in cids:
        assert cid in returned_ids


def test_list_apply_intents_filter_by_status(client, api_auth):
    tid = f"tenant_filter_{_uid()}"
    cid_active = _cid("active")
    cid_cancelled = _cid("cancelled")

    for cid in (cid_active, cid_cancelled):
        _create_state(client, api_auth, tid, cid)
        _advance_to_approved(client, api_auth, tid, cid)
        _advance_to_ready(client, api_auth, tid, cid)

    client.post(
        f"{ACTIONS_URL}/cancel-ready-for-apply",
        json={"tenant_id": tid, "change_id": cid_cancelled},
        headers=api_auth,
    )

    resp = client.get(
        f"{INTENTS_URL}?tenant_id={tid}&status=ready_for_apply", headers=api_auth
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["change_id"] == cid_active


# ---------------------------------------------------------------------------
# 404 when not found
# ---------------------------------------------------------------------------


def test_get_apply_intent_not_found(client, api_auth):
    resp = client.get(
        f"{INTENTS_URL}/pipeline:nonexistent:cat:param?tenant_id=nobody",
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
        _create_state(client, api_auth, tid, cid)
        _advance_to_approved(client, api_auth, tid, cid)
        _advance_to_ready(client, api_auth, tid, cid)

    # Cancel for tenant_a only
    client.post(
        f"{ACTIONS_URL}/cancel-ready-for-apply",
        json={"tenant_id": tid_a, "change_id": cid},
        headers=api_auth,
    )

    resp_a = client.get(f"{INTENTS_URL}/{cid}?tenant_id={tid_a}", headers=api_auth)
    resp_b = client.get(f"{INTENTS_URL}/{cid}?tenant_id={tid_b}", headers=api_auth)

    assert resp_a.json()["status"] == "cancelled"
    assert resp_b.json()["status"] == "ready_for_apply"
