"""
tests/test_review_inbox.py

Tests for GET /api/review-inbox.

Design notes
------------
- Uses the shared session-scoped SQLite DB (same pattern as test_intelligence.py).
- Each test uses a unique tenant_id via _uid() to prevent cross-test pollution.
- Basic-Auth credentials are both empty (matches conftest.py defaults).
- Run fixtures create minimal PipelineRun rows; steps are not required for
  status/confidence-based review scoring.

Scenarios covered
-----------------
Response envelope
  - Empty tenant returns total=0, items=[]
  - Envelope keys: total, limit, offset, summary, items
  - summary counts sum to total

FAILED run — high priority
  - FAILED + permanent error → review_recommended=True, review_priority=high
  - FAILED + validation error → review_recommended=True, review_priority=high
  - FAILED + transient error → review_recommended=True, review_priority=medium
  - FAILED + external_dependency → review_recommended=True, review_priority=medium
  - FAILED + no error category → review_recommended=True, review_priority=medium

NEEDS_REVIEW run — low priority
  - review_recommended=True, review_priority=low

Low confidence COMPLETED run — medium priority
  - overall_confidence_label="low" → review_recommended=True, review_priority=medium

Healthy COMPLETED run — excluded
  - status=COMPLETED, confidence=None → not in inbox

Item shape
  - All required fields present on each item

Filters
  - tenant_id isolates results
  - status filter narrows by pipeline status
  - priority filter post-filters by computed review_priority
  - review_recommended_only=False includes low-confidence COMPLETED that has
    no anomaly-driven override

Ordering
  - FAILED (high) appears before NEEDS_REVIEW (low) in same page
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from app.models.pipeline_run import PipelineRun

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

URL = "/api/review-inbox"


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
    error_category: Optional[str] = None,
    overall_confidence_label: Optional[str] = None,
    overall_confidence_score: Optional[float] = None,
    pipeline_name: str = "test_pipeline",
    lead_id: Optional[str] = None,
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=lead_id or _uid(),
        vertical_id="test_vertical",
        trace_id=_uid(),
        pipeline_name=pipeline_name,
        engine_version="1.0.0",
        status=status,
        error_category=error_category,
        overall_confidence_label=overall_confidence_label,
        overall_confidence_score=overall_confidence_score,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class TestEnvelope:
    def test_empty_tenant_returns_empty(self, client, db, api_auth):
        tid = _uid()
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_envelope_keys_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"total", "limit", "offset", "summary", "items"}

    def test_summary_counts_sum_to_total(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        summary_total = sum(body["summary"].values())
        assert summary_total == body["total"]

    def test_limit_and_offset_reflected(self, client, db, api_auth):
        resp = client.get(URL, params={"limit": 10, "offset": 5}, headers=api_auth)
        body = resp.json()
        assert body["limit"] == 10
        assert body["offset"] == 5


# ---------------------------------------------------------------------------
# FAILED runs — priority driven by error_category
# ---------------------------------------------------------------------------


class TestFailedRuns:
    def test_failed_permanent_is_high_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["review_recommended"] is True
        assert item["review_priority"] == "high"
        assert item["status"] == "FAILED"

    def test_failed_validation_is_high_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="validation")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["review_priority"] == "high"

    def test_failed_transient_is_medium_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["review_priority"] == "medium"

    def test_failed_external_dependency_is_medium_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="external_dependency")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["review_priority"] == "medium"

    def test_failed_no_error_category_is_medium_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category=None)
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["review_priority"] == "medium"


# ---------------------------------------------------------------------------
# NEEDS_REVIEW — low priority
# ---------------------------------------------------------------------------


class TestNeedsReview:
    def test_needs_review_appears_with_low_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["review_recommended"] is True
        assert item["review_priority"] == "low"
        assert item["status"] == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Low confidence COMPLETED run — medium priority
# ---------------------------------------------------------------------------


class TestLowConfidence:
    def test_completed_low_confidence_is_medium_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(
            db,
            tenant_id=tid,
            status="COMPLETED",
            overall_confidence_label="low",
            overall_confidence_score=0.25,
        )
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["review_recommended"] is True
        assert item["review_priority"] == "medium"
        assert item["confidence"] == pytest.approx(0.25)

    def test_confidence_score_in_item(self, client, db, api_auth):
        tid = _uid()
        _make_run(
            db,
            tenant_id=tid,
            status="FAILED",
            error_category="permanent",
            overall_confidence_score=0.9,
        )
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["confidence"] == pytest.approx(0.9)

    def test_null_confidence_allowed(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["items"][0]["confidence"] is None


# ---------------------------------------------------------------------------
# Healthy COMPLETED run — excluded by default
# ---------------------------------------------------------------------------


class TestHealthyRunsExcluded:
    def test_healthy_completed_not_in_inbox(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="COMPLETED")  # no low confidence
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 0

    def test_completed_medium_confidence_not_in_inbox(self, client, db, api_auth):
        tid = _uid()
        _make_run(
            db,
            tenant_id=tid,
            status="COMPLETED",
            overall_confidence_label="medium",
            overall_confidence_score=0.65,
        )
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = resp.json()
        assert body["total"] == 0


# ---------------------------------------------------------------------------
# Item shape
# ---------------------------------------------------------------------------


class TestItemShape:
    REQUIRED_FIELDS = {
        "pipeline_run_id",
        "tenant_id",
        "lead_id",
        "pipeline_name",
        "status",
        "review_recommended",
        "review_priority",
        "review_reason",
        "confidence",
        "anomaly_count",
        "created_at",
    }

    def test_all_required_fields_present(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert self.REQUIRED_FIELDS <= set(item.keys())

    def test_pipeline_run_id_is_integer(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["pipeline_run_id"] == run.id

    def test_anomaly_count_is_non_negative_int(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["anomaly_count"], int)
        assert item["anomaly_count"] >= 0

    def test_review_reason_is_non_empty_string(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert isinstance(item["review_reason"], str)
        assert len(item["review_reason"]) > 0

    def test_tenant_id_and_lead_id_in_item(self, client, db, api_auth):
        tid = _uid()
        lid = _uid()
        _make_run(db, tenant_id=tid, lead_id=lid, status="NEEDS_REVIEW")
        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["tenant_id"] == tid
        assert item["lead_id"] == lid


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_tenant_id_isolates_results(self, client, db, api_auth):
        t1, t2 = _uid(), _uid()
        _make_run(db, tenant_id=t1, status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=t2, status="FAILED", error_category="permanent")

        resp1 = client.get(URL, params={"tenant_id": t1}, headers=api_auth)
        resp2 = client.get(URL, params={"tenant_id": t2}, headers=api_auth)

        assert resp1.json()["total"] == 1
        assert resp2.json()["total"] == 1
        assert resp1.json()["items"][0]["tenant_id"] == t1
        assert resp2.json()["items"][0]["tenant_id"] == t2

    def test_status_filter_returns_only_that_status(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")

        resp = client.get(
            URL,
            params={"tenant_id": tid, "status": "FAILED"},
            headers=api_auth,
        )
        body = resp.json()
        assert all(i["status"] == "FAILED" for i in body["items"])

    def test_priority_filter_high(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")

        resp = client.get(
            URL,
            params={"tenant_id": tid, "priority": "high"},
            headers=api_auth,
        )
        body = resp.json()
        assert all(i["review_priority"] == "high" for i in body["items"])

    def test_priority_filter_medium(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")   # high
        _make_run(db, tenant_id=tid, status="FAILED", error_category="transient")   # medium
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")                          # low

        resp = client.get(
            URL,
            params={"tenant_id": tid, "priority": "medium"},
            headers=api_auth,
        )
        body = resp.json()
        assert body["total"] >= 1
        assert all(i["review_priority"] == "medium" for i in body["items"])

    def test_review_recommended_only_false_includes_all_candidates(self, client, db, api_auth):
        """
        review_recommended_only=False bypasses the post-filter but keeps the
        candidate pre-filter active (FAILED / NEEDS_REVIEW / low confidence).
        A healthy COMPLETED run is still not returned since it's not a candidate.
        """
        tid = _uid()
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")

        resp_default = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        resp_all = client.get(
            URL,
            params={"tenant_id": tid, "review_recommended_only": False},
            headers=api_auth,
        )
        # With review_recommended_only=False, total is >= the default count.
        assert resp_all.json()["total"] >= resp_default.json()["total"]


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_high_priority_before_low_priority(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")                        # low
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")  # high

        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        assert len(items) == 2
        assert items[0]["review_priority"] == "high"
        assert items[1]["review_priority"] == "low"

    def test_failed_before_needs_review_before_low_confidence(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        _make_run(
            db,
            tenant_id=tid,
            status="COMPLETED",
            overall_confidence_label="low",
            overall_confidence_score=0.3,
        )
        _make_run(db, tenant_id=tid, status="FAILED", error_category="permanent")

        resp = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        priorities = [i["review_priority"] for i in items]
        # high must come before medium, medium before low
        seen_non_high = False
        seen_low = False
        for p in priorities:
            if p != "high":
                seen_non_high = True
            if p == "low":
                seen_low = True
            if seen_non_high and p == "high":
                pytest.fail(f"high priority item found after non-high: {priorities}")
            if seen_low and p != "low":
                pytest.fail(f"non-low priority item found after low: {priorities}")
