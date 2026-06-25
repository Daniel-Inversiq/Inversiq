"""
tests/test_control_suggestions_api.py

API-level tests for:
  - GET /api/control-suggestions/pipelines
  - GET /api/control-suggestions/verticals

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

PIPELINES_URL = "/api/control-suggestions/pipelines"
VERTICALS_URL = "/api/control-suggestions/verticals"


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
# Response shape — pipelines
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
        data = client.get(PIPELINES_URL, params={"tenant_id": tid, "window_days": 14}, headers=api_auth).json()
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
        assert set(item.keys()) == {"scope", "scope_id", "suggestions", "summary"}

    def test_item_scope_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_x")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope"] == "pipeline"

    def test_item_scope_id_matches_pipeline_name(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="my_unique_pipe")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope_id"] == "my_unique_pipe"

    def test_suggestions_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert isinstance(data["items"][0]["suggestions"], list)

    def test_suggestions_non_empty(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert len(data["items"][0]["suggestions"]) >= 1

    def test_suggestion_item_has_required_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        s = data["items"][0]["suggestions"][0]
        assert "category" in s
        assert "action" in s
        assert "reason" in s
        assert "expected_effect" in s
        assert "guardrails" in s
        assert "confidence" in s

    def test_summary_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert isinstance(data["items"][0]["summary"], str)


# ---------------------------------------------------------------------------
# Response shape — verticals
# ---------------------------------------------------------------------------


class TestVerticalsEnvelope:
    def test_scope_type_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_a")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["scope_type"] == "vertical"

    def test_total_matches_items_length(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_a")
        _make_run(db, tenant_id=tid, vertical_id="vert_b")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["total"] == len(data["items"])

    def test_vertical_item_scope_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="vert_z")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope"] == "vertical"

    def test_vertical_item_scope_id_matches(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction_v1")
        data = client.get(VERTICALS_URL, params={"tenant_id": tid}, headers=api_auth).json()
        assert data["items"][0]["scope_id"] == "construction_v1"


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------


class TestLimitParameter:
    def test_limit_caps_items(self, client, db, api_auth):
        tid = _uid()
        for name in ("pipe_1", "pipe_2", "pipe_3"):
            _make_run(db, tenant_id=tid, pipeline_name=name)
        data = client.get(
            PIPELINES_URL, params={"tenant_id": tid, "limit": 2}, headers=api_auth
        ).json()
        assert len(data["items"]) <= 2

    def test_limit_reflected_in_total(self, client, db, api_auth):
        tid = _uid()
        for name in ("lp_1", "lp_2", "lp_3"):
            _make_run(db, tenant_id=tid, pipeline_name=name)
        data = client.get(
            PIPELINES_URL, params={"tenant_id": tid, "limit": 1}, headers=api_auth
        ).json()
        assert data["total"] == len(data["items"])


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_a_does_not_see_tenant_b_pipelines(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_a_only")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_b_only")

        data_a = client.get(PIPELINES_URL, params={"tenant_id": tid_a}, headers=api_auth).json()
        scope_ids_a = {item["scope_id"] for item in data_a["items"]}
        assert "pipe_b_only" not in scope_ids_a

    def test_tenant_a_does_not_see_tenant_b_verticals(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, vertical_id="vert_a_only")
        _make_run(db, tenant_id=tid_b, vertical_id="vert_b_only")

        data_a = client.get(VERTICALS_URL, params={"tenant_id": tid_a}, headers=api_auth).json()
        scope_ids_a = {item["scope_id"] for item in data_a["items"]}
        assert "vert_b_only" not in scope_ids_a


# ---------------------------------------------------------------------------
# Category inference — verify real data triggers expected suggestions
# ---------------------------------------------------------------------------


class TestCategoryInference:
    def test_many_review_runs_in_current_window_yields_suggestion(self, client, db, api_auth):
        tid = _uid()
        pipe = f"high_review_{_uid()}"
        # Current window: many NEEDS_REVIEW runs
        for _ in range(8):
            _make_run(db, tenant_id=tid, pipeline_name=pipe, status="NEEDS_REVIEW", days_ago=2)
        # Previous window: few NEEDS_REVIEW runs
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name=pipe, status="NEEDS_REVIEW", days_ago=10)
        for _ in range(8):
            _make_run(db, tenant_id=tid, pipeline_name=pipe, status="COMPLETED", days_ago=10)

        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        pipe_items = [i for i in data["items"] if i["scope_id"] == pipe]
        assert len(pipe_items) == 1
        cats = [s["category"] for s in pipe_items[0]["suggestions"]]
        # With high review rate + reasoning, expect some advisory suggestion
        assert len(cats) >= 1
        assert cats[0] != ""

    def test_guardrails_always_present_in_every_suggestion(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name=f"pipe_{_uid()}")
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        for item in data["items"]:
            for s in item["suggestions"]:
                assert isinstance(s["guardrails"], list)
                assert len(s["guardrails"]) >= 1

    def test_no_duplicate_categories_per_scope(self, client, db, api_auth):
        tid = _uid()
        pipe = f"dedup_{_uid()}"
        for _ in range(5):
            _make_run(db, tenant_id=tid, pipeline_name=pipe, status="NEEDS_REVIEW", days_ago=2)
        for _ in range(5):
            _make_run(db, tenant_id=tid, pipeline_name=pipe, status="COMPLETED", days_ago=2)
        data = client.get(PIPELINES_URL, params={"tenant_id": tid}, headers=api_auth).json()
        pipe_items = [i for i in data["items"] if i["scope_id"] == pipe]
        if pipe_items:
            cats = [s["category"] for s in pipe_items[0]["suggestions"]]
            assert len(cats) == len(set(cats))


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_window_days_too_low_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"window_days": 0}, headers=api_auth)
        assert resp.status_code == 422

    def test_window_days_too_high_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"window_days": 91}, headers=api_auth)
        assert resp.status_code == 422

    def test_lookback_days_too_low_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"lookback_days": 0}, headers=api_auth)
        assert resp.status_code == 422

    def test_lookback_days_too_high_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"lookback_days": 366}, headers=api_auth)
        assert resp.status_code == 422

    def test_limit_too_low_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"limit": 0}, headers=api_auth)
        assert resp.status_code == 422

    def test_limit_too_high_returns_422(self, client, api_auth):
        resp = client.get(PIPELINES_URL, params={"limit": 101}, headers=api_auth)
        assert resp.status_code == 422
