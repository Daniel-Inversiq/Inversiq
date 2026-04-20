"""
tests/test_reasoning_api.py

API-level tests for the reasoning endpoints:
  - GET /api/reasoning/pipelines
  - GET /api/reasoning/verticals

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

PIPELINES_URL = "/api/reasoning/pipelines"
VERTICALS_URL = "/api/reasoning/verticals"


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
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_pipelines_top_level_shape(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "scope_type" in data
        assert "total" in data
        assert "items" in data
        assert data["scope_type"] == "pipeline"

    def test_verticals_top_level_shape(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="COMPLETED", vertical_id="v_" + _uid())
        resp = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "vertical"
        assert isinstance(data["items"], list)

    def test_item_reasoning_shape(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "scope" in item
        assert "scope_id" in item
        assert "health_status" in item
        assert "reasoning" in item
        assert "summary" in item

    def test_reasoning_item_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        r = resp.json()["items"][0]["reasoning"][0]
        assert set(r.keys()) == {"category", "root_cause", "confidence", "evidence", "recommendations"}

    def test_empty_tenant_returns_empty_items(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"tenant_id": "nonexistent_" + _uid()}, headers=api_auth)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------


class TestLimitParameter:
    def test_limit_reduces_results(self, client, db, api_auth):
        tid = _uid()
        for i in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=f"pipe_{i}_{_uid()}")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid, "limit": 1}, headers=api_auth)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_without_limit_returns_all(self, client, db, api_auth):
        tid = _uid()
        for i in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=f"pipe_{i}_{_uid()}")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_a_not_visible_to_tenant_b(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        pipeline = "pipe_isolation_" + _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name=pipeline)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid_b}, headers=api_auth)
        scope_ids = [item["scope_id"] for item in resp.json()["items"]]
        assert pipeline not in scope_ids


# ---------------------------------------------------------------------------
# Categories returned for known signal patterns
# ---------------------------------------------------------------------------


class TestCategoryInference:
    def test_failed_runs_produce_reasoning(self, client, db, api_auth):
        """Failed runs should produce at least one reasoning item (even mixed_or_unclear)."""
        tid = _uid()
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="FAILED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert len(item["reasoning"]) >= 1

    def test_low_confidence_runs_produce_reasoning(self, client, db, api_auth):
        tid = _uid()
        for _ in range(5):
            _make_run(
                db,
                tenant_id=tid,
                status="COMPLETED",
                overall_confidence_label="low",
                overall_confidence_score=0.3,
            )
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert len(item["reasoning"]) >= 1

    def test_recommendations_are_non_empty(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        for reasoning_item in resp.json()["items"][0]["reasoning"]:
            assert len(reasoning_item["recommendations"]) > 0

    def test_summary_is_non_empty_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["items"][0]["summary"] != ""


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_window_days_too_large_rejected(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"window_days": 9999}, headers=api_auth)
        assert resp.status_code == 422

    def test_lookback_days_too_large_rejected(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"lookback_days": 9999}, headers=api_auth)
        assert resp.status_code == 422

    def test_limit_zero_rejected(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"limit": 0}, headers=api_auth)
        assert resp.status_code == 422

    def test_window_days_echo(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid, "window_days": 14}, headers=api_auth)
        assert resp.json()["window_days"] == 14
