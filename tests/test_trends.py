"""
tests/test_trends.py

Tests for the Trend Intelligence layer:
  - app/services/trend_engine.py       (unit, no DB)
  - app/services/trend_recommendations.py  (unit, no DB)
  - GET /api/trends/pipelines          (API, uses TestClient + SQLite)
  - GET /api/trends/verticals          (API, uses TestClient + SQLite)

Design notes
------------
- Unit tests for services need no DB; they work on plain dicts.
- API tests reuse the session-scoped client + db fixtures from conftest.py.
- Each test class uses _uid() unique tenant IDs to prevent cross-test pollution.
- Time-window runs are created with explicit created_at offsets so they land in
  the right window regardless of when the test suite runs.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.models.pipeline_run import PipelineRun
from app.services.trend_engine import (
    compute_metric_trend,
    compute_scope_trend,
    STABLE_ABS_DELTA,
    STABLE_REL_DELTA,
    MEDIUM_SEVERITY_REL,
    HIGH_SEVERITY_REL,
)
from app.services.trend_recommendations import (
    recommendation_for_metric,
    recommendations_for_trends,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PIPELINE_URL = "/api/trends/pipelines"
VERTICAL_URL = "/api/trends/verticals"


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
    """Create a PipelineRun with created_at offset by days_ago from now."""
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


# ===========================================================================
# Unit tests — trend_engine
# ===========================================================================

class TestComputeMetricTrendStable:
    def test_stable_when_abs_delta_below_threshold(self):
        # delta = 0.01 < STABLE_ABS_DELTA (0.02) → stable
        result = compute_metric_trend("failed_rate", previous=0.10, current=0.11)
        assert result["direction"] == "stable"
        assert result["severity"] is None

    def test_stable_when_rel_delta_below_threshold(self):
        # delta = 0.015, previous = 0.50, relative = 0.03 < STABLE_REL_DELTA (0.10) → stable
        result = compute_metric_trend("failed_rate", previous=0.50, current=0.515)
        assert result["direction"] == "stable"

    def test_stable_returns_all_numeric_fields(self):
        result = compute_metric_trend("failed_rate", previous=0.10, current=0.11)
        assert result["delta"] is not None
        assert result["relative_delta"] is not None
        assert result["previous"] == pytest.approx(0.10, abs=1e-4)
        assert result["current"] == pytest.approx(0.11, abs=1e-4)


class TestComputeMetricTrendDirection:
    def test_down_is_good_decreasing_is_improving(self):
        # failed_rate down: improving
        result = compute_metric_trend("failed_rate", previous=0.20, current=0.10)
        assert result["direction"] == "improving"
        assert result["severity"] is None

    def test_down_is_good_increasing_is_degrading(self):
        # failed_rate up: degrading
        result = compute_metric_trend("failed_rate", previous=0.08, current=0.18)
        assert result["direction"] == "degrading"

    def test_up_is_good_increasing_is_improving(self):
        # success_rate up: improving
        result = compute_metric_trend("success_rate", previous=0.70, current=0.88)
        assert result["direction"] == "improving"

    def test_up_is_good_decreasing_is_degrading(self):
        # avg_confidence down: degrading
        result = compute_metric_trend("avg_confidence", previous=0.80, current=0.50)
        assert result["direction"] == "degrading"

    def test_all_down_is_good_metrics(self):
        down_is_good = [
            "failed_rate", "review_rate", "low_confidence_rate",
            "negative_feedback_rate", "fallback_rate", "underpricing_rate",
        ]
        for name in down_is_good:
            result = compute_metric_trend(name, previous=0.50, current=0.10)
            assert result["direction"] == "improving", f"{name} should be improving when decreasing"

    def test_all_up_is_good_metrics(self):
        up_is_good = ["avg_confidence", "success_rate"]
        for name in up_is_good:
            result = compute_metric_trend(name, previous=0.40, current=0.80)
            assert result["direction"] == "improving", f"{name} should be improving when increasing"


class TestComputeMetricTrendSeverity:
    def test_severity_low(self):
        # relative delta ~0.20 — below MEDIUM_SEVERITY_REL (0.25) → low
        result = compute_metric_trend("failed_rate", previous=0.20, current=0.24)
        assert result["direction"] == "degrading"
        assert result["severity"] == "low"

    def test_severity_medium(self):
        # relative delta ~0.375 — between 0.25 and 0.50 → medium
        result = compute_metric_trend("failed_rate", previous=0.08, current=0.11)
        assert result["direction"] == "degrading"
        assert result["severity"] == "medium"

    def test_severity_high(self):
        # relative delta = 1.0 (doubled) → high
        result = compute_metric_trend("failed_rate", previous=0.10, current=0.20)
        assert result["direction"] == "degrading"
        assert result["severity"] == "high"

    def test_improving_has_no_severity(self):
        result = compute_metric_trend("failed_rate", previous=0.20, current=0.08)
        assert result["direction"] == "improving"
        assert result["severity"] is None


class TestComputeMetricTrendInsufficientData:
    def test_none_previous_returns_insufficient_data(self):
        result = compute_metric_trend("failed_rate", previous=None, current=0.10)
        assert result["direction"] == "insufficient_data"
        assert result["delta"] is None
        assert result["relative_delta"] is None
        assert result["severity"] is None

    def test_none_current_returns_insufficient_data(self):
        result = compute_metric_trend("failed_rate", previous=0.10, current=None)
        assert result["direction"] == "insufficient_data"

    def test_both_none_returns_insufficient_data(self):
        result = compute_metric_trend("avg_confidence", previous=None, current=None)
        assert result["direction"] == "insufficient_data"

    def test_result_preserves_name(self):
        result = compute_metric_trend("fallback_rate", previous=None, current=0.05)
        assert result["name"] == "fallback_rate"


class TestComputeScopeTrend:
    def _metrics(self, failed_rate: float, success_rate: float) -> dict:
        return {
            "run_count": 50,
            "success_rate": success_rate,
            "failed_rate": failed_rate,
            "review_rate": 0.05,
            "avg_confidence": 0.75,
            "low_confidence_rate": 0.10,
            "fallback_rate": None,
            "feedback_count": 0,
            "negative_feedback_rate": None,
            "underpricing_rate": None,
        }

    def test_aggregate_degrading_on_high_severity_metric(self):
        prev = self._metrics(failed_rate=0.05, success_rate=0.90)
        curr = self._metrics(failed_rate=0.15, success_rate=0.85)
        direction, _ = compute_scope_trend(curr, prev)
        assert direction == "degrading"

    def test_aggregate_improving_when_more_improving_than_degrading(self):
        prev = self._metrics(failed_rate=0.20, success_rate=0.60)
        curr = self._metrics(failed_rate=0.08, success_rate=0.88)
        direction, _ = compute_scope_trend(curr, prev)
        assert direction == "improving"

    def test_aggregate_stable_when_all_stable(self):
        prev = self._metrics(failed_rate=0.10, success_rate=0.85)
        curr = self._metrics(failed_rate=0.10, success_rate=0.85)
        direction, _ = compute_scope_trend(curr, prev)
        assert direction == "stable"

    def test_returns_metric_list_with_trend_metrics(self):
        prev = self._metrics(failed_rate=0.10, success_rate=0.85)
        curr = self._metrics(failed_rate=0.10, success_rate=0.85)
        _, metric_trends = compute_scope_trend(curr, prev)
        names = {t["name"] for t in metric_trends}
        assert "failed_rate" in names
        assert "success_rate" in names
        assert "avg_confidence" in names

    def test_context_only_metrics_present(self):
        prev = self._metrics(failed_rate=0.10, success_rate=0.85)
        curr = self._metrics(failed_rate=0.10, success_rate=0.85)
        _, metric_trends = compute_scope_trend(curr, prev)
        context = [t for t in metric_trends if t["direction"] == "context_only"]
        assert any(t["name"] == "run_count" for t in context)
        assert any(t["name"] == "feedback_count" for t in context)

    def test_all_none_metrics_yields_stable_aggregate(self):
        empty = {k: None for k in [
            "run_count", "success_rate", "failed_rate", "review_rate",
            "avg_confidence", "low_confidence_rate", "fallback_rate",
            "feedback_count", "negative_feedback_rate", "underpricing_rate",
        ]}
        empty["run_count"] = 0
        empty["feedback_count"] = 0
        direction, _ = compute_scope_trend(empty, empty)
        assert direction == "stable"

    def test_zero_previous_does_not_raise(self):
        prev = self._metrics(failed_rate=0.0, success_rate=1.0)
        curr = self._metrics(failed_rate=0.15, success_rate=0.85)
        # Should not raise ZeroDivisionError — epsilon guard in engine
        direction, metric_trends = compute_scope_trend(curr, prev)
        assert direction in ("improving", "degrading", "stable")


# ===========================================================================
# Unit tests — trend_recommendations
# ===========================================================================

class TestRecommendationForMetric:
    def test_known_metric_returns_string(self):
        rec = recommendation_for_metric("failed_rate")
        assert isinstance(rec, str)
        assert len(rec) > 0

    def test_all_trend_metrics_have_recommendations(self):
        metrics_with_recs = [
            "failed_rate", "review_rate", "avg_confidence", "low_confidence_rate",
            "fallback_rate", "negative_feedback_rate", "underpricing_rate", "success_rate",
        ]
        for name in metrics_with_recs:
            rec = recommendation_for_metric(name)
            assert rec is not None, f"No recommendation for {name}"

    def test_unknown_metric_returns_none(self):
        rec = recommendation_for_metric("nonexistent_metric_xyz")
        assert rec is None

    def test_context_only_metric_returns_none(self):
        assert recommendation_for_metric("run_count") is None
        assert recommendation_for_metric("feedback_count") is None


class TestRecommendationsForTrends:
    def _trend(self, name: str, direction: str, severity: Optional[str] = None) -> dict:
        return {"name": name, "direction": direction, "severity": severity}

    def test_empty_when_no_degrading_metrics(self):
        trends = [
            self._trend("failed_rate", "stable"),
            self._trend("success_rate", "improving"),
        ]
        recs = recommendations_for_trends(trends)
        assert recs == []

    def test_returns_recommendation_for_degrading_metric(self):
        trends = [self._trend("failed_rate", "degrading", "medium")]
        recs = recommendations_for_trends(trends)
        assert len(recs) == 1
        assert "failure" in recs[0].lower() or "fail" in recs[0].lower()

    def test_sorted_by_severity_high_first(self):
        trends = [
            self._trend("review_rate", "degrading", "low"),
            self._trend("failed_rate", "degrading", "high"),
            self._trend("avg_confidence", "degrading", "medium"),
        ]
        recs = recommendations_for_trends(trends)
        # All three have recommendations; high-severity should be first
        failed_rec = recommendation_for_metric("failed_rate")
        assert recs[0] == failed_rec

    def test_deduplication(self):
        # Two metrics that happen to share the same recommendation text should appear once
        trends = [
            self._trend("failed_rate", "degrading", "high"),
            self._trend("failed_rate", "degrading", "high"),  # duplicate
        ]
        recs = recommendations_for_trends(trends)
        assert len(recs) == len(set(recs))

    def test_improving_and_stable_not_included(self):
        trends = [
            self._trend("failed_rate", "improving"),
            self._trend("success_rate", "stable"),
            self._trend("avg_confidence", "insufficient_data"),
            self._trend("review_rate", "degrading", "low"),
        ]
        recs = recommendations_for_trends(trends)
        assert len(recs) == 1


# ===========================================================================
# API tests — GET /api/trends/pipelines
# ===========================================================================

class TestPipelineTrendsEnvelope:
    def test_empty_tenant_returns_zero(self, client, db, api_auth):
        tid = _uid()
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_envelope_keys_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert {"scope_type", "window_days", "window", "total", "items"}.issubset(body.keys())

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["scope_type"] == "pipeline"

    def test_window_shape_has_current_and_previous(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        window = resp.json()["window"]
        assert "current" in window and "previous" in window
        assert "start" in window["current"] and "end" in window["current"]
        assert "start" in window["previous"] and "end" in window["previous"]

    def test_window_days_reflected(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 14}, headers=api_auth
        )
        assert resp.json()["window_days"] == 14


class TestPipelineTrendsItemShape:
    REQUIRED_ITEM_KEYS = {"scope", "scope_id", "trend", "metrics", "recommendations"}

    def test_item_has_required_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert self.REQUIRED_ITEM_KEYS.issubset(set(item.keys()))

    def test_item_scope_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["scope"] == "pipeline"

    def test_item_trend_is_valid_direction(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["trend"] in ("improving", "degrading", "stable")

    def test_metrics_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["metrics"], list)

    def test_recommendations_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["recommendations"], list)

    def test_metric_item_has_required_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        metrics = resp.json()["items"][0]["metrics"]
        required = {"name", "previous", "current", "delta", "relative_delta", "direction", "severity"}
        for m in metrics:
            assert required.issubset(set(m.keys())), f"Missing keys in metric {m['name']}"

    def test_scope_id_matches_pipeline_name(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="my_pipeline", days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["scope_id"] == "my_pipeline"


class TestPipelineTrendsTenantIsolation:
    def test_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_a", days_ago=1)
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_b", days_ago=1)

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid_a}, headers=api_auth)
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["scope_id"] == "pipe_a"

    def test_multiple_pipelines_same_tenant(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, pipeline_name="pipe_x", days_ago=1)
        _make_run(db, tenant_id=tid, pipeline_name="pipe_y", days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["total"] == 2


class TestPipelineTrendDirectionWithData:
    def test_increasing_failed_rate_shows_degrading(self, client, db, api_auth):
        """
        Previous window (8-14 days ago): 1 failed out of 10 = 10% fail rate
        Current window (1-7 days ago): 4 failed out of 10 = 40% fail rate
        Expect failed_rate metric direction = degrading, aggregate = degrading
        """
        tid = _uid()
        pname = _uid()

        # Previous window: 1 fail, 9 completed
        _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=10)
        for _ in range(9):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=10)

        # Current window: 4 fails, 6 completed
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=3)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=3)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 7}, headers=api_auth
        )
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["scope_id"] == pname

        failed_trend = next(m for m in item["metrics"] if m["name"] == "failed_rate")
        assert failed_trend["direction"] == "degrading"
        assert item["trend"] == "degrading"

    def test_improving_failed_rate_shows_improving(self, client, db, api_auth):
        """
        Previous window: 4/10 = 40% failed
        Current window: 1/10 = 10% failed
        Expect failed_rate metric direction = improving
        """
        tid = _uid()
        pname = _uid()

        # Previous: 4 fail
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=10)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=10)

        # Current: 1 fail
        _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=3)
        for _ in range(9):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=3)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 7}, headers=api_auth
        )
        item = resp.json()["items"][0]
        failed_trend = next(m for m in item["metrics"] if m["name"] == "failed_rate")
        assert failed_trend["direction"] == "improving"

    def test_no_previous_data_yields_insufficient_data(self, client, db, api_auth):
        """
        Only current-window runs: previous metrics are empty (run_count=0).
        All rate metrics should be insufficient_data.
        """
        tid = _uid()
        pname = _uid()

        # Only current window (1 day ago) — no previous window data
        for _ in range(5):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=1)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 7}, headers=api_auth
        )
        item = resp.json()["items"][0]
        rate_metrics = [
            m for m in item["metrics"]
            if m["name"] in ("failed_rate", "success_rate", "review_rate")
        ]
        for m in rate_metrics:
            assert m["direction"] == "insufficient_data", (
                f"{m['name']} should be insufficient_data when previous window is empty"
            )

    def test_degrading_metric_has_recommendation(self, client, db, api_auth):
        """Degrading failed_rate must produce a non-empty recommendations list."""
        tid = _uid()
        pname = _uid()

        _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=10)
        for _ in range(9):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=10)

        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=3)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=3)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 7}, headers=api_auth
        )
        item = resp.json()["items"][0]
        assert len(item["recommendations"]) > 0
        assert all(isinstance(r, str) for r in item["recommendations"])


# ===========================================================================
# API tests — GET /api/trends/verticals
# ===========================================================================

class TestVerticalTrendsEnvelope:
    def test_empty_tenant_returns_zero(self, client, db, api_auth):
        tid = _uid()
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_scope_type_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["scope_type"] == "vertical"

    def test_groups_by_vertical_id(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction", days_ago=1)
        _make_run(db, tenant_id=tid, vertical_id="insurance", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 2
        scope_ids = {item["scope_id"] for item in body["items"]}
        assert scope_ids == {"construction", "insurance"}

    def test_item_scope_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="construction", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["scope"] == "vertical"

    def test_envelope_has_window(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="logistics", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        window = resp.json()["window"]
        assert "current" in window and "previous" in window


class TestVerticalTrendsTenantIsolation:
    def test_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, vertical_id="construction", days_ago=1)
        _make_run(db, tenant_id=tid_b, vertical_id="insurance", days_ago=1)

        resp = client.get(VERTICAL_URL, params={"tenant_id": tid_a}, headers=api_auth)
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["scope_id"] == "construction"
