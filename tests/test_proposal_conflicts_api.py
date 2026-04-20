"""
tests/test_proposal_conflicts_api.py

API-level tests for:
  - GET /api/proposal-conflicts/pipelines
  - GET /api/proposal-conflicts/verticals

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

PIPELINES_URL = "/api/proposal-conflicts/pipelines"
VERTICALS_URL = "/api/proposal-conflicts/verticals"


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
        assert set(body.keys()) == {
            "scope_type", "window_days", "lookback_days",
            "total_scopes", "total_conflicts", "items",
        }

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["scope_type"] == "pipeline"

    def test_default_window_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["window_days"] == 7

    def test_default_lookback_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["lookback_days"] == 30

    def test_total_scopes_matches_items_length(self, client, db, api_auth):
        body = client.get(PIPELINES_URL, headers=api_auth).json()
        assert body["total_scopes"] == len(body["items"])

    def test_empty_tenant_returns_empty_items(self, client, db, api_auth):
        tid = _uid()
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["items"] == []
        assert body["total_scopes"] == 0
        assert body["total_conflicts"] == 0


# ---------------------------------------------------------------------------
# Response envelope — verticals
# ---------------------------------------------------------------------------


class TestVerticalsEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "scope_type", "window_days", "lookback_days",
            "total_scopes", "total_conflicts", "items",
        }

    def test_scope_type_is_vertical(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, headers=api_auth)
        assert resp.json()["scope_type"] == "vertical"

    def test_empty_tenant_returns_empty_items(self, client, db, api_auth):
        tid = _uid()
        body = client.get(f"{VERTICALS_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["items"] == []
        assert body["total_scopes"] == 0
        assert body["total_conflicts"] == 0


# ---------------------------------------------------------------------------
# Item shape
# ---------------------------------------------------------------------------


class TestItemShape:
    def test_item_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_shape")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert len(body["items"]) >= 1
        item = body["items"][0]
        for key in ("scope", "scope_id", "proposal_count", "conflict_count", "summary", "conflicts"):
            assert key in item, f"Missing key: {key}"

    def test_conflicts_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_clist")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        item = body["items"][0]
        assert isinstance(item["conflicts"], list)

    def test_conflict_count_matches_conflicts_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_ccount")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        for item in body["items"]:
            assert item["conflict_count"] == len(item["conflicts"])

    def test_total_conflicts_is_sum_of_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_sum")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        expected = sum(i["conflict_count"] for i in body["items"])
        assert body["total_conflicts"] == expected


# ---------------------------------------------------------------------------
# Conflict object shape (when a conflict is present)
# ---------------------------------------------------------------------------


class TestConflictObjectShape:
    def test_conflict_object_keys(self, client, db, api_auth):
        """Verify the shape of a conflict object if any exist in the response."""
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_obj_shape")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        all_conflicts = [c for item in body["items"] for c in item["conflicts"]]
        if not all_conflicts:
            pytest.skip("No conflicts generated for this data set — shape test skipped.")
        conflict = all_conflicts[0]
        for key in ("conflict_id", "conflict_type", "severity", "proposal_ids", "target", "summary", "reason", "recommendation"):
            assert key in conflict, f"Missing key in conflict object: {key}"


# ---------------------------------------------------------------------------
# Query params
# ---------------------------------------------------------------------------


class TestQueryParams:
    def test_limit_respected(self, client, db, api_auth):
        for i in range(3):
            tid_shared = "shared_limit_tenant"
            _make_run(db, tenant_id=tid_shared, pipeline_name=f"pipe_limit_{i}")
        body = client.get(f"{PIPELINES_URL}?limit=1", headers=api_auth).json()
        assert len(body["items"]) <= 1

    def test_window_days_reflected(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?window_days=14", headers=api_auth)
        assert resp.json()["window_days"] == 14

    def test_lookback_days_reflected(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?lookback_days=60", headers=api_auth)
        assert resp.json()["lookback_days"] == 60

    def test_invalid_window_days_rejected(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?window_days=0", headers=api_auth)
        assert resp.status_code == 422

    def test_invalid_limit_rejected(self, client, db, api_auth):
        resp = client.get(f"{PIPELINES_URL}?limit=0", headers=api_auth)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_filter_isolates_results(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_iso_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_iso_b")

        body_a = client.get(f"{PIPELINES_URL}?tenant_id={tid_a}", headers=api_auth).json()
        body_b = client.get(f"{PIPELINES_URL}?tenant_id={tid_b}", headers=api_auth).json()

        scope_ids_a = {i["scope_id"] for i in body_a["items"]}
        scope_ids_b = {i["scope_id"] for i in body_b["items"]}
        assert scope_ids_a.isdisjoint(scope_ids_b)
