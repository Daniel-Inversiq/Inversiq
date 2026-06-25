"""
tests/test_business_metrics.py

Tests for the business metrics endpoints:
  GET /api/metrics/business
  GET /api/metrics/business/by-vertical

Design notes
------------
- The test SQLite DB is shared across the session and is NOT rolled back between
  tests.  Every test that inserts rows uses a unique tenant_id so queries cannot
  bleed into each other.
- The ``client`` fixture and the ``db`` fixture both target the same SQLite file;
  rows committed via ``db`` are visible to the ``client``.
- Basic-Auth credentials default to "" in tests (see conftest.py), so the
  ``api_auth`` fixture sends ``Authorization: Basic <base64(":")>``.
"""
from __future__ import annotations

import base64
import uuid

import pytest

from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tid() -> str:
    """Return a unique tenant_id for a single test."""
    return f"bm-test-{uuid.uuid4().hex[:12]}"


def _make_run(
    db,
    *,
    tenant_id: str,
    vertical_id: str = "construction",
    lead_id: str | None = None,
    status: str = "COMPLETED",
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=lead_id or uuid.uuid4().hex,
        vertical_id=vertical_id,
        trace_id=uuid.uuid4().hex,
        pipeline_name="test_pipeline",
        engine_version="0.0.1",
        status=status,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _make_feedback(
    db,
    *,
    tenant_id: str,
    outcome: str,
    pipeline_run_id: int | None = None,
    actual_price: float | None = None,
    estimated_price: float | None = None,
) -> LeadFeedback:
    fb = LeadFeedback(
        tenant_id=tenant_id,
        lead_id=uuid.uuid4().hex,
        outcome=outcome,
        pipeline_run_id=pipeline_run_id,
        actual_price=actual_price,
        estimated_price=estimated_price,
    )
    db.add(fb)
    db.commit()
    return fb


@pytest.fixture
def api_auth():
    """Basic-Auth header with empty user:pass (matches test env defaults)."""
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


# ---------------------------------------------------------------------------
# GET /api/metrics/business
# ---------------------------------------------------------------------------

class TestBusinessMetricsSummary:

    def test_empty_tenant_returns_zero_feedback(self, client, api_auth):
        """A tenant with no rows at all → feedback totals are 0, pipeline total is 0."""
        tid = _tid()
        resp = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()

        fb = body["feedback"]
        assert fb["total"] == 0
        assert fb["won"] == 0
        assert fb["lost"] == 0
        assert fb["win_rate"] is None
        assert fb["avg_price_delta"] is None

        pl = body["pipeline"]
        assert pl["total"] == 0
        assert pl["failed"] == 0
        assert pl["needs_review"] == 0

    def test_response_contains_required_keys(self, client, api_auth):
        tid = _tid()
        resp = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert {"as_of", "filters", "feedback", "pipeline"} == body.keys()
        assert body["filters"]["tenant_id"] == tid

    def test_won_lost_counts_and_win_rate(self, client, db, api_auth):
        """2 wins + 1 loss → win_rate = 0.667."""
        tid = _tid()
        _make_feedback(db, tenant_id=tid, outcome="won")
        _make_feedback(db, tenant_id=tid, outcome="won")
        _make_feedback(db, tenant_id=tid, outcome="lost")

        resp = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth)
        assert resp.status_code == 200
        fb = resp.json()["feedback"]

        assert fb["total"] == 3
        assert fb["won"] == 2
        assert fb["lost"] == 1
        assert fb["win_rate"] == pytest.approx(0.667, abs=0.001)

    def test_win_rate_all_won(self, client, db, api_auth):
        tid = _tid()
        _make_feedback(db, tenant_id=tid, outcome="won")
        _make_feedback(db, tenant_id=tid, outcome="won")

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["win_rate"] == 1.0

    def test_win_rate_all_lost(self, client, db, api_auth):
        tid = _tid()
        _make_feedback(db, tenant_id=tid, outcome="lost")

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["win_rate"] == 0.0

    def test_avg_price_delta_positive(self, client, db, api_auth):
        """actual > estimated → positive avg_price_delta."""
        tid = _tid()
        # delta = +200 and +100 → avg = 150
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=1200.0, estimated_price=1000.0)
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=1100.0, estimated_price=1000.0)

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["avg_price_delta"] == pytest.approx(150.0, abs=0.5)

    def test_avg_price_delta_negative(self, client, db, api_auth):
        """actual < estimated → negative avg_price_delta (over-estimated)."""
        tid = _tid()
        _make_feedback(db, tenant_id=tid, outcome="lost", actual_price=800.0, estimated_price=1000.0)

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["avg_price_delta"] == pytest.approx(-200.0, abs=0.5)

    def test_avg_price_delta_excludes_rows_without_both_prices(self, client, db, api_auth):
        """Rows missing actual or estimated price must not affect avg_price_delta."""
        tid = _tid()
        # This row has a known delta of +100
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=1100.0, estimated_price=1000.0)
        # These rows are missing one or both prices → excluded from avg
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=None, estimated_price=1000.0)
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=1000.0, estimated_price=None)
        _make_feedback(db, tenant_id=tid, outcome="lost", actual_price=None, estimated_price=None)

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["avg_price_delta"] == pytest.approx(100.0, abs=0.5)

    def test_avg_price_delta_null_when_no_complete_price_rows(self, client, db, api_auth):
        tid = _tid()
        _make_feedback(db, tenant_id=tid, outcome="won", actual_price=None, estimated_price=None)

        fb = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["feedback"]
        assert fb["avg_price_delta"] is None

    def test_pipeline_failed_count(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, status="FAILED")
        _make_run(db, tenant_id=tid, status="FAILED")
        _make_run(db, tenant_id=tid, status="COMPLETED")

        pl = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["pipeline"]
        assert pl["total"] == 3
        assert pl["failed"] == 2

    def test_pipeline_needs_review_count(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        _make_run(db, tenant_id=tid, status="COMPLETED")

        pl = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["pipeline"]
        assert pl["needs_review"] == 1
        assert pl["total"] == 2

    def test_pipeline_by_status_breakdown(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, status="COMPLETED")
        _make_run(db, tenant_id=tid, status="FAILED")
        _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")

        pl = client.get(f"/api/metrics/business?tenant_id={tid}", headers=api_auth).json()["pipeline"]
        assert pl["by_status"]["COMPLETED"] == 1
        assert pl["by_status"]["FAILED"] == 1
        assert pl["by_status"]["NEEDS_REVIEW"] == 1

    def test_tenant_id_filter_isolates_data(self, client, db, api_auth):
        """Rows from tenant_a must not appear under tenant_b."""
        tid_a = _tid()
        tid_b = _tid()
        _make_feedback(db, tenant_id=tid_a, outcome="won")
        _make_run(db, tenant_id=tid_a, status="FAILED")

        resp_b = client.get(f"/api/metrics/business?tenant_id={tid_b}", headers=api_auth)
        body_b = resp_b.json()
        assert body_b["feedback"]["total"] == 0
        assert body_b["pipeline"]["total"] == 0

    def test_no_tenant_filter_returns_200(self, client, api_auth):
        """Omitting tenant_id is valid — returns cross-tenant aggregate."""
        resp = client.get("/api/metrics/business", headers=api_auth)
        assert resp.status_code == 200
        assert resp.json()["filters"]["tenant_id"] is None


# ---------------------------------------------------------------------------
# GET /api/metrics/business/by-vertical
# ---------------------------------------------------------------------------

class TestBusinessMetricsByVertical:

    def test_empty_returns_empty_items(self, client, api_auth):
        tid = _tid()
        resp = client.get(f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []

    def test_response_structure(self, client, api_auth):
        tid = _tid()
        resp = client.get(f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert {"as_of", "filters", "items"} == body.keys()
        assert body["filters"]["tenant_id"] == tid

    def test_pipeline_runs_appear_per_vertical(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, vertical_id="construction", status="COMPLETED")
        _make_run(db, tenant_id=tid, vertical_id="insurance", status="COMPLETED")

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        verticals = {i["vertical_id"] for i in items}
        assert "construction" in verticals
        assert "insurance" in verticals

    def test_vertical_pipeline_counts_correct(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, vertical_id="construction", status="COMPLETED")
        _make_run(db, tenant_id=tid, vertical_id="construction", status="FAILED")
        _make_run(db, tenant_id=tid, vertical_id="construction", status="NEEDS_REVIEW")

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        painting = next(i for i in items if i["vertical_id"] == "construction")
        assert painting["pipeline"]["total"] == 3
        assert painting["pipeline"]["failed"] == 1
        assert painting["pipeline"]["needs_review"] == 1

    def test_feedback_linked_via_pipeline_run_id_appears(self, client, db, api_auth):
        """Feedback with a pipeline_run_id → counted in by-vertical under that vertical."""
        tid = _tid()
        run = _make_run(db, tenant_id=tid, vertical_id="logistics", status="COMPLETED")
        _make_feedback(db, tenant_id=tid, outcome="won", pipeline_run_id=run.id)
        _make_feedback(db, tenant_id=tid, outcome="lost", pipeline_run_id=run.id)

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        logistics = next(i for i in items if i["vertical_id"] == "logistics")
        assert logistics["feedback"]["won"] == 1
        assert logistics["feedback"]["lost"] == 1
        assert logistics["feedback"]["total"] == 2
        assert logistics["feedback"]["win_rate"] == pytest.approx(0.5, abs=0.001)

    def test_feedback_without_pipeline_run_id_excluded(self, client, db, api_auth):
        """Feedback rows with pipeline_run_id=None are not counted in by-vertical."""
        tid = _tid()
        _make_run(db, tenant_id=tid, vertical_id="plumbing", status="COMPLETED")
        # This feedback has no pipeline_run_id → excluded from join
        _make_feedback(db, tenant_id=tid, outcome="won", pipeline_run_id=None)

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        plumbing = next(i for i in items if i["vertical_id"] == "plumbing")
        assert plumbing["feedback"]["won"] == 0
        assert plumbing["feedback"]["total"] == 0

    def test_win_rate_null_when_no_feedback_linked(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, vertical_id="electric", status="COMPLETED")

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        electric = next(i for i in items if i["vertical_id"] == "electric")
        assert electric["feedback"]["win_rate"] is None

    def test_tenant_filter_isolates_verticals(self, client, db, api_auth):
        """Runs from tid_a must not appear under tid_b."""
        tid_a = _tid()
        tid_b = _tid()
        _make_run(db, tenant_id=tid_a, vertical_id="hvac", status="COMPLETED")

        items_b = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid_b}", headers=api_auth
        ).json()["items"]

        assert all(i["vertical_id"] != "hvac" or True for i in items_b)
        vertical_ids = {i["vertical_id"] for i in items_b}
        # tid_b has no rows, so should be empty
        assert len(items_b) == 0

    def test_items_sorted_alphabetically_by_vertical(self, client, db, api_auth):
        """Items list is sorted by vertical_id ascending."""
        tid = _tid()
        for v in ["zebra", "alpha", "mango"]:
            _make_run(db, tenant_id=tid, vertical_id=v, status="COMPLETED")

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        ids = [i["vertical_id"] for i in items]
        assert ids == sorted(ids)

    def test_item_has_required_keys(self, client, db, api_auth):
        tid = _tid()
        _make_run(db, tenant_id=tid, vertical_id="keys_test", status="COMPLETED")

        items = client.get(
            f"/api/metrics/business/by-vertical?tenant_id={tid}", headers=api_auth
        ).json()["items"]

        item = next(i for i in items if i["vertical_id"] == "keys_test")
        assert {"vertical_id", "pipeline", "feedback"} == item.keys()
        assert {"total", "failed", "needs_review", "by_status"} == item["pipeline"].keys()
        assert {"total", "won", "lost", "win_rate"} == item["feedback"].keys()
