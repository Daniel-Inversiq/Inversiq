"""
tests/test_pipeline_run_debug.py

Tests for GET /api/pipeline-runs/{id}/debug.

Design notes
------------
- The test SQLite DB is shared across the session and is NOT rolled back between
  tests.  Every test inserts its own PipelineRun so queries cannot bleed across.
- The ``client`` and ``db`` fixtures both target the same SQLite file; rows
  committed via ``db`` are immediately visible to the HTTP client.
- Basic-Auth credentials default to "" in tests (see conftest.py), so the
  ``api_auth`` fixture sends ``Authorization: Basic <base64(":")>``.

Scenarios covered
-----------------
- 404 for non-existent run
- Top-level response structure: run / steps / events / feedback / summary keys
- Run with multiple steps and events → correct summary counts
- step_use and step_contract_version present in debug step view
- Events returned in chronological order (occurred_at ASC)
- No feedback → feedback is null, has_feedback is False
- One feedback row → serialised correctly (actual_price, estimated_price, notes)
- Multiple feedback rows → all returned
- Null actual_price stays null (not coerced to 0)
- Null estimated_price stays null when absent
- Failed run → status, error_category, failure_step reflected; recoverability hint
- All four error_category → recoverability mappings
- NEEDS_REVIEW run → status reflected; NEEDS_REVIEW steps not counted as failed/skipped
- Run-level confidence fields present when stored, null when absent
- Step-level confidence fields present when stored, null when absent
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

import pytest

from app.models.engine_event import EngineEvent
from app.models.lead_feedback import LeadFeedback
from app.models.pipeline_run import PipelineRun, PipelineStepRun


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def api_auth():
    """Basic-Auth header — user:pass both empty (matches conftest defaults)."""
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


def _make_run(
    db,
    *,
    status: str = "COMPLETED",
    error_category: str | None = None,
    failure_step: str | None = None,
    overall_confidence_score: float | None = None,
    overall_confidence_label: str | None = None,
    config_hash: str | None = None,
    engine_version: str = "0.1.0",
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=f"t-{uuid.uuid4().hex[:8]}",
        lead_id=uuid.uuid4().hex,
        vertical_id="painting",
        trace_id=uuid.uuid4().hex,
        pipeline_name="test_pipeline",
        engine_version=engine_version,
        status=status,
        error_category=error_category,
        failure_step=failure_step,
        overall_confidence_score=overall_confidence_score,
        overall_confidence_label=overall_confidence_label,
        config_hash=config_hash,
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
    step_use: str | None = None,
    step_contract_version: str | None = None,
    confidence_score: float | None = None,
    confidence_label: str | None = None,
    confidence_reason: str | None = None,
    error_message: str | None = None,
    error_type: str | None = None,
    error_category: str | None = None,
) -> PipelineStepRun:
    step = PipelineStepRun(
        pipeline_run_id=run.id,
        step_name=step_name,
        step_use=step_use,
        step_contract_version=step_contract_version,
        step_order=step_order,
        status=status,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        confidence_reason=confidence_reason,
        error_message=error_message,
        error_type=error_type,
        error_category=error_category,
    )
    db.add(step)
    db.commit()
    return step


def _make_event(
    db,
    *,
    run: PipelineRun,
    event_type: str = "pipeline.started",
    status: str = "RUNNING",
    occurred_at: datetime | None = None,
) -> EngineEvent:
    kwargs: dict = dict(
        event_type=event_type,
        tenant_id=run.tenant_id,
        lead_id=run.lead_id,
        vertical_id=run.vertical_id,
        trace_id=run.trace_id,
        pipeline_run_id=run.id,
        status=status,
    )
    if occurred_at is not None:
        kwargs["occurred_at"] = occurred_at
    event = EngineEvent(**kwargs)
    db.add(event)
    db.commit()
    return event


def _make_feedback(
    db,
    *,
    run: PipelineRun,
    outcome: str = "won",
    actual_price: float | None = None,
    notes: str | None = None,
) -> LeadFeedback:
    fb = LeadFeedback(
        tenant_id=run.tenant_id,
        lead_id=run.lead_id,
        pipeline_run_id=run.id,
        outcome=outcome,
        actual_price=actual_price,
        notes=notes,
    )
    db.add(fb)
    db.commit()
    return fb


# ---------------------------------------------------------------------------
# 1. Not found
# ---------------------------------------------------------------------------

class TestDebugEndpointNotFound:

    def test_returns_404_for_missing_run(self, client, api_auth):
        resp = client.get("/api/pipeline-runs/9999999/debug", headers=api_auth)
        assert resp.status_code == 404
        assert "9999999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Response structure
# ---------------------------------------------------------------------------

class TestDebugResponseStructure:

    def test_top_level_keys(self, client, db, api_auth):
        run = _make_run(db)
        resp = client.get(f"/api/pipeline-runs/{run.id}/debug", headers=api_auth)
        assert resp.status_code == 200
        assert set(resp.json().keys()) == {"run", "steps", "events", "feedback", "anomalies", "review", "summary"}

    def test_run_section_fields(self, client, db, api_auth):
        run = _make_run(db, config_hash="abc123456789")
        run_section = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["run"]

        required = {
            "id", "tenant_id", "lead_id", "vertical_id", "trace_id",
            "pipeline_name", "engine_version", "config_hash", "status",
            "failure_step", "error_category",
            "overall_confidence_score", "overall_confidence_label",
            "started_at", "completed_at", "created_at", "updated_at",
        }
        assert required.issubset(run_section.keys())
        assert run_section["config_hash"] == "abc123456789"

    def test_summary_section_fields(self, client, db, api_auth):
        run = _make_run(db)
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]

        assert set(summary.keys()) == {
            "total_steps", "completed_steps", "failed_steps", "skipped_steps",
            "event_count", "has_feedback", "recoverability", "anomaly_count",
            "review_recommended", "review_priority",
        }

    def test_empty_run_has_zero_counts(self, client, db, api_auth):
        run = _make_run(db)
        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()

        assert body["steps"] == []
        assert body["events"] == []
        assert body["summary"]["total_steps"] == 0
        assert body["summary"]["event_count"] == 0


# ---------------------------------------------------------------------------
# 3. Steps and events
# ---------------------------------------------------------------------------

class TestDebugWithStepsAndEvents:

    def test_steps_returned_in_order(self, client, db, api_auth):
        run = _make_run(db)
        _make_step(db, run=run, step_name="s1", step_order=1)
        _make_step(db, run=run, step_name="s2", step_order=2)
        _make_step(db, run=run, step_name="s3", step_order=3)

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert [s["step_name"] for s in steps] == ["s1", "s2", "s3"]

    def test_summary_counts_by_status(self, client, db, api_auth):
        run = _make_run(db)
        _make_step(db, run=run, step_name="a", step_order=1, status="COMPLETED")
        _make_step(db, run=run, step_name="b", step_order=2, status="COMPLETED")
        _make_step(db, run=run, step_name="c", step_order=3, status="FAILED")
        _make_step(db, run=run, step_name="d", step_order=4, status="SKIPPED")

        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]

        assert summary["total_steps"] == 4
        assert summary["completed_steps"] == 2
        assert summary["failed_steps"] == 1
        assert summary["skipped_steps"] == 1

    def test_events_count_in_summary(self, client, db, api_auth):
        run = _make_run(db)
        _make_event(db, run=run, event_type="pipeline.started", status="RUNNING")
        _make_event(db, run=run, event_type="pipeline.completed", status="COMPLETED")

        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        assert len(body["events"]) == 2
        assert body["summary"]["event_count"] == 2

    def test_step_debug_includes_step_use_and_contract_version(self, client, db, api_auth):
        run = _make_run(db)
        _make_step(
            db, run=run,
            step_use="painting.estimate.v2",
            step_contract_version="1.2.0",
        )

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert steps[0]["step_use"] == "painting.estimate.v2"
        assert steps[0]["step_contract_version"] == "1.2.0"

    def test_step_debug_includes_snapshots(self, client, db, api_auth):
        run = _make_run(db)
        step = _make_step(db, run=run)
        step.input_snapshot = {"sqft": 1200}
        step.output_snapshot = {"price": 950.0}
        db.commit()

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert steps[0]["input_snapshot"] == {"sqft": 1200}
        assert steps[0]["output_snapshot"] == {"price": 950.0}

    def test_events_returned_in_chronological_order(self, client, db, api_auth):
        """Events must be oldest-first (occurred_at ASC) as stated in the docstring."""
        run = _make_run(db)
        t1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
        t3 = datetime(2024, 1, 1, 10, 0, 2, tzinfo=timezone.utc)
        # Insert deliberately out-of-order so the test fails if sorting is absent.
        _make_event(db, run=run, event_type="pipeline.completed", status="COMPLETED", occurred_at=t3)
        _make_event(db, run=run, event_type="step.started", status="RUNNING", occurred_at=t2)
        _make_event(db, run=run, event_type="pipeline.started", status="RUNNING", occurred_at=t1)

        events = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["events"]
        assert len(events) == 3
        assert [e["event_type"] for e in events] == [
            "pipeline.started",
            "step.started",
            "pipeline.completed",
        ]


# ---------------------------------------------------------------------------
# 4. Feedback
# ---------------------------------------------------------------------------

class TestDebugFeedback:

    def test_no_feedback_returns_null(self, client, db, api_auth):
        run = _make_run(db)
        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        assert body["feedback"] is None
        assert body["summary"]["has_feedback"] is False

    def test_one_feedback_row_serialised(self, client, db, api_auth):
        run = _make_run(db)
        _make_feedback(db, run=run, outcome="won", actual_price=1200.0, notes="good fit")

        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        feedback = body["feedback"]
        assert isinstance(feedback, list)
        assert len(feedback) == 1
        assert feedback[0]["outcome"] == "won"
        assert feedback[0]["actual_price"] == pytest.approx(1200.0)
        assert feedback[0]["notes"] == "good fit"
        assert body["summary"]["has_feedback"] is True

    def test_multiple_feedback_rows_all_returned(self, client, db, api_auth):
        run = _make_run(db)
        _make_feedback(db, run=run, outcome="won")
        _make_feedback(db, run=run, outcome="lost")

        feedback = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["feedback"]
        assert isinstance(feedback, list)
        assert len(feedback) == 2
        assert {f["outcome"] for f in feedback} == {"won", "lost"}

    def test_null_actual_price_stays_null(self, client, db, api_auth):
        """actual_price=None must not be coerced to 0 or any other value."""
        run = _make_run(db)
        _make_feedback(db, run=run, outcome="lost", actual_price=None)

        feedback = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["feedback"]
        assert feedback[0]["actual_price"] is None

    def test_null_estimated_price_stays_null(self, client, db, api_auth):
        """estimated_price omitted at insert must serialize as null, not 0."""
        run = _make_run(db)
        _make_feedback(db, run=run, outcome="won")

        feedback = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["feedback"]
        assert feedback[0]["estimated_price"] is None


# ---------------------------------------------------------------------------
# 5. Failed run
# ---------------------------------------------------------------------------

class TestDebugFailedRun:

    def test_failed_run_fields_in_run_section(self, client, db, api_auth):
        run = _make_run(
            db, status="FAILED", error_category="transient", failure_step="step_two"
        )
        run_section = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["run"]
        assert run_section["status"] == "FAILED"
        assert run_section["error_category"] == "transient"
        assert run_section["failure_step"] == "step_two"

    def test_transient_recoverability_is_retryable(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", error_category="transient")
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "retryable"

    def test_external_dependency_recoverability_is_retryable(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", error_category="external_dependency")
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "retryable"

    def test_permanent_recoverability_is_terminal(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", error_category="permanent")
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "terminal"

    def test_validation_recoverability_is_terminal(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", error_category="validation")
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "terminal"

    def test_no_error_category_recoverability_is_unknown(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", error_category=None)
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "unknown"

    def test_failed_step_error_fields_present(self, client, db, api_auth):
        run = _make_run(db, status="FAILED", failure_step="bad_step")
        _make_step(
            db, run=run, step_name="bad_step",
            status="FAILED",
            error_type="ValueError",
            error_message="something went wrong",
            error_category="permanent",
        )

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert steps[0]["error_type"] == "ValueError"
        assert steps[0]["error_message"] == "something went wrong"
        assert steps[0]["error_category"] == "permanent"


# ---------------------------------------------------------------------------
# 6. NEEDS_REVIEW run
# ---------------------------------------------------------------------------

class TestDebugNeedsReviewRun:

    def test_needs_review_status_and_failure_step(self, client, db, api_auth):
        run = _make_run(db, status="NEEDS_REVIEW", failure_step="review_step")
        run_section = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["run"]
        assert run_section["status"] == "NEEDS_REVIEW"
        assert run_section["failure_step"] == "review_step"

    def test_needs_review_steps_not_counted_as_failed_or_skipped(self, client, db, api_auth):
        run = _make_run(db, status="NEEDS_REVIEW")
        _make_step(db, run=run, step_name="s1", step_order=1, status="COMPLETED")
        _make_step(db, run=run, step_name="s2", step_order=2, status="NEEDS_REVIEW")

        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["total_steps"] == 2
        assert summary["completed_steps"] == 1
        assert summary["failed_steps"] == 0
        assert summary["skipped_steps"] == 0

    def test_needs_review_recoverability_is_unknown(self, client, db, api_auth):
        """NEEDS_REVIEW runs have no error_category → recoverability unknown."""
        run = _make_run(db, status="NEEDS_REVIEW")
        summary = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["summary"]
        assert summary["recoverability"] == "unknown"


# ---------------------------------------------------------------------------
# 7. Confidence fields
# ---------------------------------------------------------------------------

class TestDebugConfidenceFields:

    def test_run_level_confidence_present(self, client, db, api_auth):
        run = _make_run(
            db,
            overall_confidence_score=0.82,
            overall_confidence_label="high",
        )
        run_section = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["run"]
        assert run_section["overall_confidence_score"] == pytest.approx(0.82)
        assert run_section["overall_confidence_label"] == "high"

    def test_run_level_confidence_null_when_absent(self, client, db, api_auth):
        run = _make_run(db)
        run_section = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["run"]
        assert run_section["overall_confidence_score"] is None
        assert run_section["overall_confidence_label"] is None

    def test_step_level_confidence_present(self, client, db, api_auth):
        run = _make_run(db)
        _make_step(
            db, run=run,
            confidence_score=0.65,
            confidence_label="medium",
            confidence_reason="fallback rule applied",
        )

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert steps[0]["confidence_score"] == pytest.approx(0.65)
        assert steps[0]["confidence_label"] == "medium"
        assert steps[0]["confidence_reason"] == "fallback rule applied"

    def test_step_level_confidence_null_when_absent(self, client, db, api_auth):
        run = _make_run(db)
        _make_step(db, run=run)

        steps = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()["steps"]
        assert steps[0]["confidence_score"] is None
        assert steps[0]["confidence_label"] is None
        assert steps[0]["confidence_reason"] is None


# ---------------------------------------------------------------------------
# 8. Anomalies in debug payload
# ---------------------------------------------------------------------------

class TestDebugAnomalies:

    def test_anomalies_key_present_and_is_list(self, client, db, api_auth):
        """anomalies key is always present; empty list when no anomalies fire."""
        run = _make_run(db, status="COMPLETED", overall_confidence_score=0.9,
                        overall_confidence_label="high")
        step = _make_step(db, run=run, status="COMPLETED")
        step.output_snapshot = {"price": 100.0}
        db.commit()

        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        assert "anomalies" in body
        assert isinstance(body["anomalies"], list)

    def test_anomaly_count_in_summary_matches_anomalies_list(self, client, db, api_auth):
        """summary.anomaly_count must equal len(anomalies)."""
        run = _make_run(db)
        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        assert body["summary"]["anomaly_count"] == len(body["anomalies"])

    def test_failed_high_confidence_anomaly_surfaces_in_debug(self, client, db, api_auth):
        """FAILED run with confidence >= 0.60 must produce a FAILED_HIGH_CONFIDENCE anomaly."""
        run = _make_run(
            db,
            status="FAILED",
            overall_confidence_score=0.85,
            overall_confidence_label="high",
            error_category="permanent",
        )
        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        anomaly_types = [a["anomaly_type"] for a in body["anomalies"]]
        assert "FAILED_HIGH_CONFIDENCE" in anomaly_types
        assert body["summary"]["anomaly_count"] == len(body["anomalies"])

    def test_missing_step_output_anomaly_surfaces_in_debug(self, client, db, api_auth):
        """COMPLETED step with no output_snapshot must produce a MISSING_STEP_OUTPUT anomaly."""
        run = _make_run(db, status="COMPLETED", overall_confidence_score=0.7,
                        overall_confidence_label="high")
        _make_step(db, run=run, status="COMPLETED")  # output_snapshot defaults to None

        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        anomaly_types = [a["anomaly_type"] for a in body["anomalies"]]
        assert "MISSING_STEP_OUTPUT" in anomaly_types

    def test_anomaly_items_have_required_fields(self, client, db, api_auth):
        """Each anomaly dict must contain the standard envelope fields."""
        run = _make_run(
            db,
            status="FAILED",
            overall_confidence_score=0.75,
            overall_confidence_label="high",
            error_category="transient",
        )
        body = client.get(
            f"/api/pipeline-runs/{run.id}/debug", headers=api_auth
        ).json()
        # At minimum the FAILED_HIGH_CONFIDENCE detector should fire.
        assert len(body["anomalies"]) >= 1
        for item in body["anomalies"]:
            assert "anomaly_type" in item
            assert "severity" in item
            assert "description" in item
            assert "context" in item

    def test_anomalies_scoped_to_run_not_other_runs(self, client, db, api_auth):
        """Anomalies for a different run must not bleed into this run's debug payload."""
        # Run A: clean — COMPLETED with confidence and output
        run_a = _make_run(db, status="COMPLETED", overall_confidence_score=0.8,
                          overall_confidence_label="high")
        step_a = _make_step(db, run=run_a, status="COMPLETED")
        step_a.output_snapshot = {"price": 500.0}
        db.commit()

        # Run B: FAILED with high confidence → fires FAILED_HIGH_CONFIDENCE
        _make_run(db, status="FAILED", overall_confidence_score=0.85,
                  overall_confidence_label="high", error_category="permanent")

        body = client.get(
            f"/api/pipeline-runs/{run_a.id}/debug", headers=api_auth
        ).json()
        # FAILED_HIGH_CONFIDENCE must not appear for run_a
        anomaly_types = [a["anomaly_type"] for a in body["anomalies"]]
        assert "FAILED_HIGH_CONFIDENCE" not in anomaly_types
