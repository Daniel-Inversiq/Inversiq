"""
tests/test_intelligence.py

Tests for GET /api/intelligence/signals.

Design notes
------------
- Uses the shared session-scoped SQLite DB (same pattern as test_anomalies.py).
- Every test class uses unique tenant_id values via _uid() to prevent
  cross-test contamination.
- The ``client`` fixture is session-scoped; ``db`` is function-scoped.
- Basic-Auth credentials are both empty (matches conftest.py defaults).
- All thresholds passed explicitly so tests are self-describing.

Scenarios covered
-----------------
Response envelope
  - Empty scope → total=0, summary={}, items=[]
  - total equals len(items)
  - summary counts sum to total
  - Every item carries the required fields

LIKELY_UNDERPRICING
  - Fires when ≥ min_fraction of won deals are underpriced
  - Silent when sample is below min_sample
  - Silent when fraction is below min_fraction
  - Context fields present with correct values

LIKELY_OVERPRICING
  - Fires when loss rate exceeds threshold
  - Silent when loss rate is below threshold
  - Silent when sample is below min_sample

REPEATED_LOW_CONFIDENCE
  - Fires when a step has ≥ min_runs low-confidence runs
  - Silent when below min_runs
  - Groups by step_name independently

REPEATED_FALLBACK
  - Fires when a step has ≥ min_runs runs with "fallback" in confidence_reason
  - Silent when below min_runs
  - Silent when confidence_reason does not contain "fallback"

REPEATED_REVIEW_FLAG
  - Fires when a pipeline has ≥ min_runs NEEDS_REVIEW runs
  - Silent when below min_runs
  - pipeline_name is propagated in signal and context

Scope / filters
  - signal_type filter runs only that detector
  - tenant_id isolates results
"""
from __future__ import annotations

import base64
import uuid

import pytest

from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

