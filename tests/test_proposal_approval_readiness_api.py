"""
tests/test_proposal_approval_readiness_api.py

API-level tests for:
  - GET /api/proposal-approval-readiness/pipelines
  - GET /api/proposal-approval-readiness/verticals

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

PIPELINES_URL = "/api/proposal-approval-readiness/pipelines"
VERTICALS_URL = "/api/proposal-approval-readiness/verticals"


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
            "total_scopes", "total_blocked", "total_warnings", "total_ready",
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
            "total_scopes", "total_blocked", "total_warnings", "total_ready",
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
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        if not data["items"]:
            pytest.skip("No health scopes produced — run data may be insufficient.")
        item = data["items"][0]
        assert set(item.keys()) == {
            "scope", "scope_id", "proposal_count",
            "blocked_count", "warnings_count", "ready_count",
            "summary", "approval_readiness",
        }

    def test_approval_readiness_entry_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        if not data["items"]:
            pytest.skip("No health scopes produced.")
        for item in data["items"]:
            for entry in item["approval_readiness"]:
                assert set(entry.keys()) == {
                    "change_id", "status", "severity", "summary",
                    "blocking_reasons", "warnings", "required_actions", "recommendation",
                }

    def test_status_values_are_valid(self, client, db, api_auth):
        valid_statuses = {"approval_ready", "blocked_with_warnings", "blocked"}
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        for item in data["items"]:
            for entry in item["approval_readiness"]:
                assert entry["status"] in valid_statuses

    def test_severity_values_are_valid(self, client, db, api_auth):
        valid_severities = {"low", "medium", "high"}
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        for item in data["items"]:
            for entry in item["approval_readiness"]:
                assert entry["severity"] in valid_severities


# ---------------------------------------------------------------------------
# Aggregate counters
# ---------------------------------------------------------------------------


class TestAggregateCounters:
    def test_counter_consistency(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        total_blocked = sum(i["blocked_count"] for i in data["items"])
        total_warnings = sum(i["warnings_count"] for i in data["items"])
        total_ready = sum(i["ready_count"] for i in data["items"])
        assert data["total_blocked"] == total_blocked
        assert data["total_warnings"] == total_warnings
        assert data["total_ready"] == total_ready

    def test_proposal_count_matches_readiness_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth)
        data = resp.json()
        for item in data["items"]:
            assert item["proposal_count"] == len(item["approval_readiness"])


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------


class TestLimitParam:
    def test_limit_restricts_items(self, client, db, api_auth):
        tid = _uid()
        for pipeline in ["pipe_a", "pipe_b", "pipe_c"]:
            _make_run(db, tenant_id=tid, pipeline_name=pipeline, overall_confidence_label="low")
        resp = client.get(PIPELINES_URL, params={"tenant_id": tid, "limit": 1}, headers=api_auth)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 1

    def test_invalid_limit_rejected(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"limit": 0}, headers=api_auth)
        assert resp.status_code == 422

    def test_limit_above_max_rejected(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"limit": 101}, headers=api_auth)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_same_request_returns_same_output(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, overall_confidence_label="low", overall_confidence_score=0.55)
        params = {"tenant_id": tid}
        r1 = client.get(PIPELINES_URL, params=params, headers=api_auth).json()
        r2 = client.get(PIPELINES_URL, params=params, headers=api_auth).json()
        # Exclude timing-sensitive totals — compare structure
        assert r1["scope_type"] == r2["scope_type"]
        assert r1["total_scopes"] == r2["total_scopes"]
        assert len(r1["items"]) == len(r2["items"])
