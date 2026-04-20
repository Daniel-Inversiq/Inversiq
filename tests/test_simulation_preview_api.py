"""
tests/test_simulation_preview_api.py

API-level tests for:
  - GET /api/simulation-preview/pipelines
  - GET /api/simulation-preview/verticals

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

PIPELINES_URL = "/api/simulation-preview/pipelines"
VERTICALS_URL = "/api/simulation-preview/verticals"


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
# Envelope shape — pipelines
# ---------------------------------------------------------------------------


class TestPipelinesEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"scope_type", "window_days", "lookback_days", "total", "items"}

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["scope_type"] == "pipeline"

    def test_total_matches_items_length(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_a")
        _make_run(db, tenant_id=tid, pipeline_name="pipe_b")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["total"] == len(data["items"])

    def test_empty_tenant_returns_empty_items(self, client, api_auth):
        data = client.get(PIPELINES_URL, params={"tenant_id": _uid()}, headers=api_auth).json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_default_window_days(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["window_days"] == 7

    def test_custom_window_days_reflected(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(
            PIPELINES_URL, params={"tenant_id": tid, "window_days": 14}, headers=api_auth
        ).json()
        assert data["window_days"] == 14


# ---------------------------------------------------------------------------
# Item shape — pipelines
# ---------------------------------------------------------------------------


class TestPipelinesItemShape:
    def test_item_top_level_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        item = data["items"][0]
        assert set(item.keys()) == {"scope", "scope_id", "previews", "summary"}

    def test_item_scope_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_x")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope"] == "pipeline"

    def test_item_scope_id_matches_pipeline_name(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="named_pipe")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope_id"] == "named_pipe"

    def test_previews_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert isinstance(data["items"][0]["previews"], list)

    def test_summary_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert isinstance(data["items"][0]["summary"], str)

    def test_preview_item_keys_when_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        previews = data["items"][0]["previews"]
        if previews:
            p = previews[0]
            assert "category" in p
            assert "action" in p
            assert "simulation_summary" in p
            assert "expected_impacts" in p
            assert "risks" in p
            assert "assumptions" in p
            assert "safety_checks" in p
            assert "confidence" in p


# ---------------------------------------------------------------------------
# Limit parameter — pipelines
# ---------------------------------------------------------------------------


class TestPipelinesLimit:
    def test_limit_restricts_items(self, client, db, api_auth):
        tid = _uid()
        for i in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=f"pipe_{i}")
        data = client.get(
            PIPELINES_URL, params={"tenant_id": tid, "limit": 2}, headers=api_auth
        ).json()
        assert len(data["items"]) <= 2

    def test_total_reflects_limited_count(self, client, db, api_auth):
        tid = _uid()
        for i in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=f"lim_pipe_{i}")
        data = client.get(
            PIPELINES_URL, params={"tenant_id": tid, "limit": 1}, headers=api_auth
        ).json()
        assert data["total"] == len(data["items"])


# ---------------------------------------------------------------------------
# Envelope shape — verticals
# ---------------------------------------------------------------------------


class TestVerticalsEnvelope:
    def test_top_level_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_a")
        resp = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"scope_type", "window_days", "lookback_days", "total", "items"}

    def test_scope_type_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_b")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["scope_type"] == "vertical"

    def test_item_scope_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_c")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope"] == "vertical"

    def test_item_scope_id_matches_vertical_id(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="named_vert")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope_id"] == "named_vert"

    def test_empty_tenant_returns_empty_items(self, client, api_auth):
        data = client.get(VERTICALS_URL, params={"tenant_id": _uid()}, headers=api_auth).json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_total_matches_items_length(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="v1")
        _make_run(db, tenant_id=tid, vertical_id="v2")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["total"] == len(data["items"])


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_pipeline_results_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_b")
        data_a = client.get(
            PIPELINES_URL, params={"tenant_id": tid_a}, headers=api_auth
        ).json()
        scope_ids = [i["scope_id"] for i in data_a["items"]]
        assert "pipe_a" in scope_ids
        assert "pipe_b" not in scope_ids

    def test_vertical_results_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, vertical_id="vert_x")
        _make_run(db, tenant_id=tid_b, vertical_id="vert_y")
        data_a = client.get(
            VERTICALS_URL, params={"tenant_id": tid_a}, headers=api_auth
        ).json()
        scope_ids = [i["scope_id"] for i in data_a["items"]]
        assert "vert_x" in scope_ids
        assert "vert_y" not in scope_ids