URL = "/api/intelligence/signals"


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
    lead_id: str | None = None,
    status: str = "COMPLETED",
    pipeline_name: str = "test_pipeline",
    overall_confidence_score: float | None = None,
    overall_confidence_label: str | None = None,
    error_category: str | None = None,
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=lead_id or _uid(),
        vertical_id="construction",
        trace_id=_uid(),
        pipeline_name=pipeline_name,
        engine_version="1.0.0",
        status=status,
        error_category=error_category,
        overall_confidence_score=overall_confidence_score,
        overall_confidence_label=overall_confidence_label,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _make_step(
    db,
    *,
    run: PipelineRun,
    step_name: str = "step_one",
    step_order: int = 1,
    status: str = "COMPLETED",
    confidence_score: float | None = None,
    confidence_label: str | None = None,
    confidence_reason: str | None = None,
    output_snapshot: dict | None = None,
) -> PipelineStepRun:
    step = PipelineStepRun(
        pipeline_run_id=run.id,
        step_name=step_name,
        step_order=step_order,
        status=status,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        confidence_reason=confidence_reason,
        output_snapshot=output_snapshot,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def _make_feedback(
    db,
    *,
    tenant_id: str,
    lead_id: str | None = None,
    outcome: str = "won",
    actual_price: float | None = None,
    estimated_price: float | None = None,
) -> LeadFeedback:
    fb = LeadFeedback(
        tenant_id=tenant_id,
        lead_id=lead_id or _uid(),
        outcome=outcome,
        actual_price=actual_price,
        estimated_price=estimated_price,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


class TestResponseEnvelope:
    def test_empty_scope_returns_zero(self, client, db, api_auth):
        """A tenant with no data → total=0, empty summary and items."""
        tid = f"int-empty-{_uid()}"
        r = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["summary"] == {}
        assert body["items"] == []

    def test_total_equals_items_length(self, client, db, api_auth):
        tid = f"int-len-{_uid()}"
        # Create enough NEEDS_REVIEW runs to fire repeated_review_flag
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == len(body["items"])

    def test_summary_counts_sum_to_total(self, client, db, api_auth):
        tid = f"int-summ-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        body = r.json()
        assert sum(body["summary"].values()) == body["total"]

    def test_item_required_fields_present(self, client, db, api_auth):
        """Every returned item carries the required envelope fields."""
        tid = f"int-fld-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        item = r.json()["items"][0]
        for key in ("signal_type", "severity", "description", "suggested_action", "context", "tenant_id"):
            assert key in item, f"Missing key: {key!r}"
        assert isinstance(item["description"], str) and item["description"]
        assert isinstance(item["suggested_action"], str) and item["suggested_action"]


# ---------------------------------------------------------------------------
# LIKELY_UNDERPRICING
# ---------------------------------------------------------------------------


class TestLikelyUnderpricing:
    def test_fires_when_fraction_met(self, client, db, api_auth):
        """
        6 of 6 won deals have actual < estimated × 0.9 → fires at min_fraction=0.60.
        """
        tid = f"up-fire-{_uid()}"
        for _ in range(6):
            _make_feedback(
                db, tenant_id=tid, outcome="won",
                actual_price=80.0, estimated_price=100.0,  # 80 < 90 → underpriced
            )
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "likely_underpricing",
                "pricing_min_sample": 5,
                "underpricing_threshold": 0.10,
                "underpricing_min_fraction": 0.60,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["signal_type"] == "likely_underpricing"
        assert item["severity"] == "medium"
        assert item["tenant_id"] == tid

    def test_context_fields(self, client, db, api_auth):
        tid = f"up-ctx-{_uid()}"
        for _ in range(6):
            _make_feedback(
                db, tenant_id=tid, outcome="won",
                actual_price=80.0, estimated_price=100.0,
            )
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "likely_underpricing",
                "pricing_min_sample": 5,
                "underpricing_threshold": 0.10,
                "underpricing_min_fraction": 0.60,
            },
            headers=api_auth,
        )
        ctx = r.json()["items"][0]["context"]
        assert ctx["sample_count"] == 6
        assert ctx["underpriced_count"] == 6
        assert ctx["underpriced_fraction"] == pytest.approx(1.0, abs=0.01)
        assert ctx["avg_actual_price"] == pytest.approx(80.0, abs=0.01)
        assert ctx["avg_estimated_price"] == pytest.approx(100.0, abs=0.01)
        assert ctx["threshold"] == pytest.approx(0.10)

    def test_silent_below_min_sample(self, client, db, api_auth):
        """Only 3 records < min_sample of 5 → silent."""
        tid = f"up-smp-{_uid()}"
        for _ in range(3):
            _make_feedback(
                db, tenant_id=tid, outcome="won",
                actual_price=80.0, estimated_price=100.0,
            )
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "likely_underpricing", "pricing_min_sample": 5},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_silent_when_fraction_below_threshold(self, client, db, api_auth):
        """Only 2 of 6 deals are underpriced → fraction 0.33 < min_fraction 0.60 → silent."""
        tid = f"up-frac-{_uid()}"
        for _ in range(2):
            _make_feedback(
                db, tenant_id=tid, outcome="won",
                actual_price=80.0, estimated_price=100.0,  # underpriced
            )
        for _ in range(4):
            _make_feedback(
                db, tenant_id=tid, outcome="won",
                actual_price=105.0, estimated_price=100.0,  # not underpriced
            )
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "likely_underpricing",
                "pricing_min_sample": 5,
                "underpricing_threshold": 0.10,
                "underpricing_min_fraction": 0.60,
            },
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_silent_when_only_lost_outcomes(self, client, db, api_auth):
        """LIKELY_UNDERPRICING only looks at won outcomes."""
        tid = f"up-lost-{_uid()}"
        for _ in range(6):
            _make_feedback(
                db, tenant_id=tid, outcome="lost",
                actual_price=80.0, estimated_price=100.0,
            )
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "likely_underpricing", "pricing_min_sample": 5},
            headers=api_auth,
        )
        assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# LIKELY_OVERPRICING
# ---------------------------------------------------------------------------


class TestLikelyOverpricing:
    def test_fires_when_loss_rate_exceeded(self, client, db, api_auth):
        """7 lost + 3 won = 70% loss rate > 60% threshold → fires."""
        tid = f"op-fire-{_uid()}"
        for _ in range(7):
            _make_feedback(db, tenant_id=tid, outcome="lost")
        for _ in range(3):
            _make_feedback(db, tenant_id=tid, outcome="won")
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "likely_overpricing",
                "pricing_min_sample": 5,
                "loss_rate_threshold": 0.60,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["signal_type"] == "likely_overpricing"
        assert item["severity"] == "medium"
        ctx = item["context"]
        assert ctx["lost_count"] == 7
        assert ctx["won_count"] == 3
        assert ctx["loss_rate"] == pytest.approx(0.70, abs=0.01)

    def test_silent_when_loss_rate_below_threshold(self, client, db, api_auth):
        """3 lost + 7 won = 30% loss rate < 60% threshold → silent."""
        tid = f"op-sil-{_uid()}"
        for _ in range(3):
            _make_feedback(db, tenant_id=tid, outcome="lost")
        for _ in range(7):
            _make_feedback(db, tenant_id=tid, outcome="won")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "likely_overpricing", "pricing_min_sample": 5},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_silent_below_min_sample(self, client, db, api_auth):
        """3 records total < min_sample=5 → silent even if all lost."""
        tid = f"op-smp-{_uid()}"
        for _ in range(3):
            _make_feedback(db, tenant_id=tid, outcome="lost")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "likely_overpricing", "pricing_min_sample": 5},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_fires_at_exact_threshold(self, client, db, api_auth):
        """Exactly 60% loss rate at threshold=0.60 → fires (>= comparison)."""
        tid = f"op-exact-{_uid()}"
        for _ in range(6):
            _make_feedback(db, tenant_id=tid, outcome="lost")
        for _ in range(4):
            _make_feedback(db, tenant_id=tid, outcome="won")
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "likely_overpricing",
                "pricing_min_sample": 5,
                "loss_rate_threshold": 0.60,
            },
            headers=api_auth,
        )
        assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# REPEATED_LOW_CONFIDENCE
