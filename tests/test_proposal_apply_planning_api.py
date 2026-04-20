"""
tests/test_proposal_apply_planning_api.py

API-level tests for:
  - GET /api/proposal-apply-planning/pipelines
  - GET /api/proposal-apply-planning/verticals

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

PIPELINES_URL = "/api/proposal-apply-planning/pipelines"
VERTICALS_URL = "/api/proposal-apply-planning/verticals"


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
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {
            "scope_type", "window_days", "lookback_days",
            "total_scopes", "total_planned", "total_combined", "total_blocked",
            "items",
        }

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["scope_type"] == "pipeline"

    def test_empty_tenant_returns_empty_items(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, params={"tenant_id": _uid()}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total_scopes"] == 0

    def test_default_window_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, headers=api_auth)
        assert resp.json()["window_days"] == 7

    def test_custom_window_days(self, client, db, api_auth):
        resp = client.get(PIPELINES_URL, params={"window_days": 14}, headers=api_auth)
        assert resp.json()["window_days"] == 14


# ---------------------------------------------------------------------------
# Response envelope — verticals
# ---------------------------------------------------------------------------


class TestVerticalsEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {
            "scope_type", "window_days", "lookback_days",
            "total_scopes", "total_planned", "total_combined", "total_blocked",
            "items",
        }

    def test_scope_type_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["scope_type"] == "vertical"

    def test_empty_tenant_returns_empty_items(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, params={"tenant_id": _uid()}, headers=api_auth)
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Item shape
# ---------------------------------------------------------------------------


class TestItemShape:
    def test_item_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        assert len(items) >= 1
        item = items[0]
        assert set(item.keys()) == {
            "scope", "scope_id", "proposal_count",
            "planned_count", "combined_count", "blocked_count",
            "summary", "apply_plans",
        }

    def test_item_scope_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["scope"] == "pipeline"

    def test_apply_plans_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["apply_plans"], list)

    def test_plan_entry_keys_when_plans_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="LOW", overall_confidence_score=0.3)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        plans = [p for item in items for p in item["apply_plans"]]
        if plans:
            plan = plans[0]
            assert "change_id" in plan
            assert "status" in plan
            assert "preflight_checks" in plan
            assert "rollback_plan" in plan
            assert "execution_sequence" in plan
            assert "dependencies" in plan
            assert "blocking_reasons" in plan
            assert "recommendation" in plan


# ---------------------------------------------------------------------------
# limit param
# ---------------------------------------------------------------------------


class TestLimitParam:
    def test_limit_reduces_items(self, client, db, api_auth):
        tid = _uid()
        for pname in ("pipe_a", "pipe_b", "pipe_c"):
            _make_run(db, tenant_id=tid, pipeline_name=pname)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid, "limit": 1}, headers=api_auth)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 1

    def test_no_limit_returns_all(self, client, db, api_auth):
        tid = _uid()
        for pname in ("pipe_x", "pipe_y"):
            _make_run(db, tenant_id=tid, pipeline_name=pname)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 2


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_a_does_not_see_tenant_b_scopes(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_for_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_for_b")

        resp_a = client.get(PIPELINES_URL, params={"tenant_id": tid_a}, headers=api_auth)
        scope_ids_a = {i["scope_id"] for i in resp_a.json()["items"]}
        assert "pipe_for_b" not in scope_ids_a

    def test_no_tenant_returns_all_scopes(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name=f"pipe_{tid_a}")
        _make_run(db, tenant_id=tid_b, pipeline_name=f"pipe_{tid_b}")

        resp = client.get(PIPELINES_URL, headers=api_auth)
        scope_ids = {i["scope_id"] for i in resp.json()["items"]}
        assert f"pipe_{tid_a}" in scope_ids
        assert f"pipe_{tid_b}" in scope_ids


# ---------------------------------------------------------------------------
# Aggregate totals
# ---------------------------------------------------------------------------


class TestAggregateTotals:
    def test_total_planned_matches_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        computed = sum(i["planned_count"] for i in data["items"])
        assert data["total_planned"] == computed

    def test_total_blocked_matches_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        computed = sum(i["blocked_count"] for i in data["items"])
        assert data["total_blocked"] == computed

    def test_total_combined_matches_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        computed = sum(i["combined_count"] for i in data["items"])
        assert data["total_combined"] == computed
