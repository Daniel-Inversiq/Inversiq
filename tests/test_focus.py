"""
tests/test_focus.py

Tests for the Focus / Prioritization layer:
  - app/services/focus_engine.py  (unit, no DB)
  - GET /api/focus/pipelines      (API, uses TestClient + SQLite)
  - GET /api/focus/verticals      (API, uses TestClient + SQLite)

Design notes
------------
- Unit tests verify scoring rules directly with plain dicts.
- API tests use the shared session-scoped SQLite DB from conftest.py.
- Each test class uses _uid() unique tenant IDs to prevent cross-test pollution.
- Runs are created with explicit created_at offsets so they land in the
  correct health/trend windows regardless of when the test suite runs.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.models.pipeline_run import PipelineRun
from app.services.focus_engine import (
    build_focus_item,
    build_reason,
    compute_focus_score,
    extract_key_issues,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

PIPELINE_URL = "/api/focus/pipelines"
VERTICAL_URL = "/api/focus/verticals"


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
        started_at=created_at,
        completed_at=created_at,
        created_at=created_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _trend(direction: str, metrics: Optional[list] = None) -> dict:
    return {
        "trend": direction,
        "metrics": metrics or [],
        "recommendations": ["Fix it."] if direction == "degrading" else [],
    }


def _metric(name: str, direction: str, severity: Optional[str] = None, delta: Optional[float] = None) -> dict:
    return {
        "name": name,
        "direction": direction,
        "severity": severity,
        "delta": delta,
        "previous": None,
        "current": None,
        "relative_delta": None,
    }


# ===========================================================================
# Unit tests — compute_focus_score
# ===========================================================================

class TestComputeFocusScore:
    def test_unhealthy_stable_no_signals(self):
        score = compute_focus_score("unhealthy", "stable", [], {})
        assert score == 60

    def test_watch_stable_no_signals(self):
        score = compute_focus_score("watch", "stable", [], {})
        assert score == 30

    def test_healthy_stable_no_signals(self):
        score = compute_focus_score("healthy", "stable", [], {})
        assert score == 5

    def test_unhealthy_degrading_high_severity(self):
        metrics = [_metric("failed_rate", "degrading", "high")]
        score = compute_focus_score("unhealthy", "degrading", metrics, {})
        assert score == 90  # 60 + 30

    def test_unhealthy_degrading_medium_severity(self):
        metrics = [_metric("failed_rate", "degrading", "medium")]
        score = compute_focus_score("unhealthy", "degrading", metrics, {})
        assert score == 80  # 60 + 20

    def test_watch_degrading_low_severity(self):
        metrics = [_metric("failed_rate", "degrading", "low")]
        score = compute_focus_score("watch", "degrading", metrics, {})
        assert score == 40  # 30 + 10

    def test_degrading_no_severity_uses_fallback(self):
        metrics = [_metric("failed_rate", "degrading", None)]
        score = compute_focus_score("watch", "degrading", metrics, {})
        assert score == 35  # 30 + 5

    def test_improving_applies_penalty(self):
        score = compute_focus_score("watch", "improving", [], {})
        assert score == 25  # 30 - 5

    def test_improving_does_not_go_below_zero(self):
        score = compute_focus_score("healthy", "improving", [], {})
        assert score == 0  # 5 - 5 = 0

    def test_signal_medium_adds_bonus(self):
        from app.intelligence.types import SignalType
        counts = {SignalType.LIKELY_UNDERPRICING.value: 1}
        score = compute_focus_score("watch", "stable", [], counts)
        assert score == 35  # 30 + 5

    def test_signal_bonus_capped_at_20(self):
        from app.intelligence.types import SignalType
        # 10 medium signals × 5 = 50, but capped at 20
        counts = {SignalType.LIKELY_UNDERPRICING.value: 10}
        score = compute_focus_score("healthy", "stable", [], counts)
        assert score == 25  # 5 + 20 (capped)

    def test_score_clamped_to_100(self):
        metrics = [_metric("failed_rate", "degrading", "high")]
        from app.intelligence.types import SignalType
        counts = {SignalType.LIKELY_UNDERPRICING.value: 10}
        score = compute_focus_score("unhealthy", "degrading", metrics, counts)
        assert score == 100  # 60 + 30 + 20 = 110 → clamped

    def test_worst_severity_drives_trend_mod(self):
        # Both high and low degrading: high should win
        metrics = [
            _metric("failed_rate", "degrading", "high"),
            _metric("review_rate", "degrading", "low"),
        ]
        score = compute_focus_score("watch", "degrading", metrics, {})
        assert score == 60  # 30 + 30 (high wins)

    def test_improving_metrics_ignored_for_trend_mod(self):
        # Aggregate is "degrading" but no degrading individual metrics classified
        metrics = [_metric("success_rate", "improving", None)]
        score = compute_focus_score("watch", "degrading", metrics, {})
        assert score == 35  # 30 + 5 (fallback: degrading but no classified severity)


# ===========================================================================
# Unit tests — extract_key_issues
# ===========================================================================

class TestExtractKeyIssues:
    def test_healthy_no_threshold_breaches(self):
        issues = extract_key_issues("healthy", 0.05, 0.05, 0.05, [], {})
        assert issues == []

    def test_unhealthy_failed_rate_listed(self):
        issues = extract_key_issues("unhealthy", 0.35, 0.0, 0.0, [], {})
        assert any("failed_rate" in i and "unhealthy" in i for i in issues)

    def test_watch_failed_rate_listed(self):
        issues = extract_key_issues("watch", 0.15, 0.0, 0.0, [], {})
        assert any("failed_rate" in i and "watch" in i for i in issues)

    def test_degrading_metric_listed(self):
        metrics = [_metric("failed_rate", "degrading", "high", delta=0.20)]
        issues = extract_key_issues("healthy", 0.0, 0.0, 0.0, metrics, {})
        assert any("failed_rate" in i and "degrading" in i for i in issues)

    def test_degrading_sorted_by_severity(self):
        metrics = [
            _metric("review_rate", "degrading", "low"),
            _metric("failed_rate", "degrading", "high"),
        ]
        issues = extract_key_issues("healthy", 0.0, 0.0, 0.0, metrics, {})
        degrading_issues = [i for i in issues if "degrading" in i]
        assert degrading_issues[0].startswith("failed_rate")

    def test_signal_counts_included(self):
        from app.intelligence.types import SignalType
        counts = {SignalType.LIKELY_UNDERPRICING.value: 2}
        issues = extract_key_issues("healthy", 0.0, 0.0, 0.0, [], counts)
        assert any("likely_underpricing" in i for i in issues)

    def test_stable_metrics_not_included(self):
        metrics = [_metric("success_rate", "stable")]
        issues = extract_key_issues("healthy", 0.0, 0.0, 0.0, metrics, {})
        assert not any("success_rate" in i for i in issues)

    def test_capped_at_six(self):
        metrics = [_metric(f"metric_{i}", "degrading", "low") for i in range(10)]
        issues = extract_key_issues("unhealthy", 0.35, 0.45, 0.55, metrics, {})
        assert len(issues) <= 6

    def test_delta_included_in_degrading_issue(self):
        metrics = [_metric("failed_rate", "degrading", "medium", delta=0.15)]
        issues = extract_key_issues("healthy", 0.0, 0.0, 0.0, metrics, {})
        assert any("Δ" in i for i in issues)


# ===========================================================================
# Unit tests — build_reason
# ===========================================================================

class TestBuildReason:
    def test_contains_score(self):
        reason = build_reason("watch", "stable", [], {}, 30)
        assert "30" in reason

    def test_contains_health_status(self):
        reason = build_reason("unhealthy", "degrading", [], {}, 60)
        assert "health=unhealthy" in reason

    def test_contains_trend_direction(self):
        reason = build_reason("watch", "degrading", [], {}, 35)
        assert "trend=degrading" in reason

    def test_worst_metric_mentioned(self):
        metrics = [_metric("failed_rate", "degrading", "high")]
        reason = build_reason("unhealthy", "degrading", metrics, {}, 90)
        assert "failed_rate" in reason and "high" in reason

    def test_active_signals_mentioned(self):
        from app.intelligence.types import SignalType
        counts = {SignalType.LIKELY_UNDERPRICING.value: 1}
        reason = build_reason("watch", "stable", [], counts, 35)
        assert "likely_underpricing" in reason

    def test_no_degrading_metrics_no_metric_mention(self):
        metrics = [_metric("success_rate", "improving")]
        reason = build_reason("watch", "stable", metrics, {}, 30)
        assert "worst degrading metric" not in reason


# ===========================================================================
# Unit tests — build_focus_item
# ===========================================================================

class TestBuildFocusItem:
    def test_returns_required_keys(self):
        item = build_focus_item(
            scope_type="pipeline",
            scope_id="my_pipe",
            health_status="watch",
            failed_rate=0.12,
            needs_review_rate=0.05,
            low_confidence_rate=0.05,
            signal_counts={},
            health_recommendation="Check failures.",
            trend_item=_trend("stable"),
        )
        required = {"scope", "scope_id", "priority_score", "severity", "health_status",
                    "trend", "key_issues", "recommendation", "reason"}
        assert required.issubset(item.keys())

    def test_scope_id_propagated(self):
        item = build_focus_item(
            scope_type="pipeline", scope_id="pipe_abc",
            health_status="healthy", failed_rate=0.0,
            needs_review_rate=0.0, low_confidence_rate=0.0,
            signal_counts={}, health_recommendation="OK",
            trend_item=_trend("stable"),
        )
        assert item["scope_id"] == "pipe_abc"
        assert item["scope"] == "pipeline"

    def test_trend_rec_preferred_over_health_rec(self):
        item = build_focus_item(
            scope_type="pipeline", scope_id="p",
            health_status="healthy", failed_rate=0.0,
            needs_review_rate=0.0, low_confidence_rate=0.0,
            signal_counts={}, health_recommendation="Health rec.",
            trend_item=_trend("degrading", [_metric("failed_rate", "degrading", "high")]),
        )
        assert item["recommendation"] == "Fix it."

    def test_health_rec_fallback_when_no_trend_recs(self):
        item = build_focus_item(
            scope_type="pipeline", scope_id="p",
            health_status="watch", failed_rate=0.15,
            needs_review_rate=0.0, low_confidence_rate=0.0,
            signal_counts={}, health_recommendation="Health rec.",
            trend_item=_trend("stable"),
        )
        assert item["recommendation"] == "Health rec."

    def test_severity_label_critical_at_75_plus(self):
        # unhealthy (60) + degrading high (30) = 90 → critical
        item = build_focus_item(
            scope_type="pipeline", scope_id="p",
            health_status="unhealthy", failed_rate=0.35,
            needs_review_rate=0.0, low_confidence_rate=0.0,
            signal_counts={},
            health_recommendation="Fix.",
            trend_item=_trend("degrading", [_metric("failed_rate", "degrading", "high")]),
        )
        assert item["severity"] == "critical"
        assert item["priority_score"] == 90

    def test_severity_label_low_for_healthy_improving(self):
        item = build_focus_item(
            scope_type="pipeline", scope_id="p",
            health_status="healthy", failed_rate=0.0,
            needs_review_rate=0.0, low_confidence_rate=0.0,
            signal_counts={}, health_recommendation="OK.",
            trend_item=_trend("improving"),
        )
        assert item["severity"] == "low"


# ===========================================================================
# API tests — GET /api/focus/pipelines
# ===========================================================================

class TestPipelineFocusEnvelope:
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
        assert {"scope_type", "window_days", "lookback_days", "total", "items"}.issubset(body.keys())

    def test_scope_type_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["scope_type"] == "pipeline"

    def test_window_and_lookback_reflected(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(
            PIPELINE_URL,
            params={"tenant_id": tid, "window_days": 14, "lookback_days": 60},
            headers=api_auth,
        )
        body = resp.json()
        assert body["window_days"] == 14
        assert body["lookback_days"] == 60


class TestPipelineFocusItemShape:
    REQUIRED = {
        "scope", "scope_id", "priority_score", "severity",
        "health_status", "trend", "key_issues", "recommendation", "reason",
    }

    def test_item_has_required_keys(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert self.REQUIRED.issubset(item.keys())

    def test_scope_is_pipeline(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["scope"] == "pipeline"

    def test_priority_score_is_int_in_range(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["priority_score"], int)
        assert 0 <= item["priority_score"] <= 100

    def test_severity_is_valid_label(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["severity"] in ("critical", "high", "medium", "low")

    def test_health_status_valid(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["health_status"] in ("healthy", "watch", "unhealthy")

    def test_trend_is_valid_direction(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["trend"] in ("improving", "degrading", "stable")

    def test_key_issues_is_list(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["key_issues"], list)

    def test_recommendation_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["recommendation"], str)
        assert len(item["recommendation"]) > 0

    def test_reason_is_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, days_ago=1)
        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["reason"], str)
        assert len(item["reason"]) > 0


class TestPipelineFocusPriorityOrdering:
    def test_unhealthy_pipeline_ranks_above_healthy(self, client, db, api_auth):
        """
        Pipeline A: all failures → unhealthy
        Pipeline B: all successes → healthy
        A must appear before B in focus output.
        """
        tid = _uid()
        pipe_unhealthy = _uid()
        pipe_healthy = _uid()

        # Unhealthy: 7 failed out of 10
        for _ in range(7):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_unhealthy, status="FAILED", days_ago=1)
        for _ in range(3):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_unhealthy, status="COMPLETED", days_ago=1)

        # Healthy: all completed
        for _ in range(10):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_healthy, status="COMPLETED", days_ago=1)

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

        scores = {item["scope_id"]: item["priority_score"] for item in items}
        assert scores[pipe_unhealthy] > scores[pipe_healthy]
        assert items[0]["scope_id"] == pipe_unhealthy

    def test_degrading_trend_raises_score_above_stable(self, client, db, api_auth):
        """
        Two pipelines with same health (watch).
        One has a degrading trend (increasing failures), one is stable.
        The degrading one must score higher.
        """
        tid = _uid()
        pipe_deg = _uid()
        pipe_stable = _uid()

        # pipe_deg: previous window 1/10 failed, current window 4/10 failed
        _make_run(db, tenant_id=tid, pipeline_name=pipe_deg, status="FAILED", days_ago=10)
        for _ in range(9):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_deg, status="COMPLETED", days_ago=10)
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_deg, status="FAILED", days_ago=3)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_deg, status="COMPLETED", days_ago=3)

        # pipe_stable: same rate both windows (watch-level)
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_stable, status="FAILED", days_ago=10)
        for _ in range(8):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_stable, status="COMPLETED", days_ago=10)
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_stable, status="FAILED", days_ago=3)
        for _ in range(8):
            _make_run(db, tenant_id=tid, pipeline_name=pipe_stable, status="COMPLETED", days_ago=3)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "window_days": 7}, headers=api_auth
        )
        items = resp.json()["items"]
        scores = {item["scope_id"]: item["priority_score"] for item in items}
        assert scores[pipe_deg] > scores[pipe_stable]

    def test_items_sorted_descending(self, client, db, api_auth):
        """Items must appear score-descending."""
        tid = _uid()
        for name in ("p1", "p2", "p3"):
            _make_run(db, tenant_id=tid, pipeline_name=name, status="COMPLETED", days_ago=1)
        # Add some failures to p1 to differentiate scores
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name="p1", status="FAILED", days_ago=1)

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        scores = [item["priority_score"] for item in resp.json()["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_unhealthy_key_issues_populated(self, client, db, api_auth):
        """An unhealthy pipeline should have at least one key issue."""
        tid = _uid()
        pname = _uid()
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="FAILED", days_ago=1)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name=pname, status="COMPLETED", days_ago=1)

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid}, headers=api_auth)
        item = next(i for i in resp.json()["items"] if i["scope_id"] == pname)
        assert len(item["key_issues"]) > 0


class TestPipelineFocusTopN:
    def test_top_n_limits_output(self, client, db, api_auth):
        tid = _uid()
        for name in ("pa", "pb", "pc", "pd"):
            _make_run(db, tenant_id=tid, pipeline_name=name, days_ago=1)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "top_n": 2}, headers=api_auth
        )
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 2

    def test_top_n_returns_highest_scored(self, client, db, api_auth):
        tid = _uid()
        # Unhealthy pipeline
        for _ in range(4):
            _make_run(db, tenant_id=tid, pipeline_name="bad_pipe", status="FAILED", days_ago=1)
        for _ in range(6):
            _make_run(db, tenant_id=tid, pipeline_name="bad_pipe", status="COMPLETED", days_ago=1)
        # Healthy pipelines
        for name in ("good_a", "good_b"):
            for _ in range(5):
                _make_run(db, tenant_id=tid, pipeline_name=name, status="COMPLETED", days_ago=1)

        resp = client.get(
            PIPELINE_URL, params={"tenant_id": tid, "top_n": 1}, headers=api_auth
        )
        assert resp.json()["items"][0]["scope_id"] == "bad_pipe"


class TestPipelineFocusTenantIsolation:
    def test_scoped_to_tenant(self, client, db, api_auth):
        tid_a = _uid()
        tid_b = _uid()
        _make_run(db, tenant_id=tid_a, pipeline_name="pipe_a", days_ago=1)
        _make_run(db, tenant_id=tid_b, pipeline_name="pipe_b", days_ago=1)

        resp = client.get(PIPELINE_URL, params={"tenant_id": tid_a}, headers=api_auth)
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["scope_id"] == "pipe_a"


# ===========================================================================
# API tests — GET /api/focus/verticals
# ===========================================================================

class TestVerticalFocusEnvelope:
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
        _make_run(db, tenant_id=tid, vertical_id="roofing", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 2
        scope_ids = {item["scope_id"] for item in body["items"]}
        assert scope_ids == {"construction", "roofing"}

    def test_item_scope_is_vertical(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, vertical_id="solar", days_ago=1)
        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.json()["items"][0]["scope"] == "vertical"

    def test_items_sorted_descending(self, client, db, api_auth):
        tid = _uid()
        for vid in ("v1", "v2", "v3"):
            _make_run(db, tenant_id=tid, vertical_id=vid, days_ago=1)
        for _ in range(3):
            _make_run(db, tenant_id=tid, vertical_id="v1", status="FAILED", days_ago=1)

        resp = client.get(VERTICAL_URL, params={"tenant_id": tid}, headers=api_auth)
        scores = [item["priority_score"] for item in resp.json()["items"]]
        assert scores == sorted(scores, reverse=True)
