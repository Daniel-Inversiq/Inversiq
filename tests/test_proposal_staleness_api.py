"""
tests/test_proposal_staleness_api.py

API-level tests for:
  - GET /api/proposal-staleness/pipelines
  - GET /api/proposal-staleness/verticals

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

PIPELINES_URL = "/api/proposal-staleness/pipelines"
VERTICALS_URL = "/api/proposal-staleness/verticals"


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
            "total_scopes", "total_stale", "total_aging", "items",
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
        assert body["total_stale"] == 0
        assert body["total_aging"] == 0

    def test_total_stale_is_sum_of_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_stale_sum")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        expected = sum(i["stale_count"] for i in body["items"])
        assert body["total_stale"] == expected

    def test_total_aging_is_sum_of_items(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_aging_sum")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        expected = sum(i["aging_count"] for i in body["items"])
        assert body["total_aging"] == expected


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
            "total_scopes", "total_stale", "total_aging", "items",
        }

    def test_scope_type_is_vertical(self, client, db, api_auth):
        resp = client.get(VERTICALS_URL, headers=api_auth)
        assert resp.json()["scope_type"] == "vertical"

    def test_empty_tenant_returns_empty_items(self, client, db, api_auth):
        tid = _uid()
        body = client.get(f"{VERTICALS_URL}?tenant_id={tid}", headers=api_auth).json()
        assert body["items"] == []
        assert body["total_scopes"] == 0


# ---------------------------------------------------------------------------
# Item shape
# ---------------------------------------------------------------------------


class TestItemShape:
    def test_item_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_shape_stale")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        assert len(body["items"]) >= 1
        item = body["items"][0]
        for key in ("scope", "scope_id", "proposal_count", "stale_count", "aging_count", "summary", "staleness"):
            assert key in item, f"Missing key: {key}"

    def test_staleness_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_slist")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        item = body["items"][0]
        assert isinstance(item["staleness"], list)

    def test_staleness_count_matches_proposal_count(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_count_match")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        for item in body["items"]:
            assert len(item["staleness"]) == item["proposal_count"]

    def test_stale_count_matches_annotations(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_stale_match")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        for item in body["items"]:
            computed = sum(1 for a in item["staleness"] if a["status"] == "stale")
            assert item["stale_count"] == computed

    def test_aging_count_matches_annotations(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_aging_match")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        for item in body["items"]:
            computed = sum(1 for a in item["staleness"] if a["status"] == "aging")
            assert item["aging_count"] == computed


# ---------------------------------------------------------------------------
# Annotation object shape
# ---------------------------------------------------------------------------


class TestAnnotationShape:
    def test_annotation_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_ann_shape")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        all_annotations = [a for item in body["items"] for a in item["staleness"]]
        if not all_annotations:
            pytest.skip("No proposals generated for this data set — shape test skipped.")
        ann = all_annotations[0]
        for key in ("change_id", "status", "severity", "summary", "reason", "signals", "recommendation"):
            assert key in ann, f"Missing key in annotation: {key}"

    def test_annotation_status_values(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_status_vals")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        valid = {"fresh", "aging", "stale", "superseded"}
        for item in body["items"]:
            for ann in item["staleness"]:
                assert ann["status"] in valid, f"Unexpected status: {ann['status']}"

    def test_annotation_severity_values(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_sev_vals")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        valid = {"low", "medium", "high"}
        for item in body["items"]:
            for ann in item["staleness"]:
                assert ann["severity"] in valid, f"Unexpected severity: {ann['severity']}"

    def test_annotation_signals_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_sig_list")
        body = client.get(f"{PIPELINES_URL}?tenant_id={tid}", headers=api_auth).json()
        for item in body["items"]:
            for ann in item["staleness"]:
                assert isinstance(ann["signals"], list)


# ---------------------------------------------------------------------------
# Query params
# ---------------------------------------------------------------------------


class TestQueryParams:
    def test_limit_respected(self, client, db, api_auth):
        for i in range(3):
            _make_run(db, tenant_id="shared_stale_limit", pipeline_name=f"pipe_sl_{i}")
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
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_stale_iso_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_stale_iso_b")

        body_a = client.get(f"{PIPELINES_URL}?tenant_id={tid_a}", headers=api_auth).json()
        body_b = client.get(f"{PIPELINES_URL}?tenant_id={tid_b}", headers=api_auth).json()

        scope_ids_a = {i["scope_id"] for i in body_a["items"]}
        scope_ids_b = {i["scope_id"] for i in body_b["items"]}
        assert scope_ids_a.isdisjoint(scope_ids_b)

    def test_no_review_states_without_tenant_id(self, client, db, api_auth):
        # Without tenant_id, review states are not loaded — all proposals should be fresh
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_no_rs")
        body = client.get(PIPELINES_URL, headers=api_auth).json()
        # No persisted review states without tenant_id, so all annotations should be fresh
        for item in body["items"]:
            for ann in item["staleness"]:
                assert ann["status"] == "fresh"
