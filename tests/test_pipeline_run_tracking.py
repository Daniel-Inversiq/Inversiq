"""
tests/test_pipeline_run_tracking.py

Tests for persistent pipeline execution tracking (PipelineRun + PipelineStepRun).

Scope: run_pipeline() with a real SQLite session (from conftest) and stub
step functions.  No mocks — stubs are registered directly in a fresh
StepRegistry per test.

Important behavioral notes about the current implementation
(tested accurately below, not idealized):

- With on_fail=CONTINUE: if all subsequent steps succeed, state.status is
  overwritten to "SUCCEEDED" at the end of the loop, so pipeline_run.status
  becomes "COMPLETED".  failure_step is still recorded on the run.
- With on_needs_review=CONTINUE: same semantics.
- error_type / error_message are only written for FAILED step runs,
  not for NEEDS_REVIEW.
"""
from __future__ import annotations

import uuid

import pytest

from inversiq.engine.config import EngineConfig, StepConfig
from inversiq.engine.context import EngineContext, StepResult
from inversiq.engine.registry import StepRegistry
from inversiq.engine.runner import run_pipeline
from app.models.pipeline_run import PipelineRun, PipelineStepRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(
    *,
    tenant_id: str | None = None,
    vertical_id: str = "test_v",
    lead_id: str | None = None,
) -> EngineContext:
    return EngineContext(
        tenant_id=tenant_id or f"t-{uuid.uuid4().hex[:8]}",
        vertical_id=vertical_id,
        lead_id=lead_id or uuid.uuid4().hex,
        trace_id=uuid.uuid4().hex,
    )


def _cfg(steps: list[StepConfig], version: str = "1.0") -> EngineConfig:
    return EngineConfig(
        vertical_id="test_v",
        rules_path="",
        template_path="",
        steps=steps,
        version=version,
    )


def _step(
    id: str,
    use: str,
    *,
    on_fail: str = "STOP",
    on_needs_review: str = "STOP",
) -> StepConfig:
    return StepConfig(
        id=id, use=use, with_={}, on_fail=on_fail, on_needs_review=on_needs_review
    )


def _registry(*pairs: tuple) -> StepRegistry:
    reg = StepRegistry()
    for key, fn in pairs:
        reg.register(key, fn)
    return reg


def _ok_fn(data: dict | None = None):
    """Step function that always returns OK."""
    def _fn(state, cfg, assets):
        return StepResult(status="OK", data=data or {})
    return _fn


def _fail_fn(error: str = "ValueError: something went wrong"):
    """Step function that returns FAILED."""
    def _fn(state, cfg, assets):
        return StepResult(status="FAILED", error=error)
    return _fn


def _review_fn():
    """Step function that returns NEEDS_REVIEW."""
    def _fn(state, cfg, assets):
        return StepResult(status="NEEDS_REVIEW")
    return _fn


def _explode_fn(exc_msg: str = "Boom"):
    """Step function that raises an unhandled exception."""
    def _fn(state, cfg, assets):
        raise RuntimeError(exc_msg)
    return _fn


def _get_run(db, trace_id: str) -> PipelineRun:
    return db.query(PipelineRun).filter_by(trace_id=trace_id).one()


def _get_steps(db, pipeline_run_id: int) -> list[PipelineStepRun]:
    return (
        db.query(PipelineStepRun)
        .filter_by(pipeline_run_id=pipeline_run_id)
        .order_by(PipelineStepRun.step_order)
        .all()
    )


# ---------------------------------------------------------------------------
# 1. Successful pipeline execution
# ---------------------------------------------------------------------------

