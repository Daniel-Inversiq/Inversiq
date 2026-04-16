"""
tests/test_anomalies.py

Tests for GET /api/anomalies.

Design notes
------------
- Uses the shared session-scoped SQLite DB (no rollback between tests).
- Every test uses unique tenant_id / lead_id values to prevent cross-test
  contamination.
- The ``client`` fixture is session-scoped; ``db`` is function-scoped.
  Data committed via ``db`` is visible to the HTTP client because both
  use the same SQLite file and each HTTP request opens a fresh session.
- Basic-Auth credentials are both empty (matches conftest.py defaults).

Scenarios covered
-----------------
Response envelope
  - Empty scope → total=0, summary={}, items=[]
  - total always equals len(items)
  - summary counts sum to total

PRICE_DELTA_LARGE
  - Fires when |actual - estimated| / estimated > 0.50 (default)
  - Silent when delta is below the threshold
  - Silent when estimated_price is 0 (division guard)
  - Silent when either price is None
  - Custom threshold (0.30) fires what the default threshold misses
  - Context fields: actual_price, estimated_price, delta_ratio, threshold, outcome, feedback_id

FAILED_HIGH_CONFIDENCE
  - Fires for FAILED run with confidence >= 0.60 (default)
  - Silent when confidence is below threshold
  - Silent when run is COMPLETED (not FAILED)
  - Fires at exactly the threshold value (>= not >)
  - Custom threshold silences a previously-firing run

MISSING_STEP_OUTPUT
  - Fires for COMPLETED step with output_snapshot=None
  - Silent when output_snapshot is present (even as {})
  - Silent for FAILED step with output_snapshot=None (only COMPLETED triggers)
  - Context fields: step_name, step_use, step_order, step_contract_version, duration_ms

CONFIDENCE_ABSENT_ON_COMPLETION
  - Fires for COMPLETED run with overall_confidence_score=None
  - Silent when confidence score is present
  - Silent for FAILED run with no confidence score

REPEATED_FAILURE
  - Fires when same (tenant_id, pipeline_name) has >= 3 FAILEDs in last 24 h
  - Silent when failure count is below the minimum
  - Custom repeat_failure_min_count=2 fires what the default misses
  - Different pipeline names group independently (no cross-pipeline merging)
  - context.run_ids lists all contributing run IDs

Scope filters
  - tenant_id: anomalies from other tenants are excluded
  - lead_id: only anomalies for that lead
  - pipeline_run_id: only anomalies for that specific run
  - anomaly_type: only the named detector runs; other types absent from results
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

URL = "/api/anomalies"


@pytest.fixture
def api_auth():
    """Basic-Auth header with empty credentials (matches conftest.py defaults)."""
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _make_run(
    db,
    *,
    tenant_id: str | None = None,
    lead_id: str | None = None,
    status: str = "COMPLETED",
    pipeline_name: str = "test_pipeline",
    engine_version: str = "0.1.0",
    config_hash: str | None = "abc123def456",
    overall_confidence_score: float | None = None,
    overall_confidence_label: str | None = None,
    failure_step: str | None = None,
    error_category: str | None = None,
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id or f"t-{_uid()}",
        lead_id=lead_id or _uid(),
        vertical_id="painting",
        trace_id=_uid(),
        pipeline_name=pipeline_name,
        engine_version=engine_version,
        config_hash=config_hash,
        status=status,
        failure_step=failure_step,
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
    step_use: str | None = None,
    step_contract_version: str | None = None,
    status: str = "COMPLETED",
    output_snapshot: dict | None = None,
    duration_ms: int | None = None,
) -> PipelineStepRun:
    step = PipelineStepRun(
        pipeline_run_id=run.id,
        step_name=step_name,
        step_order=step_order,
        step_use=step_use,
        step_contract_version=step_contract_version,
        status=status,
        output_snapshot=output_snapshot,
        duration_ms=duration_ms,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def _make_feedback(
    db,
    *,
    tenant_id: str,
    lead_id: str,
    pipeline_run_id: int | None = None,
    outcome: str = "won",
    actual_price: float | None = None,
    estimated_price: float | None = None,
) -> LeadFeedback:
    fb = LeadFeedback(
        tenant_id=tenant_id,
        lead_id=lead_id,
        pipeline_run_id=pipeline_run_id,
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
        tid = f"env-empty-{_uid()}"
        r = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["summary"] == {}
        assert body["items"] == []

    def test_total_equals_items_length(self, client, db, api_auth):
        """``total`` always equals ``len(items)``."""
        tid = f"env-len-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        _make_step(db, run=run, status="COMPLETED", output_snapshot=None)
        r = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = r.json()
        assert body["total"] == len(body["items"])

    def test_summary_counts_sum_to_total(self, client, db, api_auth):
        """Sum of all ``summary`` values equals ``total``."""
        tid = f"env-summ-{_uid()}"
        # CONFIDENCE_ABSENT_ON_COMPLETION
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        # MISSING_STEP_OUTPUT
        run2 = _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=0.8)
        _make_step(db, run=run2, status="COMPLETED", output_snapshot=None)
        r = client.get(URL, params={"tenant_id": tid}, headers=api_auth)
        body = r.json()
        assert sum(body["summary"].values()) == body["total"]

    def test_item_fields_present(self, client, db, api_auth):
        """Every item contains the expected envelope fields."""
        tid = f"env-fld-{_uid()}"
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth)
        item = r.json()["items"][0]
        for key in ("anomaly_type", "severity", "description", "context", "pipeline_run_id", "pipeline_step_run_id", "lead_id", "tenant_id"):
            assert key in item, f"Missing key: {key!r}"


# ---------------------------------------------------------------------------
# PRICE_DELTA_LARGE
# ---------------------------------------------------------------------------


class TestPriceDeltaLarge:
    def test_fires_above_default_threshold(self, client, db, api_auth):
        """100 % price delta (actual=200, estimated=100) → fires at 50 % default."""
        tid = f"pd-fire-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=200.0, estimated_price=100.0,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["anomaly_type"] == "PRICE_DELTA_LARGE"
        assert item["severity"] == "high"
        assert item["tenant_id"] == tid
        assert item["context"]["delta_ratio"] == pytest.approx(1.0, abs=0.001)

    def test_silent_below_threshold(self, client, db, api_auth):
        """40 % delta is below the 50 % default → no anomaly."""
        tid = f"pd-sil-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=140.0, estimated_price=100.0,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_silent_when_estimated_is_zero(self, client, db, api_auth):
        """estimated_price=0 must be skipped to avoid division-by-zero."""
        tid = f"pd-zero-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=500.0, estimated_price=0.0,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_silent_when_price_is_none(self, client, db, api_auth):
        """Feedback missing actual_price should not trigger the detector."""
        tid = f"pd-none-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=None, estimated_price=100.0,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_custom_threshold_lowers_bar(self, client, db, api_auth):
        """delta=40 % is silent at 0.50 but fires when threshold is lowered to 0.30."""
        tid = f"pd-thresh-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=140.0, estimated_price=100.0,
        )
        # Default threshold: silent
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        assert r.json()["total"] == 0
        # Custom lower threshold: fires
        r2 = client.get(
            URL,
            params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE", "price_delta_threshold": 0.30},
            headers=api_auth,
        )
        assert r2.json()["total"] == 1

    def test_context_fields(self, client, db, api_auth):
        """All expected context keys are present with correct values."""
        tid = f"pd-ctx-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=300.0, estimated_price=100.0, outcome="lost",
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        ctx = r.json()["items"][0]["context"]
        assert ctx["actual_price"] == pytest.approx(300.0)
        assert ctx["estimated_price"] == pytest.approx(100.0)
        assert ctx["delta_ratio"] == pytest.approx(2.0, abs=0.001)
        assert ctx["threshold"] == pytest.approx(0.50)
        assert ctx["outcome"] == "lost"
        assert "feedback_id" in ctx


# ---------------------------------------------------------------------------
# FAILED_HIGH_CONFIDENCE
# ---------------------------------------------------------------------------


class TestFailedHighConfidence:
    def test_fires_for_failed_run_with_high_confidence(self, client, db, api_auth):
        tid = f"fhc-fire-{_uid()}"
        run = _make_run(
            db, tenant_id=tid, status="FAILED",
            overall_confidence_score=0.85, overall_confidence_label="high",
            failure_step="scoring_step", error_category="transient",
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["anomaly_type"] == "FAILED_HIGH_CONFIDENCE"
        assert item["severity"] == "high"
        assert item["pipeline_run_id"] == run.id
        ctx = item["context"]
        assert ctx["overall_confidence_score"] == pytest.approx(0.85)
        assert ctx["overall_confidence_label"] == "high"
        assert ctx["failure_step"] == "scoring_step"
        assert ctx["error_category"] == "transient"
        assert ctx["confidence_threshold"] == pytest.approx(0.60)

    def test_silent_when_confidence_below_threshold(self, client, db, api_auth):
        """FAILED with confidence=0.50 is below the 0.60 default → silent."""
        tid = f"fhc-sil-{_uid()}"
        _make_run(db, tenant_id=tid, status="FAILED", overall_confidence_score=0.50)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_silent_for_completed_run(self, client, db, api_auth):
        """COMPLETED run with high confidence score is not contradictory → silent."""
        tid = f"fhc-comp-{_uid()}"
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=0.95)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_fires_at_exact_threshold(self, client, db, api_auth):
        """Score exactly equal to threshold triggers (>= comparison)."""
        tid = f"fhc-exact-{_uid()}"
        _make_run(db, tenant_id=tid, status="FAILED", overall_confidence_score=0.60)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        assert r.json()["total"] == 1

    def test_custom_threshold_silences(self, client, db, api_auth):
        """score=0.70 fires at default (0.60) but not at a raised threshold (0.80)."""
        tid = f"fhc-thresh-{_uid()}"
        _make_run(db, tenant_id=tid, status="FAILED", overall_confidence_score=0.70)
        # Default: fires
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        assert r.json()["total"] == 1
        # Raised threshold: silent
        r2 = client.get(
            URL,
            params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE", "confidence_threshold": 0.80},
            headers=api_auth,
        )
        assert r2.json()["total"] == 0


# ---------------------------------------------------------------------------
# MISSING_STEP_OUTPUT
# ---------------------------------------------------------------------------


class TestMissingStepOutput:
    def test_fires_for_completed_step_without_snapshot(self, client, db, api_auth):
        tid = f"mso-fire-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="COMPLETED")
        step = _make_step(
            db, run=run, step_name="parse_step", step_order=2,
            step_use="parser_v2", step_contract_version="1.0",
            status="COMPLETED", output_snapshot=None, duration_ms=120,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "MISSING_STEP_OUTPUT"}, headers=api_auth)
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["anomaly_type"] == "MISSING_STEP_OUTPUT"
        assert item["severity"] == "medium"
        assert item["pipeline_run_id"] == run.id
        assert item["pipeline_step_run_id"] == step.id
        ctx = item["context"]
        assert ctx["step_name"] == "parse_step"
        assert ctx["step_use"] == "parser_v2"
        assert ctx["step_order"] == 2
        assert ctx["step_contract_version"] == "1.0"
        assert ctx["duration_ms"] == 120

    def test_silent_when_output_snapshot_present(self, client, db, api_auth):
        """COMPLETED step with a non-null output_snapshot is healthy → silent."""
        tid = f"mso-snap-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="COMPLETED")
        _make_step(db, run=run, status="COMPLETED", output_snapshot={"result": "ok"})
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "MISSING_STEP_OUTPUT"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_silent_for_failed_step_without_snapshot(self, client, db, api_auth):
        """FAILED steps are expected to have no output → should not fire."""
        tid = f"mso-fail-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="FAILED")
        _make_step(db, run=run, status="FAILED", output_snapshot=None)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "MISSING_STEP_OUTPUT"}, headers=api_auth)
        assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# CONFIDENCE_ABSENT_ON_COMPLETION
# ---------------------------------------------------------------------------


class TestConfidenceAbsentOnCompletion:
    def test_fires_for_completed_run_without_confidence(self, client, db, api_auth):
        tid = f"cac-fire-{_uid()}"
        run = _make_run(
            db, tenant_id=tid, status="COMPLETED",
            overall_confidence_score=None,
            pipeline_name="score_pipe", engine_version="1.2.0",
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth)
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["anomaly_type"] == "CONFIDENCE_ABSENT_ON_COMPLETION"
        assert item["severity"] == "low"
        assert item["pipeline_run_id"] == run.id
        assert item["tenant_id"] == tid
        ctx = item["context"]
        assert ctx["pipeline_name"] == "score_pipe"
        assert ctx["engine_version"] == "1.2.0"

    def test_silent_when_confidence_score_present(self, client, db, api_auth):
        """COMPLETED run with a confidence score is healthy → silent."""
        tid = f"cac-scr-{_uid()}"
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=0.75)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_silent_for_failed_run_without_confidence(self, client, db, api_auth):
        """FAILED runs with no confidence are expected → detector only watches COMPLETED."""
        tid = f"cac-fail-{_uid()}"
        _make_run(db, tenant_id=tid, status="FAILED", overall_confidence_score=None)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth)
        assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# REPEATED_FAILURE
# ---------------------------------------------------------------------------


class TestRepeatedFailure:
    def test_fires_at_default_threshold(self, client, db, api_auth):
        """3 FAILEDs for (tenant, pipeline) within 24 h → fires."""
        tid = f"rf-fire-{_uid()}"
        runs = [
            _make_run(db, tenant_id=tid, pipeline_name="batch_pipe", status="FAILED", error_category="transient")
            for _ in range(3)
        ]
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["anomaly_type"] == "REPEATED_FAILURE"
        assert item["severity"] == "high"
        assert item["tenant_id"] == tid
        ctx = item["context"]
        assert ctx["pipeline_name"] == "batch_pipe"
        assert ctx["failure_count"] == 3
        assert ctx["window_hours"] == 24
        assert ctx["min_failures"] == 3
        assert "transient" in ctx["error_categories"]
        assert set(ctx["run_ids"]) == {r_.id for r_ in runs}

    def test_silent_below_threshold(self, client, db, api_auth):
        """2 FAILEDs < 3 minimum → silent."""
        tid = f"rf-sil-{_uid()}"
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name="batch_pipe", status="FAILED")
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        assert r.json()["total"] == 0

    def test_custom_min_count_lowers_bar(self, client, db, api_auth):
        """2 FAILEDs at repeat_failure_min_count=2 → fires."""
        tid = f"rf-min-{_uid()}"
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name="batch_pipe", status="FAILED")
        r = client.get(
            URL,
            params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE", "repeat_failure_min_count": 2},
            headers=api_auth,
        )
        assert r.json()["total"] == 1

    def test_separate_pipelines_group_independently(self, client, db, api_auth):
        """Failures on pipe_a and pipe_b never merge into a combined count."""
        tid = f"rf-sep-{_uid()}"
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name="pipe_a", status="FAILED")
        for _ in range(2):
            _make_run(db, tenant_id=tid, pipeline_name="pipe_b", status="FAILED")

        # Neither reaches 3 → both silent
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        assert r.json()["total"] == 0

        # With min_count=2, each pipeline fires as a separate anomaly
        r2 = client.get(
            URL,
            params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE", "repeat_failure_min_count": 2},
            headers=api_auth,
        )
        assert r2.json()["total"] == 2

    def test_context_run_ids_complete(self, client, db, api_auth):
        """context.run_ids lists every contributing run ID."""
        tid = f"rf-ids-{_uid()}"
        runs = [_make_run(db, tenant_id=tid, pipeline_name="pipe_x", status="FAILED") for _ in range(3)]
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        ctx = r.json()["items"][0]["context"]
        assert set(ctx["run_ids"]) == {run.id for run in runs}


# ---------------------------------------------------------------------------
# Scope filters
# ---------------------------------------------------------------------------


class TestScopeFilters:
    def test_tenant_id_isolates_results(self, client, db, api_auth):
        """Two tenants each have a CONFIDENCE_ABSENT anomaly; scoping returns only one."""
        tid_a = f"tf-a-{_uid()}"
        tid_b = f"tf-b-{_uid()}"
        _make_run(db, tenant_id=tid_a, status="COMPLETED", overall_confidence_score=None)
        _make_run(db, tenant_id=tid_b, status="COMPLETED", overall_confidence_score=None)

        r_a = client.get(
            URL, params={"tenant_id": tid_a, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth
        )
        r_b = client.get(
            URL, params={"tenant_id": tid_b, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth
        )

        assert r_a.json()["total"] == 1
        assert r_a.json()["items"][0]["tenant_id"] == tid_a
        assert r_b.json()["total"] == 1
        assert r_b.json()["items"][0]["tenant_id"] == tid_b

    def test_lead_id_filter(self, client, db, api_auth):
        """Two leads in the same tenant — scoping to one lead returns only its anomaly."""
        tid = f"lf-{_uid()}"
        lead_a = _uid()
        lead_b = _uid()
        _make_run(db, tenant_id=tid, lead_id=lead_a, status="COMPLETED", overall_confidence_score=None)
        _make_run(db, tenant_id=tid, lead_id=lead_b, status="COMPLETED", overall_confidence_score=None)

        r = client.get(
            URL,
            params={"tenant_id": tid, "lead_id": lead_a, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"},
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["lead_id"] == lead_a

    def test_pipeline_run_id_filter(self, client, db, api_auth):
        """Scoping to a specific pipeline_run_id returns only anomalies for that run."""
        tid = f"prf-{_uid()}"
        run_a = _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)

        r = client.get(
            URL,
            params={"pipeline_run_id": run_a.id, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"},
            headers=api_auth,
        )
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["pipeline_run_id"] == run_a.id

    def test_anomaly_type_filter_runs_single_detector(self, client, db, api_auth):
        """
        anomaly_type=PRICE_DELTA_LARGE runs only that detector.
        A CONFIDENCE_ABSENT_ON_COMPLETION anomaly in the same tenant is excluded.
        """
        tid = f"atf-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        # This feedback creates a PRICE_DELTA_LARGE anomaly
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=300.0, estimated_price=100.0,
        )

        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        body = r.json()
        assert body["total"] >= 1
        assert all(i["anomaly_type"] == "PRICE_DELTA_LARGE" for i in body["items"])


# ---------------------------------------------------------------------------
# Triage fields
# ---------------------------------------------------------------------------


class TestTriageFields:
    """
    Verify that every anomaly item carries ``review_recommended`` (bool) and
    ``action_hint`` (non-empty string), and that the values follow the
    per-type triage rules.
    """

    def test_triage_fields_present_on_every_item(self, client, db, api_auth):
        """Both triage fields must appear in every returned item."""
        tid = f"tr-fld-{_uid()}"
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        r = client.get(
            URL,
            params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"},
            headers=api_auth,
        )
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert "review_recommended" in item, "Missing review_recommended"
            assert "action_hint" in item, "Missing action_hint"
            assert isinstance(item["review_recommended"], bool)
            assert isinstance(item["action_hint"], str) and item["action_hint"]

    def test_price_delta_review_recommended(self, client, db, api_auth):
        """PRICE_DELTA_LARGE always recommends review."""
        tid = f"tr-pd-{_uid()}"
        run = _make_run(db, tenant_id=tid)
        _make_feedback(
            db, tenant_id=tid, lead_id=run.lead_id,
            pipeline_run_id=run.id, actual_price=300.0, estimated_price=100.0,
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "PRICE_DELTA_LARGE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "pricing" in item["action_hint"].lower() or "price" in item["action_hint"].lower()

    def test_failed_high_confidence_transient_gets_retry_hint(self, client, db, api_auth):
        """FAILED_HIGH_CONFIDENCE with error_category=transient → retry hint."""
        tid = f"tr-fhc-t-{_uid()}"
        _make_run(
            db, tenant_id=tid, status="FAILED",
            overall_confidence_score=0.80, error_category="transient",
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "retry" in item["action_hint"].lower()

    def test_failed_high_confidence_permanent_gets_investigate_hint(self, client, db, api_auth):
        """FAILED_HIGH_CONFIDENCE with error_category=permanent → investigate hint."""
        tid = f"tr-fhc-p-{_uid()}"
        _make_run(
            db, tenant_id=tid, status="FAILED",
            overall_confidence_score=0.80, error_category="permanent",
        )
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "FAILED_HIGH_CONFIDENCE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "investigate" in item["action_hint"].lower() or "failure step" in item["action_hint"].lower()

    def test_confidence_absent_review_not_recommended(self, client, db, api_auth):
        """CONFIDENCE_ABSENT_ON_COMPLETION is a coverage gap, not an incident → review_recommended=False."""
        tid = f"tr-cac-{_uid()}"
        _make_run(db, tenant_id=tid, status="COMPLETED", overall_confidence_score=None)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "CONFIDENCE_ABSENT_ON_COMPLETION"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is False
        assert item["action_hint"]  # hint is still present even when not urgent

    def test_missing_step_output_review_recommended(self, client, db, api_auth):
        """MISSING_STEP_OUTPUT always recommends review."""
        tid = f"tr-mso-{_uid()}"
        run = _make_run(db, tenant_id=tid, status="COMPLETED")
        _make_step(db, run=run, status="COMPLETED", output_snapshot=None)
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "MISSING_STEP_OUTPUT"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "step" in item["action_hint"].lower()

    def test_repeated_failure_transient_gets_infra_hint(self, client, db, api_auth):
        """REPEATED_FAILURE with only transient errors → infrastructure hint."""
        tid = f"tr-rf-t-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, pipeline_name="pipe_t", status="FAILED", error_category="transient")
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "infrastructure" in item["action_hint"].lower() or "transient" in item["action_hint"].lower()

    def test_repeated_failure_permanent_gets_bug_hint(self, client, db, api_auth):
        """REPEATED_FAILURE with only permanent errors → bug-fix hint."""
        tid = f"tr-rf-p-{_uid()}"
        for _ in range(3):
            _make_run(db, tenant_id=tid, pipeline_name="pipe_p", status="FAILED", error_category="permanent")
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        assert "bug" in item["action_hint"].lower() or "fix" in item["action_hint"].lower() or "permanent" in item["action_hint"].lower()

    def test_repeated_failure_mixed_categories_gets_generic_hint(self, client, db, api_auth):
        """REPEATED_FAILURE with mixed error categories → generic investigate hint."""
        tid = f"tr-rf-m-{_uid()}"
        _make_run(db, tenant_id=tid, pipeline_name="pipe_m", status="FAILED", error_category="transient")
        _make_run(db, tenant_id=tid, pipeline_name="pipe_m", status="FAILED", error_category="permanent")
        _make_run(db, tenant_id=tid, pipeline_name="pipe_m", status="FAILED", error_category="validation")
        r = client.get(URL, params={"tenant_id": tid, "anomaly_type": "REPEATED_FAILURE"}, headers=api_auth)
        item = r.json()["items"][0]
        assert item["review_recommended"] is True
        # Mixed → neither pure infra nor pure bug hint
        assert "transient" not in item["action_hint"].lower()
        assert item["action_hint"]