# ---------------------------------------------------------------------------


class TestRepeatedLowConfidence:
    def test_fires_when_min_runs_met(self, client, db, api_auth):
        """5 step runs with confidence=0.20 < threshold=0.40 → fires."""
        tid = f"lc-fire-{_uid()}"
        for _ in range(5):
            run = _make_run(db, tenant_id=tid)
            _make_step(
                db, run=run, step_name="vision_step",
                confidence_score=0.20, confidence_label="low",
            )
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_low_confidence",
                "confidence_min_runs": 5,
                "confidence_low_threshold": 0.40,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["signal_type"] == "repeated_low_confidence"
        assert item["severity"] == "medium"
        ctx = item["context"]
        assert ctx["step_name"] == "vision_step"
        assert ctx["low_conf_count"] == 5
        assert ctx["avg_confidence_score"] == pytest.approx(0.20, abs=0.01)

    def test_silent_below_min_runs(self, client, db, api_auth):
        """4 low-confidence runs < min_runs=5 → silent."""
        tid = f"lc-sil-{_uid()}"
        for _ in range(4):
            run = _make_run(db, tenant_id=tid)
            _make_step(db, run=run, step_name="vision_step", confidence_score=0.20)
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_low_confidence",
                "confidence_min_runs": 5,
                "confidence_low_threshold": 0.40,
            },
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_silent_when_confidence_at_or_above_threshold(self, client, db, api_auth):
        """Steps with confidence=0.40 (exactly at threshold) are not low-confidence."""
        tid = f"lc-thr-{_uid()}"
        for _ in range(5):
            run = _make_run(db, tenant_id=tid)
            _make_step(db, run=run, step_name="vision_step", confidence_score=0.40)
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_low_confidence",
                "confidence_min_runs": 5,
                "confidence_low_threshold": 0.40,  # strict < not <=
            },
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_different_step_names_group_independently(self, client, db, api_auth):
        """Two steps each with 3 low-conf runs at min_runs=3 → two signals."""
        tid = f"lc-grp-{_uid()}"
        for _ in range(3):
            run = _make_run(db, tenant_id=tid)
            _make_step(db, run=run, step_name="step_a", confidence_score=0.10)
            _make_step(db, run=run, step_name="step_b", confidence_score=0.15)
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_low_confidence",
                "confidence_min_runs": 3,
                "confidence_low_threshold": 0.40,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 2
        step_names = {item["context"]["step_name"] for item in body["items"]}
        assert step_names == {"step_a", "step_b"}


# ---------------------------------------------------------------------------
# REPEATED_FALLBACK
# ---------------------------------------------------------------------------


class TestRepeatedFallback:
    def test_fires_when_min_runs_met(self, client, db, api_auth):
        """3 step runs with 'fallback' in confidence_reason → fires."""
        tid = f"fb-fire-{_uid()}"
        for _ in range(3):
            run = _make_run(db, tenant_id=tid)
            _make_step(
                db, run=run, step_name="estimate_step",
                confidence_reason="used fallback formula due to missing data",
            )
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_fallback",
                "fallback_min_runs": 3,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["signal_type"] == "repeated_fallback"
        assert item["severity"] == "medium"
        ctx = item["context"]
        assert ctx["step_name"] == "estimate_step"
        assert ctx["fallback_count"] == 3

    def test_silent_below_min_runs(self, client, db, api_auth):
        """2 fallback runs < min_runs=3 → silent."""
        tid = f"fb-sil-{_uid()}"
        for _ in range(2):
            run = _make_run(db, tenant_id=tid)
            _make_step(
                db, run=run, step_name="estimate_step",
                confidence_reason="fallback: missing input",
            )
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_fallback", "fallback_min_runs": 3},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_silent_when_reason_does_not_contain_fallback(self, client, db, api_auth):
        """confidence_reason without 'fallback' substring → silent."""
        tid = f"fb-kw-{_uid()}"
        for _ in range(5):
            run = _make_run(db, tenant_id=tid)
            _make_step(
                db, run=run, step_name="estimate_step",
                confidence_reason="normal estimation path",
            )
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_fallback", "fallback_min_runs": 3},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_case_insensitive_match(self, client, db, api_auth):
        """'FALLBACK' (uppercase) must also trigger the signal."""
        tid = f"fb-case-{_uid()}"
        for _ in range(3):
            run = _make_run(db, tenant_id=tid)
            _make_step(
                db, run=run, step_name="pricing_step",
                confidence_reason="FALLBACK: default pricing used",
            )
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_fallback", "fallback_min_runs": 3},
            headers=api_auth,
        )
        assert r.json()["total"] == 1


