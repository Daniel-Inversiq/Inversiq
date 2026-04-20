"""
tests/test_proposed_change_actions.py

Tests for the workflow action endpoints:
  POST /api/proposed-change-actions/approve
  POST /api/proposed-change-actions/reject
  POST /api/proposed-change-actions/reopen
  POST /api/proposed-change-actions/mark-ready-for-apply
  POST /api/proposed-change-actions/cancel-ready-for-apply

Also covers:
  - Server-side governance enforcement (approve, mark-ready-for-apply)
  - Caller-supplied values are ignored as source of truth
  - Invalid transitions
  - Audit event emission per action
  - Audit metadata enriched with governance snapshot on gated actions
  - workflow_phase field on state responses
  - Tenant isolation

Governance attestation is mocked at the router module level using monkeypatch.
This isolates state-machine and audit tests from the live governance chain,
which requires real pipeline data in the DB.  Dedicated attestation enforcement
tests verify that the server-side gate overrides any caller-supplied values.
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


def _create_state(client, api_auth, tenant_id: str, change_id: str, status: str = "pending") -> dict:
    resp = client.post(
        STATE_URL,
        json=_state_payload(tenant_id, change_id, status=status),
        headers=api_auth,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _get_audit(client, api_auth, tenant_id: str, change_id: str) -> list[dict]:
    resp = client.get(f"{AUDIT_URL}?change_id={change_id}&tenant_id={tenant_id}", headers=api_auth)
    assert resp.status_code == 200
    return resp.json()


def _attest_ok(change_id: str = "") -> dict[str, Any]:
    """Attestation result: governance-valid, approval_ready + planned."""
    return {
        "attestable": True,
        "change_id": change_id,
        "scope_type": "pipeline",
        "scope_id": "test_pipe",
        "approval_readiness_status": "approval_ready",
        "apply_planning_status": "planned",
        "conflict_status": {"has_high_conflict": False, "has_medium_conflict": False},
        "staleness_status": "fresh",
        "attestation_summary": "Proposal remains governance-valid for approval and guarded apply intent.",
        "attested_at": "2026-04-18T00:00:00+00:00",
    }


def _attest_blocked(
    change_id: str = "",
    *,
    readiness: str = "blocked",
    planning: str = "planned",
    staleness: str = "fresh",
    has_high_conflict: bool = False,
) -> dict[str, Any]:
    """Attestation result: governance blocked."""
    return {
        "attestable": True,
        "change_id": change_id,
        "scope_type": "pipeline",
        "scope_id": "test_pipe",
        "approval_readiness_status": readiness,
        "apply_planning_status": planning,
        "conflict_status": {
            "has_high_conflict": has_high_conflict,
            "has_medium_conflict": False,
        },
        "staleness_status": staleness,
        "attestation_summary": f"Blocked: readiness={readiness} planning={planning}.",
        "attested_at": "2026-04-18T00:00:00+00:00",
    }


def _attest_unattestable(change_id: str = "", reason: str = "scope not found") -> dict[str, Any]:
    return {
        "attestable": False,
        "change_id": change_id,
        "scope_type": None,
        "scope_id": None,
        "approval_readiness_status": None,
        "apply_planning_status": None,
        "conflict_status": None,
        "staleness_status": None,
        "attestation_summary": reason,
        "attested_at": None,
    }


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


class TestApprove:
    def test_approve_from_pending_when_approval_ready(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_ok(cid),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["workflow_phase"] == "review"

    def test_approve_blocked_when_server_attestation_says_blocked(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, readiness="blocked"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "approval_readiness_status" in resp.json()["detail"]

    def test_approve_blocked_when_server_attestation_says_blocked_with_warnings(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, readiness="blocked_with_warnings"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422

    def test_approve_writes_audit_event(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        events = _get_audit(client, api_auth, tid, cid)
        action_events = [e for e in events if e["event_type"] == "approved"]
        assert len(action_events) == 1
        ev = action_events[0]
        assert ev["previous_status"] == "pending"
        assert ev["new_status"] == "approved"

    def test_approve_audit_contains_governance_snapshot(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        events = _get_audit(client, api_auth, tid, cid)
        approved_event = next(e for e in events if e["event_type"] == "approved")
        meta_raw = approved_event.get("metadata_json")
        assert meta_raw is not None
        meta = json.loads(meta_raw)
        assert meta["attested_approval_readiness_status"] == "approval_ready"
        assert meta["attested_apply_planning_status"] == "planned"
        assert meta["attested_staleness_status"] == "fresh"
        assert meta["attested_has_high_conflict"] is False

    def test_approve_with_note(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid, "note": "LGTM"},
            headers=api_auth,
        )
        assert resp.json()["note"] == "LGTM"

    def test_approve_404_for_nonexistent_state(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


class TestReject:
    def test_reject_from_pending(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        resp = client.post(
            f"{ACTIONS_URL}/reject",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_from_approved(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        resp = client.post(
            f"{ACTIONS_URL}/reject",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_writes_audit_event(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")
        client.post(f"{ACTIONS_URL}/reject", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

        events = _get_audit(client, api_auth, tid, cid)
        action_events = [e for e in events if e["event_type"] == "rejected"]
        assert len(action_events) == 1
        assert action_events[0]["previous_status"] == "pending"
        assert action_events[0]["new_status"] == "rejected"

    def test_reject_from_ready_for_apply_is_invalid(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="ready_for_apply")

        resp = client.post(
            f"{ACTIONS_URL}/reject",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "Invalid transition" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Reopen
# ---------------------------------------------------------------------------


class TestReopen:
    def test_reopen_from_rejected(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="rejected")

        resp = client.post(
            f"{ACTIONS_URL}/reopen",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_reopen_from_archived(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="archived")

        resp = client.post(
            f"{ACTIONS_URL}/reopen",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_reopen_from_approved(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        resp = client.post(
            f"{ACTIONS_URL}/reopen",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_reopen_writes_audit_event(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="rejected")
        client.post(f"{ACTIONS_URL}/reopen", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)

        events = _get_audit(client, api_auth, tid, cid)
        action_events = [e for e in events if e["event_type"] == "reopened"]
        assert len(action_events) == 1
        assert action_events[0]["previous_status"] == "rejected"
        assert action_events[0]["new_status"] == "pending"


# ---------------------------------------------------------------------------
# Mark ready_for_apply
# ---------------------------------------------------------------------------


class TestMarkReadyForApply:
    def test_mark_ready_from_approved_when_planned(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready_for_apply"
        assert body["workflow_phase"] == "apply_intent"

    def test_mark_ready_blocked_when_server_attestation_says_requires_combined_plan(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, planning="requires_combined_plan"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "apply_planning_status" in resp.json()["detail"]

    def test_mark_ready_blocked_when_server_attestation_says_blocked_from_planning(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, planning="blocked_from_planning"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422

    def test_mark_ready_invalid_from_pending(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "Invalid transition" in resp.json()["detail"]

    def test_mark_ready_writes_audit_event(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        events = _get_audit(client, api_auth, tid, cid)
        action_events = [e for e in events if e["event_type"] == "marked_ready_for_apply"]
        assert len(action_events) == 1
        assert action_events[0]["previous_status"] == "approved"
        assert action_events[0]["new_status"] == "ready_for_apply"

    def test_mark_ready_audit_contains_governance_snapshot(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        events = _get_audit(client, api_auth, tid, cid)
        mark_event = next(
            e for e in events if e["event_type"] == "marked_ready_for_apply"
        )
        meta = json.loads(mark_event["metadata_json"])
        assert meta["attested_apply_planning_status"] == "planned"
        assert meta["attested_approval_readiness_status"] == "approval_ready"


# ---------------------------------------------------------------------------
# Cancel ready_for_apply
# ---------------------------------------------------------------------------


class TestCancelReadyForApply:
    def test_cancel_from_ready_for_apply(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="ready_for_apply")

        resp = client.post(
            f"{ACTIONS_URL}/cancel-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["workflow_phase"] == "review"

    def test_cancel_invalid_from_pending(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        resp = client.post(
            f"{ACTIONS_URL}/cancel-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "Invalid transition" in resp.json()["detail"]

    def test_cancel_writes_audit_event(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="ready_for_apply")
        client.post(
            f"{ACTIONS_URL}/cancel-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        events = _get_audit(client, api_auth, tid, cid)
        action_events = [e for e in events if e["event_type"] == "cancelled_ready_for_apply"]
        assert len(action_events) == 1
        assert action_events[0]["previous_status"] == "ready_for_apply"
        assert action_events[0]["new_status"] == "approved"


# ---------------------------------------------------------------------------
# Full workflow sequence
# ---------------------------------------------------------------------------


class TestFullWorkflowSequence:
    def test_approve_then_mark_ready_then_cancel(self, client, api_auth, monkeypatch):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )

        # pending → approved
        client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        # approved → ready_for_apply
        client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        # ready_for_apply → approved
        resp = client.post(
            f"{ACTIONS_URL}/cancel-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.json()["status"] == "approved"

        # Audit trail should have: created, approved, marked_ready_for_apply, cancelled_ready_for_apply
        events = _get_audit(client, api_auth, tid, cid)
        types = [e["event_type"] for e in events]
        assert "approved" in types
        assert "marked_ready_for_apply" in types
        assert "cancelled_ready_for_apply" in types

    def test_reject_then_reopen(self, client, api_auth):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")
        client.post(f"{ACTIONS_URL}/reject", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
        resp = client.post(f"{ACTIONS_URL}/reopen", json={"tenant_id": tid, "change_id": cid}, headers=api_auth)
        assert resp.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    @pytest.mark.parametrize("from_status,action,extra", [
        ("rejected", "approve", {}),
        ("archived", "approve", {}),
        ("ready_for_apply", "reject", {}),
        ("pending", "cancel-ready-for-apply", {}),
        ("rejected", "cancel-ready-for-apply", {}),
        ("pending", "mark-ready-for-apply", {}),
        ("rejected", "mark-ready-for-apply", {}),
    ])
    def test_invalid_transition_returns_422(self, client, api_auth, monkeypatch, from_status, action, extra):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status=from_status)

        # Provide a valid attestation so governance gating does not interfere
        # with the state-machine transition check
        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/{action}",
            json={"tenant_id": tid, "change_id": cid, **extra},
            headers=api_auth,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Server-side attestation enforcement
# Tests that the server ignores caller-supplied readiness/planning values.
# ---------------------------------------------------------------------------


class TestServerSideAttestationEnforcement:
    def test_approve_succeeds_when_server_attests_approval_ready(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        # Caller does NOT supply approval_readiness_status — server is authority
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_fails_even_if_caller_sends_approval_ready_but_server_says_blocked(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        # Server says blocked — caller-supplied value is irrelevant
        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, readiness="blocked"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            # Caller supplies "approval_ready" — must be ignored
            json={
                "tenant_id": tid,
                "change_id": cid,
                "approval_readiness_status": "approval_ready",
            },
            headers=api_auth,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "server-side" in detail.lower() or "approval_readiness_status" in detail

    def test_mark_ready_succeeds_when_server_attests_planned(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready_for_apply"

    def test_mark_ready_fails_when_server_says_requires_combined_plan(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(cid, planning="requires_combined_plan"),
            raising=False,
        )
        # Caller supplies "planned" — must be ignored
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={
                "tenant_id": tid,
                "change_id": cid,
                "apply_planning_status": "planned",
            },
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "apply_planning_status" in resp.json()["detail"]

    def test_approve_fails_when_proposal_is_unattestable(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_unattestable(cid, "scope not found"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "not attestable" in resp.json()["detail"].lower()

    def test_mark_ready_fails_when_proposal_is_unattestable(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_unattestable(cid, "proposal not found in governance output"),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422
        assert "not attestable" in resp.json()["detail"].lower()

    def test_mark_ready_fails_when_server_attests_stale(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        # Stale proposal → apply planning is blocked_from_planning
        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(
                cid,
                planning="blocked_from_planning",
                staleness="stale",
            ),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422

    def test_mark_ready_fails_when_server_attests_high_conflict(
        self, client, api_auth, monkeypatch
    ):
        tid, cid = _uid(), _cid()
        _create_state(client, api_auth, tid, cid, status="approved")

        monkeypatch.setattr(
            _ATTEST_MODULE,
            lambda *a, **kw: _attest_blocked(
                cid,
                planning="blocked_from_planning",
                has_high_conflict=True,
            ),
            raising=False,
        )
        resp = client.post(
            f"{ACTIONS_URL}/mark-ready-for-apply",
            json={"tenant_id": tid, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_action_on_other_tenant_returns_404(self, client, api_auth, monkeypatch):
        tid_a, tid_b = _uid(), _uid()
        cid = _cid("shared")

        _create_state(client, api_auth, tid_a, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        # Tenant B tries to approve tenant A's change
        resp = client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid_b, "change_id": cid},
            headers=api_auth,
        )
        assert resp.status_code == 404

    def test_actions_isolated_per_tenant(self, client, api_auth, monkeypatch):
        tid_a, tid_b = _uid(), _uid()
        cid = _cid("shared2")

        _create_state(client, api_auth, tid_a, cid, status="pending")
        _create_state(client, api_auth, tid_b, cid, status="pending")

        monkeypatch.setattr(
            _ATTEST_MODULE, lambda *a, **kw: _attest_ok(cid), raising=False
        )
        # Approve tenant A
        client.post(
            f"{ACTIONS_URL}/approve",
            json={"tenant_id": tid_a, "change_id": cid},
            headers=api_auth,
        )

        # Tenant B should still be pending
        resp_b = client.get(f"{STATE_URL}?change_id={cid}&tenant_id={tid_b}", headers=api_auth)
        assert resp_b.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# workflow_phase on state GET
# ---------------------------------------------------------------------------


class TestWorkflowPhase:
    @pytest.mark.parametrize("status,expected_phase", [
        ("pending", "review"),
        ("approved", "review"),
        ("rejected", "review"),
        ("archived", "review"),
        ("ready_for_apply", "apply_intent"),
    ])
    def test_workflow_phase_matches_status(self, client, api_auth, status, expected_phase):
        tid, cid = _uid(), _cid()
        resp = client.post(
            STATE_URL,
            json=_state_payload(tid, cid, status=status),
            headers=api_auth,
        )
        assert resp.json()["workflow_phase"] == expected_phase

    def test_synthetic_default_has_review_phase(self, client, api_auth):
        resp = client.get(
            f"{STATE_URL}?change_id={_cid()}&tenant_id={_uid()}",
            headers=api_auth,
        )
        assert resp.json()["workflow_phase"] == "review"
