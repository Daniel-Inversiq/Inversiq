"""
tests/test_proposed_change_audit.py

Tests for:
  POST /api/proposed-change-state  — audit events emitted on create/update
  GET  /api/proposed-change-audit  — audit history retrieval
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

STATE_URL = "/api/proposed-change-state"
AUDIT_URL = "/api/proposed-change-audit"


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _cid(prefix: str = "pipe") -> str:
    return f"pipeline:{prefix}_{_uid()}:confidence_threshold_tuning:no_parameter"


def _api_auth():
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


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


def _post_state(client, **overrides):
    return client.post(STATE_URL, json=_payload(**overrides), headers=_api_auth())


def _get_audit(client, *, change_id: str, tenant_id: str) -> list[dict]:
    resp = client.get(
        f"{AUDIT_URL}?change_id={change_id}&tenant_id={tenant_id}",
        headers=_api_auth(),
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Audit event created on initial POST
# ---------------------------------------------------------------------------


class TestAuditOnCreate:
    def test_single_event_on_create(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        assert len(events) == 1

    def test_create_event_type(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        assert events[0]["event_type"] == "created"

    def test_create_event_status_fields(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="approved")

        event = _get_audit(client, change_id=cid, tenant_id=tid)[0]
        assert event["previous_status"] is None
        assert event["new_status"] == "approved"

    def test_create_event_note_fields_null(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, note=None)

        event = _get_audit(client, change_id=cid, tenant_id=tid)[0]
        assert event["previous_note"] is None
        assert event["new_note"] is None


# ---------------------------------------------------------------------------
# Audit event on status change
# ---------------------------------------------------------------------------


class TestAuditOnStatusChange:
    def test_status_change_event_emitted(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")
        _post_state(client, tenant_id=tid, change_id=cid, status="approved")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        types = [e["event_type"] for e in events]
        assert "status_changed" in types

    def test_status_change_event_captures_transition(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")
        _post_state(client, tenant_id=tid, change_id=cid, status="rejected")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        status_event = next(e for e in events if e["event_type"] == "status_changed")
        assert status_event["previous_status"] == "pending"
        assert status_event["new_status"] == "rejected"

    def test_no_status_change_event_when_status_unchanged(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending", note=None)
        _post_state(client, tenant_id=tid, change_id=cid, status="pending", note="same status")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        types = [e["event_type"] for e in events]
        assert "status_changed" not in types


# ---------------------------------------------------------------------------
# Audit event on note change
# ---------------------------------------------------------------------------


class TestAuditOnNoteChange:
    def test_note_update_event_emitted(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, note=None)
        _post_state(client, tenant_id=tid, change_id=cid, note="new note")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        types = [e["event_type"] for e in events]
        assert "note_updated" in types

    def test_note_update_captures_previous_and_new(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, note="old note")
        _post_state(client, tenant_id=tid, change_id=cid, note="new note")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        note_event = next(e for e in events if e["event_type"] == "note_updated")
        assert note_event["previous_note"] == "old note"
        assert note_event["new_note"] == "new note"

    def test_no_note_event_when_note_unchanged(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, note="same", status="pending")
        _post_state(client, tenant_id=tid, change_id=cid, note="same", status="approved")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        types = [e["event_type"] for e in events]
        assert "note_updated" not in types


# ---------------------------------------------------------------------------
# Multiple updates produce multiple events
# ---------------------------------------------------------------------------


class TestMultipleUpdates:
    def test_multiple_updates_accumulate_events(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending", note=None)
        _post_state(client, tenant_id=tid, change_id=cid, status="approved", note=None)
        _post_state(client, tenant_id=tid, change_id=cid, status="approved", note="looks good")
        _post_state(client, tenant_id=tid, change_id=cid, status="archived", note="looks good")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        assert len(events) >= 4

    def test_events_contain_all_expected_types(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending", note=None)
        _post_state(client, tenant_id=tid, change_id=cid, status="approved", note=None)
        _post_state(client, tenant_id=tid, change_id=cid, status="approved", note="comment")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        types = {e["event_type"] for e in events}
        assert "created" in types
        assert "status_changed" in types
        assert "note_updated" in types


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_events_ordered_oldest_first(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")
        _post_state(client, tenant_id=tid, change_id=cid, status="approved")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        ids = [e["id"] for e in events]
        assert ids == sorted(ids), "Events should be ordered by id ascending (oldest first)"

    def test_first_event_is_created(self, client):
        tid = _uid()
        cid = _cid()
        _post_state(client, tenant_id=tid, change_id=cid, status="pending")
        _post_state(client, tenant_id=tid, change_id=cid, status="approved")

        events = _get_audit(client, change_id=cid, tenant_id=tid)
        assert events[0]["event_type"] == "created"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_audit_not_visible_across_tenants(self, client):
        tid_a = _uid()
        tid_b = _uid()
        cid = _cid("shared")

        _post_state(client, tenant_id=tid_a, change_id=cid, status="approved")

        events_b = _get_audit(client, change_id=cid, tenant_id=tid_b)
        assert events_b == []

    def test_separate_audit_trails_per_tenant(self, client):
        tid_a = _uid()
        tid_b = _uid()
        cid = _cid("shared2")

        _post_state(client, tenant_id=tid_a, change_id=cid, status="approved")
        _post_state(client, tenant_id=tid_b, change_id=cid, status="rejected")
        _post_state(client, tenant_id=tid_b, change_id=cid, status="archived")

        events_a = _get_audit(client, change_id=cid, tenant_id=tid_a)
        events_b = _get_audit(client, change_id=cid, tenant_id=tid_b)

        assert len(events_a) == 1
        assert len(events_b) >= 2


# ---------------------------------------------------------------------------
# GET — empty result for unknown change
# ---------------------------------------------------------------------------


class TestGetAuditEdgeCases:
    def test_empty_list_for_unknown_change(self, client):
        events = _get_audit(client, change_id=_cid(), tenant_id=_uid())
        assert events == []

    def test_missing_change_id_returns_422(self, client):
        resp = client.get(f"{AUDIT_URL}?tenant_id=abc", headers=_api_auth())
        assert resp.status_code == 422

    def test_missing_tenant_id_returns_422(self, client):
        resp = client.get(f"{AUDIT_URL}?change_id=abc", headers=_api_auth())
        assert resp.status_code == 422