# ---------------------------------------------------------------------------
# REPEATED_REVIEW_FLAG
# ---------------------------------------------------------------------------


class TestRepeatedReviewFlag:
    def test_fires_at_min_runs(self, client, db, api_auth):
        """3 NEEDS_REVIEW runs for same pipeline → fires."""
        tid = f"rv-fire-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="score_pipe")
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_review_flag",
                "review_min_runs": 3,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["signal_type"] == "repeated_review_flag"
        assert item["severity"] == "low"
        assert item["pipeline_name"] == "score_pipe"
        ctx = item["context"]
        assert ctx["pipeline_name"] == "score_pipe"
        assert ctx["review_count"] == 3

    def test_silent_below_min_runs(self, client, db, api_auth):
        """2 NEEDS_REVIEW runs < min_runs=3 → silent."""
        tid = f"rv-sil-{_uid()}"
        for _ in range(2):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="score_pipe")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        assert r.json()["total"] == 0

    def test_different_pipelines_group_independently(self, client, db, api_auth):
        """Two pipelines each with 3 NEEDS_REVIEW → two signals."""
        tid = f"rv-grp-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="pipe_a")
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="pipe_b")
        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_review_flag",
                "review_min_runs": 3,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 2
        names = {item["pipeline_name"] for item in body["items"]}
        assert names == {"pipe_a", "pipe_b"}

    def test_completed_runs_not_counted(self, client, db, api_auth):
        """COMPLETED runs are not NEEDS_REVIEW — should not count."""
        tid = f"rv-stat-{_uid()}"
        for _ in range(5):
            _make_run(db, tenant_id=tid, status="COMPLETED", pipeline_name="score_pipe")
        r = client.get(
            URL,
            params={"tenant_id": tid, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# Signal type filter
# ---------------------------------------------------------------------------


class TestSignalTypeFilter:
    def test_signal_type_filter_runs_single_detector(self, client, db, api_auth):
        """
        With signal_type=repeated_review_flag, only that detector runs.
        A qualifying LIKELY_OVERPRICING pattern in the same tenant is excluded.
        """
        tid = f"sf-flt-{_uid()}"
        # Create overpricing condition
        for _ in range(7):
            _make_feedback(db, tenant_id=tid, outcome="lost")
        for _ in range(3):
            _make_feedback(db, tenant_id=tid, outcome="won")
        # Create review flag condition
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="score_pipe")

        r = client.get(
            URL,
            params={
                "tenant_id": tid,
                "signal_type": "repeated_review_flag",
                "review_min_runs": 3,
                "pricing_min_sample": 5,
            },
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] >= 1
        assert all(i["signal_type"] == "repeated_review_flag" for i in body["items"])

    def test_no_filter_runs_all_detectors(self, client, db, api_auth):
        """Without signal_type, all detectors run and their results combine."""
        tid = f"sf-all-{_uid()}"
        # Trigger review flag
        for _ in range(3):
            _make_run(db, tenant_id=tid, status="NEEDS_REVIEW", pipeline_name="test_pipe")

        r = client.get(
            URL,
            params={"tenant_id": tid, "review_min_runs": 3},
            headers=api_auth,
        )
        body = r.json()
        # At minimum the repeated_review_flag signal should be present
        types_present = {item["signal_type"] for item in body["items"]}
        assert "repeated_review_flag" in types_present


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_tenant_id_scopes_results(self, client, db, api_auth):
        """Signals from tenant B must not appear when scoped to tenant A."""
        tid_a = f"ti-a-{_uid()}"
        tid_b = f"ti-b-{_uid()}"
        # Both tenants have qualifying REPEATED_REVIEW_FLAG data
        for _ in range(3):
            _make_run(db, tenant_id=tid_a, status="NEEDS_REVIEW", pipeline_name="pipe_x")
        for _ in range(3):
            _make_run(db, tenant_id=tid_b, status="NEEDS_REVIEW", pipeline_name="pipe_x")

        r_a = client.get(
            URL,
            params={"tenant_id": tid_a, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )
        r_b = client.get(
            URL,
            params={"tenant_id": tid_b, "signal_type": "repeated_review_flag", "review_min_runs": 3},
            headers=api_auth,
        )

        assert r_a.json()["total"] == 1
        assert r_a.json()["items"][0]["tenant_id"] == tid_a
        assert r_b.json()["total"] == 1
        assert r_b.json()["items"][0]["tenant_id"] == tid_b