class TestSuccessfulRun:

    def test_pipeline_run_is_created(self, db):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.id is not None

    def test_status_is_completed(self, db):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok"), _step("s2", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.status == "COMPLETED"

    def test_identifiers_are_persisted(self, db):
        ctx = _ctx(tenant_id="ten-abc", vertical_id="paint", lead_id="lead-xyz")
        config = _cfg([_step("s1", "ok")], version="2.1")
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.tenant_id == "ten-abc"
        assert run.vertical_id == "paint"
        assert run.lead_id == "lead-xyz"
        assert run.trace_id == ctx.trace_id
        assert run.engine_version == "2.1"

    def test_step_runs_created_for_each_step(self, db):
        ctx = _ctx()
        config = _cfg([_step("a", "ok"), _step("b", "ok"), _step("c", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = _get_steps(db, run.id)
        assert len(steps) == 3
        assert [s.step_name for s in steps] == ["a", "b", "c"]

    def test_step_order_is_persisted(self, db):
        ctx = _ctx()
        config = _cfg([_step("alpha", "ok"), _step("beta", "ok"), _step("gamma", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = _get_steps(db, run.id)
        assert [s.step_order for s in steps] == [0, 1, 2]

    def test_all_step_run_statuses_are_ok(self, db):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok"), _step("s2", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = _get_steps(db, run.id)
        assert all(s.status == "OK" for s in steps)

    def test_timestamps_and_duration_are_set(self, db):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok")])
        reg = _registry(("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.completed_at >= run.started_at

        step = _get_steps(db, run.id)[0]
        assert step.started_at is not None
        assert step.completed_at is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_runner_returns_succeeded_state(self, db):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok")])
        reg = _registry(("ok", _ok_fn({"key": "value"})))

        state = run_pipeline(ctx, config, reg, assets={}, db=db)

        assert state.status == "SUCCEEDED"
        assert state.data["steps"]["s1"] == {"key": "value"}


# ---------------------------------------------------------------------------
# 2. Failed step (on_fail=STOP, the default)
# ---------------------------------------------------------------------------

class TestFailedStep:

    def test_failing_step_run_status_is_failed(self, db):
        ctx = _ctx()
        config = _cfg([_step("bad", "fail")])
        reg = _registry(("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        step = _get_steps(db, run.id)[0]
        assert step.status == "FAILED"

    def test_error_type_and_message_are_persisted(self, db):
        ctx = _ctx()
        config = _cfg([_step("bad", "fail")])
        reg = _registry(("fail", _fail_fn("ValueError: bad input")))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        step = _get_steps(db, run.id)[0]
        assert step.error_type == "ValueError"
        assert step.error_message == "bad input"

    def test_pipeline_run_status_is_failed(self, db):
        ctx = _ctx()
        config = _cfg([_step("bad", "fail")])
        reg = _registry(("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.status == "FAILED"

    def test_failure_step_is_recorded_on_pipeline_run(self, db):
        ctx = _ctx()
        config = _cfg([_step("good", "ok"), _step("bad", "fail")])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.failure_step == "bad"

    def test_steps_after_failing_step_are_not_persisted(self, db):
        """With on_fail=STOP, the runner exits early — step3 never runs."""
        ctx = _ctx()
        config = _cfg([
            _step("step1", "ok"),
            _step("step2", "fail"),
            _step("step3", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        names = [s.step_name for s in _get_steps(db, run.id)]
        assert "step1" in names
        assert "step2" in names
        assert "step3" not in names

    def test_unhandled_exception_produces_failed_step_run(self, db):
        """An exception raised inside a step is caught, wrapped as FAILED."""
        ctx = _ctx()
        config = _cfg([_step("boom", "explode")])
        reg = _registry(("explode", _explode_fn("Kaboom")))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        step = _get_steps(db, run.id)[0]
        assert step.status == "FAILED"
        assert step.error_type == "RuntimeError"
        assert "Kaboom" in step.error_message
        assert run.status == "FAILED"
        assert run.failure_step == "boom"

    def test_runner_returns_failed_state(self, db):
        ctx = _ctx()
        config = _cfg([_step("bad", "fail")])
        reg = _registry(("fail", _fail_fn()))

        state = run_pipeline(ctx, config, reg, assets={}, db=db)

        assert state.status == "FAILED"
        assert state.failure_step == "bad"


# ---------------------------------------------------------------------------
# 3. NEEDS_REVIEW flow (on_needs_review=STOP, the default)
# ---------------------------------------------------------------------------

class TestNeedsReviewFlow:

    def test_step_run_status_is_needs_review(self, db):
        ctx = _ctx()
        config = _cfg([_step("review", "rev")])
        reg = _registry(("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        step = _get_steps(db, run.id)[0]
        assert step.status == "NEEDS_REVIEW"

    def test_pipeline_run_status_is_needs_review(self, db):
        ctx = _ctx()
        config = _cfg([_step("review", "rev")])
        reg = _registry(("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.status == "NEEDS_REVIEW"

    def test_failure_step_recorded_on_pipeline_run(self, db):
        ctx = _ctx()
        config = _cfg([_step("good", "ok"), _step("review", "rev")])
        reg = _registry(("ok", _ok_fn()), ("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.failure_step == "review"

    def test_steps_after_review_stop_are_not_persisted(self, db):
        ctx = _ctx()
        config = _cfg([_step("review", "rev"), _step("after", "ok")])
        reg = _registry(("rev", _review_fn()), ("ok", _ok_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        names = [s.step_name for s in _get_steps(db, run.id)]
        assert "after" not in names

    def test_runner_state_and_db_are_consistent(self, db):
        ctx = _ctx()
        config = _cfg([_step("review", "rev")])
        reg = _registry(("rev", _review_fn()))

        state = run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert state.status == "NEEDS_REVIEW"
        assert run.status == "NEEDS_REVIEW"
        assert run.failure_step == state.failure_step


# ---------------------------------------------------------------------------
# 4. Continue-on-failure
#
# Behavioral note: with on_fail=CONTINUE, state.status is set to "FAILED"
# at the failing step but is then overwritten to "SUCCEEDED" at the end of
# the loop if all subsequent steps pass.  The pipeline_run therefore ends
# with status="COMPLETED", but failure_step is still recorded.
# ---------------------------------------------------------------------------

class TestContinueOnFailure:

    def test_all_steps_are_persisted(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("s1", "ok"),
            _step("s2", "fail", on_fail="CONTINUE"),
            _step("s3", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        names = [s.step_name for s in _get_steps(db, run.id)]
        assert names == ["s1", "s2", "s3"]

    def test_failing_step_run_is_marked_failed(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("fail_step", "fail", on_fail="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn("IOError: disk full")))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = {s.step_name: s for s in _get_steps(db, run.id)}
        assert steps["fail_step"].status == "FAILED"
        assert steps["fail_step"].error_type == "IOError"

    def test_subsequent_step_run_is_marked_ok(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("fail_step", "fail", on_fail="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = {s.step_name: s for s in _get_steps(db, run.id)}
        assert steps["ok_step"].status == "OK"

    def test_pipeline_final_status_is_completed_when_rest_succeeds(self, db):
        """
        Current engine behavior: state.status is overwritten to SUCCEEDED at
        the end of the loop even if an earlier step failed with CONTINUE.
        """
        ctx = _ctx()
        config = _cfg([
            _step("fail_step", "fail", on_fail="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.status == "COMPLETED"

    def test_failure_step_still_recorded_even_when_completed(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("fail_step", "fail", on_fail="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.failure_step == "fail_step"

    def test_timestamps_set_for_all_steps(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("fail_step", "fail", on_fail="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("fail", _fail_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        for step in _get_steps(db, run.id):
            assert step.started_at is not None, f"{step.step_name} missing started_at"
            assert step.completed_at is not None, f"{step.step_name} missing completed_at"
            assert step.duration_ms is not None, f"{step.step_name} missing duration_ms"


# ---------------------------------------------------------------------------
# 5. Continue-on-needs-review
#
# Same semantics as continue-on-failure: pipeline ends COMPLETED when all
# subsequent steps succeed, but failure_step is still recorded.
# ---------------------------------------------------------------------------

class TestContinueOnNeedsReview:

    def test_all_steps_are_persisted(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("review_step", "rev", on_needs_review="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        names = [s.step_name for s in _get_steps(db, run.id)]
        assert names == ["review_step", "ok_step"]

    def test_review_step_run_is_marked_needs_review(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("review_step", "rev", on_needs_review="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        steps = {s.step_name: s for s in _get_steps(db, run.id)}
        assert steps["review_step"].status == "NEEDS_REVIEW"

    def test_pipeline_final_status_is_completed_when_rest_succeeds(self, db):
        """Same as continue-on-failure: SUCCEEDED state overwrites NEEDS_REVIEW."""
        ctx = _ctx()
        config = _cfg([
            _step("review_step", "rev", on_needs_review="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.status == "COMPLETED"

    def test_failure_step_still_recorded(self, db):
        ctx = _ctx()
        config = _cfg([
            _step("review_step", "rev", on_needs_review="CONTINUE"),
            _step("ok_step", "ok"),
        ])
        reg = _registry(("ok", _ok_fn()), ("rev", _review_fn()))

        run_pipeline(ctx, config, reg, assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        assert run.failure_step == "review_step"


# ---------------------------------------------------------------------------
# 6. No DB session — existing runner return behavior is unchanged
# ---------------------------------------------------------------------------

class TestNoDatabaseSession:
    """When db=None, run_pipeline must still return a correct PipelineState."""

    def test_success_without_db(self):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok")])
        reg = _registry(("ok", _ok_fn({"x": 1})))

        state = run_pipeline(ctx, config, reg, assets={}, db=None)

        assert state.status == "SUCCEEDED"
        assert state.data["steps"]["s1"] == {"x": 1}

    def test_failure_without_db(self):
        ctx = _ctx()
        config = _cfg([_step("bad", "fail")])
        reg = _registry(("fail", _fail_fn()))

        state = run_pipeline(ctx, config, reg, assets={}, db=None)

        assert state.status == "FAILED"
        assert state.failure_step == "bad"

    def test_needs_review_without_db(self):
        ctx = _ctx()
        config = _cfg([_step("rev", "rev")])
        reg = _registry(("rev", _review_fn()))

        state = run_pipeline(ctx, config, reg, assets={}, db=None)

        assert state.status == "NEEDS_REVIEW"
        assert state.failure_step == "rev"

    def test_logs_are_populated_without_db(self):
        ctx = _ctx()
        config = _cfg([_step("s1", "ok")])
        reg = _registry(("ok", _ok_fn()))

        state = run_pipeline(ctx, config, reg, assets={}, db=None)

        assert len(state.logs) > 0
        levels = {e["level"] for e in state.logs}
        assert "info" in levels
