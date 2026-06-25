"""
tests/test_health.py

Tests for GET /api/health/pipelines and GET /api/health/verticals.

Design notes
------------
- Uses the shared session-scoped SQLite DB (same conftest.py pattern).
- Each test class uses a unique tenant_id via _uid() to prevent pollution.
- Runs are created directly via the db fixture (no steps needed for these
  aggregate metrics).
- Basic-Auth uses empty credentials (matches conftest defaults).

Scenarios covered
-----------------

Response envelope
  - Empty tenant returns total=0, items=[]
  - Required envelope keys present
  - summary counts sum to total

Pipeline health_status classification
  - healthy: all rates below watch thresholds
  - watch: failed_rate >= WATCH_FAILED_RATE (0.10)
  - watch: needs_review_rate >= WATCH_NEEDS_REVIEW_RATE (0.20)
  - watch: low_confidence_rate >= WATCH_LOW_CONFIDENCE_RATE (0.30)
  - unhealthy: failed_rate >= UNHEALTHY_FAILED_RATE (0.30)
  - unhealthy: needs_review_rate >= UNHEALTHY_NEEDS_REVIEW_RATE (0.40)
  - unhealthy: low_confidence_rate >= UNHEALTHY_LOW_CONFIDENCE_RATE (0.50)

Vertical health
  - Groups by vertical_id, pipeline_count is accurate
  - health_status aggregated across all pipelines in vertical

Item shape
  - Pipeline: all required fields present and correct types
  - Vertical: all required fields present and correct types

Top recommendation
  - High failed_rate → failure investigation message
  - Healthy run → "No action needed"

Ordering
  - unhealthy before watch before healthy

Tenant isolation
  - tenant_id scoping works for both endpoints
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest

from app.models.pipeline_run import PipelineRun

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PIPELINE_URL = "/api/health/pipelines"
VERTICAL_URL = "/api/health/verticals"


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
    pipeline_name: str = "test_pipeline",
    vertical_id: str = "test_vertical",
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=_uid(),
        vertical_id=vertical_id,
        trace_id=_uid(),
        pipeline_name=pipeline_name,
        engine_version="1.0.0",
        status=status,
        overall_confidence_label=overall_confidence_label,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Envelope — pipelines
# ---------------------------------------------------------------------------

class TestPipelineEnvelope:
    def test_empty_tenant_returns_empty(self, client, db, api_auth):
        tid = _uid()
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_envelope_keys_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert set(body.keys()) >= {"total", "lookback_days", "summary", "items"}

    def test_summary_counts_sum_to_total(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="COMPLETED")
        _make_run(db, tenant_id=tid, status="FAILED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        s = body["summary"]
        assert s["healthy"] + s["watch"] + s["unhealthy"] == body["total"]


# ---------------------------------------------------------------------------
# Pipeline health_status classification
# ---------------------------------------------------------------------------

class TestPipelineHealthStatus:
    # All runs COMPLETED, no bad confidence → healthy
    def test_healthy_when_all_good(self, client, db, api_auth):
        tid = _uid()
        for _ in range(10):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "healthy"
        assert item["failed_rate"] == 0.0
        assert item["needs_review_rate"] == 0.0

    # 1/10 failed → 10% = WATCH threshold exactly → watch
    def test_watch_on_failed_rate_at_threshold(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED")
        for _ in range(9):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "watch"
        assert item["failed_rate"] == pytest.approx(0.1)

    # 2/10 needs_review → 20% = WATCH threshold → watch
    def test_watch_on_needs_review_rate(self, client, db, api_auth):
        tid = _uid()
        for _ in range(2):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        for _ in range(8):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "watch"
        assert item["needs_review_rate"] == pytest.approx(0.2)

    # 3/10 low confidence → 30% = WATCH threshold → watch
    def test_watch_on_low_confidence_rate(self, client, db, api_auth):
        tid = _uid()
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_label="low")
        for _ in range(7):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "watch"
        assert item["low_confidence_rate"] == pytest.approx(0.3)

    # 3/10 failed → 30% = UNHEALTHY threshold → unhealthy
    def test_unhealthy_on_failed_rate(self, client, db, api_auth):
        tid = _uid()
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="FAILED")
        for _ in range(7):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "unhealthy"

    # 4/10 needs_review → 40% = UNHEALTHY threshold → unhealthy
    def test_unhealthy_on_needs_review_rate(self, client, db, api_auth):
        tid = _uid()
        for _ in range(4):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        for _ in range(6):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "unhealthy"

    # 5/10 low confidence → 50% = UNHEALTHY threshold → unhealthy
    def test_unhealthy_on_low_confidence_rate(self, client, db, api_auth):
        tid = _uid()
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_label="low")
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "unhealthy"

    # Just below watch threshold → healthy
    def test_below_watch_threshold_is_healthy(self, client, db, api_auth):
        tid = _uid()
        # 9% failed (1/11) — below 10%
        _make_run(db, tenant_id=tid, status="FAILED")
        for _ in range(10):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "healthy"


# ---------------------------------------------------------------------------
# Pipeline item shape
# ---------------------------------------------------------------------------

class TestPipelineItemShape:
    REQUIRED_KEYS = {
        "pipeline_name", "vertical_id", "tenant_id", "total_runs",
        "failed_rate", "needs_review_rate", "low_confidence_rate",
        "signal_counts", "health_status", "top_recommendation",
        "lookback_days", "computed_at",
    }

    def test_all_required_fields_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert self.REQUIRED_KEYS.issubset(set(item.keys()))

    def test_rates_between_zero_and_one(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED")
        _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        for field in ("failed_rate", "needs_review_rate", "low_confidence_rate"):
            assert 0.0 <= item[field] <= 1.0

    def test_total_runs_matches_created(self, client, db, api_auth):
        tid = _uid()
        for _ in range(5):
            _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["total_runs"] == 5

    def test_signal_counts_is_dict(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["signal_counts"], dict)

    def test_computed_at_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["computed_at"], str)

    def test_lookback_days_reflected(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "lookback_days": 7}, headers=api_auth
        )
        body = resp.json()
        assert body["lookback_days"] == 7
        assert body["items"][0]["lookback_days"] == 7

    def test_vertical_id_from_run(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["vertical_id"] == "construction"


# ---------------------------------------------------------------------------
# Top recommendation
# ---------------------------------------------------------------------------

class TestTopRecommendation:
    def test_healthy_returns_no_action(self, client, db, api_auth):
        tid = _uid()
        for _ in range(10):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["top_recommendation"].startswith("No action needed")

    def test_high_failed_rate_returns_failure_message(self, client, db, api_auth):
        tid = _uid()
        for _ in range(4):
            _make_run(db, tenant_id=tid, status="FAILED")
        for _ in range(6):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert "failure" in item["top_recommendation"].lower() or "fail" in item["top_recommendation"].lower()

    def test_high_needs_review_rate_returns_review_message(self, client, db, api_auth):
        tid = _uid()
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        for _ in range(7):
            _make_run(db, tenant_id=tid, status="COMPLETED")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert "review" in item["top_recommendation"].lower()


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

class TestPipelineOrdering:
    def test_unhealthy_before_watch_before_healthy(self, client, db, api_auth):
        tid = _uid()

        # Pipeline A: healthy (all completed)
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="COMPLETED", pipeline_name="pipeline_a")

        # Pipeline B: watch (10% failed: 1/10)
        _make_run(db, tenant_id=tid, status="FAILED", pipeline_name="pipeline_b")
        for _ in range(9):
            _make_run(db, tenant_id=tid, status="COMPLETED", pipeline_name="pipeline_b")

        # Pipeline C: unhealthy (30% failed: 3/10)
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="FAILED", pipeline_name="pipeline_c")
        for _ in range(7):
            _make_run(db, tenant_id=tid, status="COMPLETED", pipeline_name="pipeline_c")

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        statuses = [i["health_status"] for i in items]

        # unhealthy must come before watch, watch before healthy
        unhealthy_idx = statuses.index("unhealthy")
        watch_idx = statuses.index("watch")
        healthy_idx = statuses.index("healthy")
        assert unhealthy_idx < watch_idx < healthy_idx


# ---------------------------------------------------------------------------
# Tenant isolation — pipelines
# ---------------------------------------------------------------------------

class TestPipelineTenantIsolation:
    def test_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_a")
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_b")

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid_a}, headers=api_auth)
        items = resp.json()["items"]
        assert all(i["pipeline_name"] == "pipe_a" for i in items)
        assert len(items) == 1

    def test_multiple_pipelines_same_tenant(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_x")
        _make_run(db, tenant_id=tid, pipeline_name="pipe_y")
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Envelope — verticals
# ---------------------------------------------------------------------------

class TestVerticalEnvelope:
    def test_empty_tenant_returns_empty(self, client, db, api_auth):
        tid = _uid()
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_envelope_keys_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert set(body.keys()) >= {"total", "lookback_days", "summary", "items"}

    def test_summary_counts_sum_to_total(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="v1")
        _make_run(db, tenant_id=tid, vertical_id="v2")
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        s = body["summary"]
        assert s["healthy"] + s["watch"] + s["unhealthy"] == body["total"]


# ---------------------------------------------------------------------------
# Vertical grouping
# ---------------------------------------------------------------------------

class TestVerticalGrouping:
    def test_groups_by_vertical_id(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction")
        _make_run(db, tenant_id=tid, vertical_id="roofing")
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 2
        vids = {i["vertical_id"] for i in body["items"]}
        assert vids == {"construction", "roofing"}

    def test_pipeline_count_is_accurate(self, client, db, api_auth):
        tid = _uid()
        # 2 distinct pipelines, same vertical
        _make_run(db, tenant_id=tid, vertical_id="construction", pipeline_name="pipe_alpha")
        _make_run(db, tenant_id=tid, vertical_id="construction", pipeline_name="pipe_beta")
        _make_run(db, tenant_id=tid, vertical_id="construction", pipeline_name="pipe_alpha")
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["pipeline_count"] == 2

    def test_vertical_health_status_reflects_runs(self, client, db, api_auth):
        tid = _uid()
        # 30% failed within the vertical → unhealthy
        for _ in range(3):
            _make_run(db, tenant_id=tid, vertical_id="construction", status="FAILED")
        for _ in range(7):
            _make_run(db, tenant_id=tid, vertical_id="construction", status="COMPLETED")
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] == "unhealthy"


# ---------------------------------------------------------------------------
# Vertical item shape
# ---------------------------------------------------------------------------

class TestVerticalItemShape:
    REQUIRED_KEYS = {
        "vertical_id", "tenant_id", "total_runs", "pipeline_count",
        "failed_rate", "needs_review_rate", "low_confidence_rate",
        "signal_counts", "health_status", "top_recommendation",
        "lookback_days", "computed_at",
    }

    def test_all_required_fields_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert self.REQUIRED_KEYS.issubset(set(item.keys()))
