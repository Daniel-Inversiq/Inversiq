"""
tests/test_proposed_change_state.py

Tests for:
  GET  /api/proposed-change-state
  POST /api/proposed-change-state
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import pytest

STATE_URL = "/api/proposed-change-state"


@pytest.fixture
def api_auth():
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _cid(prefix: str = "pipe") -> str:
    return f"pipeline:{prefix}_{_uid()}:confidence_threshold_tuning:no_parameter"


def _payload(**overrides) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "tenant_id": _uid(),
        "change_id": _cid(),
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


# ---------------------------------------------------------------------------
# GET — synthetic default
# ---------------------------------------------------------------------------


class TestGetSyntheticDefault:
    def test_returns_200_for_unknown_change(self, client, api_auth):
        resp = client.get(f"{STATE_URL}?change_id={_cid()}&tenant_id={_uid()}", headers=api_auth)
        assert resp.status_code == 200

    def test_synthetic_default_shape(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        body = client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth).json()
        assert body["change_id"] == cid
        assert body["tenant_id"] == tid
        assert body["status"] == "pending"
        assert body["note"] is None
        assert body["created_at"] is None
        assert body["updated_at"] is None
        assert body["persisted"] is False

    def test_get_missing_change_id_returns_422(self, client, api_auth):
        resp = client.get(f"{STATE_URL}?tenant_id=abc", headers=api_auth)
        assert resp.status_code == 422

    def test_get_missing_tenant_id_returns_422(self, client, api_auth):
        resp = client.get(f"{STATE_URL}?change_id=abc", headers=api_auth)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST — create
# ---------------------------------------------------------------------------


class TestCreateState:
    def test_create_returns_200(self, client, api_auth):
        resp = client.post(STATE_URL, json=_payload(), headers=api_auth)
        assert resp.status_code == 200

    def test_create_response_shape(self, client, api_auth):
        p = _payload(status="pending", note="initial")
        body = client.post(STATE_URL, json=p, headers=api_auth).json()
        assert body["change_id"] == p["change_id"]
        assert body["tenant_id"] == p["tenant_id"]
        assert body["status"] == "pending"
        assert body["note"] == "initial"
        assert body["persisted"] is True
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_get_after_create_returns_persisted(self, client, api_auth):
        p = _payload(status="approved", note="looks good")
        client.post(STATE_URL, json=p, headers=api_auth)

        body = client.get(
            f"{STATE_URL}?change_id={p['change_id']}&tenant_id={p['tenant_id']}",
            headers=api_auth,
        ).json()
        assert body["status"] == "approved"
        assert body["note"] == "looks good"
        assert body["persisted"] is True


# ---------------------------------------------------------------------------
# POST — upsert / update
# ---------------------------------------------------------------------------


class TestUpsertState:
    def test_upsert_updates_status(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, status="pending"), headers=api_auth)
        body = client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, status="approved"), headers=api_auth).json()
        assert body["status"] == "approved"

    def test_upsert_updates_note(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, note=None), headers=api_auth)
        body = client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, note="reviewed"), headers=api_auth).json()
        assert body["note"] == "reviewed"

    def test_created_at_preserved_on_update(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        r1 = client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, status="pending"), headers=api_auth).json()
        r2 = client.post(STATE_URL, json=_payload(tenant_id=tid, change_id=cid, status="approved"), headers=api_auth).json()
        assert r1["created_at"] == r2["created_at"]

    def test_double_create_does_not_duplicate(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        p = _payload(tenant_id=tid, change_id=cid)
        client.post(STATE_URL, json=p, headers=api_auth)
        client.post(STATE_URL, json=p, headers=api_auth)

        body = client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid}", headers=api_auth).json()
        assert body["persisted"] is True

    def test_proposal_payload_persisted_and_returned(self, client, api_auth):
        tid = _uid()
        cid = _cid()
        payload_data = {"direction": "decrease", "suggested_delta": -0.05}
        p = _payload(tenant_id=tid, change_id=cid, proposal_payload=payload_data)
        body = client.post(STATE_URL, json=p, headers=api_auth).json()
        assert body["proposal_payload"] == payload_data


# ---------------------------------------------------------------------------
# Status validation
# ---------------------------------------------------------------------------


class TestStatusValidation:
    def test_invalid_status_returns_422(self, client, api_auth):
        resp = client.post(STATE_URL, json=_payload(status="bad_value"), headers=api_auth)
        assert resp.status_code == 422

    def test_all_valid_statuses_accepted(self, client, api_auth):
        for status in ("pending", "approved", "rejected", "archived"):
            resp = client.post(STATE_URL, json=_payload(status=status), headers=api_auth)
            assert resp.status_code == 200, f"Failed for status={status}"
            assert resp.json()["status"] == status


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_state_not_visible_across_tenants(self, client, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        cid = _cid("shared")

        client.post(STATE_URL, json=_payload(tenant_id=tid_a, change_id=cid, status="approved"), headers=api_auth)

        body_b = client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid_b}", headers=api_auth).json()
        assert body_b["persisted"] is False
        assert body_b["status"] == "pending"

    def test_same_change_id_independent_per_tenant(self, client, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        cid = _cid("shared2")

        client.post(STATE_URL, json=_payload(tenant_id=tid_a, change_id=cid, status="approved"), headers=api_auth)
        client.post(STATE_URL, json=_payload(tenant_id=tid_b, change_id=cid, status="rejected"), headers=api_auth)

        assert client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid_a}", headers=api_auth).json()["status"] == "approved"
        assert client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid_b}", headers=api_auth).json()["status"] == "rejected"
