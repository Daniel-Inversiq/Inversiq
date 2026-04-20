"""
tests/test_proposed_changes_api.py

API-level tests for:
  - GET /api/proposed-changes/pipelines
  - GET /api/proposed-changes/verticals

Tests use the shared session-scoped TestClient + SQLite from conftest.py.
Each test class uses unique tenant IDs to prevent cross-test pollution.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.models.pipeline_run import PipelineRun

PIPELINES_URL = "/api/proposed-changes/pipelines"
VERTICALS_URL = "/api/proposed-changes/verticals"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def api_auth():
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _make_run(
    db,
    *,
    tenant_id: str,
    status: str = "COMPLETED",
    overall_confidence_label: Optional[str] = None,
    overall_confidence_score: Optional[float] = None,
    pipeline_name: str = "test_pipeline",
    vertical_id: str = "test_vertical",
    days_ago: float = 1.0,
) -> PipelineRun:
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=_uid(),
        vertical_id=vertical_id,
        trace_id=_uid(),
        pipeline_name=pipeline_name,
        engine_version="1.0.0",
        status=status,
        overall_confidence_label=overall_confidence_label,
        overall_confidence_score=overall_confidence_score,
        started_at=created_at,
        completed_at=created_at,
        created_at=created_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Response envelope — pipelines
# ---------------------------------------------------------------------------


class TestPipelinesEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"scope_type", "window_days", "lookback_days", "total", "items"}

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["scope_type"] == "pipeline"

    def test_default_window_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["window_days"] == 7

    def test_default_lookback_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["lookback_days"] == 30

    def test_total_matches_items_length(self, client, db, api_auth):
        body = client.get(PIPELINES_URL, headers=api_auth).json()
        assert body["total"] == len(body["items"])

    def test_empty_db_returns_empty_items(self, client, db, api_auth):
        tid = _uid()
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["items"] == []
        assert body["total"] == 0


# ---------------------------------------------------------------------------
# Response envelope — verticals
# ---------------------------------------------------------------------------


class TestVerticalsEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"scope_type", "window_days", "lookback_days", "total", "items"}

    def test_scope_type_is_vertical(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, headers=api_auth)
        assert resp.json()["scope_type"] == "vertical"


# ---------------------------------------------------------------------------
# Item shape
# ---------------------------------------------------------------------------


class TestItemShape:
    def test_item_top_level_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="shape_pipe", vertical_id="shape_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["total"] >= 1
        item = body["items"][0]
        assert set(item.keys()) == {"scope", "scope_id", "proposed_changes", "summary"}

    def test_item_scope_matches_scope_type(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="scope_pipe", vertical_id="scope_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["items"][0]["scope"] == "pipeline"

    def test_item_summary_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="sum_pipe", vertical_id="sum_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert isinstance(body["items"][0]["summary"], str)

    def test_proposed_changes_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="list_pipe", vertical_id="list_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert isinstance(body["items"][0]["proposed_changes"], list)

    def test_change_object_has_required_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="keys_pipe", vertical_id="keys_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        assert len(changes) >= 1
        required = {
            "change_id", "category", "title", "change_type", "target",
            "proposed_change", "reason", "expected_effect", "preconditions",
            "approval_intent", "rollback_hint", "evidence", "status",
        }
        assert required.issubset(set(changes[0].keys()))

    def test_all_changes_have_status_proposal_only(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="status_pipe", vertical_id="status_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        for change in changes:
            assert change["status"] == "proposal_only"

    def test_approval_intent_block_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="ai_pipe", vertical_id="ai_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        for change in changes:
            ai = change["approval_intent"]
            assert "requires_human_review" in ai
            assert "risk_level" in ai
            assert "approval_type" in ai

    def test_rollback_hint_present_for_non_no_action(self, client, db, api_auth):
        tid = _uid()
        # Create multiple FAILED runs to raise health pressure and trigger suggestions
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="FAILED",
                      pipeline_name="rh_pipe", vertical_id="rh_vert", days_ago=1.0)
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        for change in changes:
            if change["change_type"] != "no_action_proposed":
                assert isinstance(change["rollback_hint"], list)


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------


class TestLimitParameter:
    def test_limit_caps_items(self, client, db, api_auth):
        tid = _uid()
        for i in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=f"lim_pipe_{i}", vertical_id=f"lim_vert_{i}")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}&limit=1", headers=api_auth).json()
        assert len(body["items"]) <= 1

    def test_limit_invalid_returns_422(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?limit=0", headers=api_auth)
        assert resp.status_code == 422

    def test_limit_too_large_returns_422(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?limit=101", headers=api_auth)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_a_does_not_see_tenant_b_data(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="iso_pipe_a", vertical_id="iso_vert_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="iso_pipe_b", vertical_id="iso_vert_b")

        body_a = client.get(f"{PIPELINES_URL}?tenant_id={tid_a}", headers=api_auth).json()
        scope_ids_a = {item["scope_id"] for item in body_a["items"]}
        assert "iso_pipe_b" not in scope_ids_a

    def test_unknown_tenant_returns_empty(self, client, db, api_auth):
        body = client.get(f"{PIPELINES_URL}?tenant_id={_uid()}", headers=api_auth).json()
        assert body["items"] == []


# ---------------------------------------------------------------------------
# change_id stability
# ---------------------------------------------------------------------------


class TestChangeIdStability:
    def test_change_id_contains_scope_and_pipeline_name(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="cid_pipe", vertical_id="cid_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        for change in changes:
            assert "pipeline" in change["change_id"]
            assert "cid_pipe" in change["change_id"]

    def test_change_ids_are_unique_within_scope(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="uid_pipe", vertical_id="uid_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        ids = [c["change_id"] for c in changes]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Review state enrichment
# ---------------------------------------------------------------------------

STATE_URL = "/api/proposed-change-state"


class TestReviewStateEnrichment:
    def test_each_change_has_review_state(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="rs_pipe", vertical_id="rs_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        assert len(changes) >= 1
        for change in changes:
            assert "review_state" in change

    def test_default_review_state_is_pending_not_persisted(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="rs_default_pipe", vertical_id="rs_default_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        for change in changes:
            rs = change["review_state"]
            assert rs["status"] == "pending"
            assert rs["persisted"] is False
            assert rs["note"] is None
            assert rs["updated_at"] is None

    def test_persisted_review_state_reflected_in_proposed_changes(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="rs_persist_pipe", vertical_id="rs_persist_vert")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        changes = body["items"][0]["proposed_changes"]
        assert len(changes) >= 1

        # Persist a state for the first change
        first_change = changes[0]
        state_payload = {
            "tenant_id": tid,
            "change_id": first_change["change_id"],
            "scope_type": first_change["target"]["scope_type"],
            "scope_id": first_change["target"]["scope_id"],
            "category": first_change["category"],
            "change_type": first_change["change_type"],
            "title": first_change["title"],
            "status": "approved",
            "note": "approved by ops",
            "proposal_payload": None,
        }
        client.post(STATE_URL, json=state_payload, headers=api_auth)

        # Re-fetch and verify review_state is enriched
        body2 = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        all_changes = body2["items"][0]["proposed_changes"]
        enriched = {c["change_id"]: c["review_state"] for c in all_changes}

        assert enriched[first_change["change_id"]]["status"] == "approved"
        assert enriched[first_change["change_id"]]["note"] == "approved by ops"
        assert enriched[first_change["change_id"]]["persisted"] is True

    def test_no_tenant_id_returns_default_review_states(self, client, db, api_auth):
        # Without tenant_id filter, review_state should still be present but all defaults
        body = client.get(PIPELINES_URL, headers=api_auth).json()
        for item in body["items"]:
            for change in item["proposed_changes"]:
                assert "review_state" in change
                assert change["review_state"]["persisted"] is False
