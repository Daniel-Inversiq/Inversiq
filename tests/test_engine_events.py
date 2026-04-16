"""
tests/test_engine_events.py

Tests for EngineEvent emission from run_pipeline() and the /api/engine-events endpoint.

Scope:
  - All 8 event types are emitted on the correct pipeline paths:
      pipeline.started / pipeline.completed / pipeline.failed / pipeline.needs_review
      pipeline.step.started / pipeline.step.completed /
      pipeline.step.failed / pipeline.step.needs_review
  - Key correlation fields are set correctly on each event.
  - GET /api/engine-events filters (pipeline_run_id, lead_id, trace_id) work.
  - Endpoint returns 400 when no filter is supplied.

Design notes:
  - Every test gets a fresh EngineContext with a unique trace_id so queries
    cannot bleed across tests (the SQLite file is shared and not rolled back).
  - Events are committed by run_pipeline() via _finish_pipeline_run → db.commit().
  - The `client` fixture and the `db` fixture both target the same SQLite file;
    committed rows are visible to both.
"""
from __future__ import annotations

import base64
import uuid
from typing import List

import pytest

from inversiq.engine.config import EngineConfig, StepConfig
from inversiq.engine.context import EngineContext, StepResult
from inversiq.engine.registry import StepRegistry
from inversiq.engine.runner import run_pipeline
from app.models.engine_event import EngineEvent
from app.models.pipeline_run import PipelineRun


# ---------------------------------------------------------------------------
# Shared helpers  (mirror the style of test_pipeline_run_tracking.py)
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
    def _fn(state, cfg, assets):
        return StepResult(status="OK", data=data or {})
    return _fn


def _fail_fn(error: str = "ValueError: something went wrong"):
    def _fn(state, cfg, assets):
        return StepResult(status="FAILED", error=error)
    return _fn


def _review_fn():
    def _fn(state, cfg, assets):
        return StepResult(status="NEEDS_REVIEW")
    return _fn


def _explode_fn(exc_msg: str = "Boom"):
    def _fn(state, cfg, assets):
        raise RuntimeError(exc_msg)
    return _fn


def _get_events(db, *, trace_id: str) -> List[EngineEvent]:
    """Return all EngineEvents for a trace, ordered by occurred_at."""
    return (
        db.query(EngineEvent)
        .filter_by(trace_id=trace_id)
        .order_by(EngineEvent.occurred_at)
        .all()
    )


def _get_run(db, trace_id: str) -> PipelineRun:
    return db.query(PipelineRun).filter_by(trace_id=trace_id).one()


@pytest.fixture
def api_auth():
    """Basic-Auth header for /api/* endpoints.

    SALES_BASIC_AUTH_USER / SALES_BASIC_AUTH_PASS default to "" in tests, so
    we send an Authorization: Basic header with empty user:password (":").
    """
    encoded = base64.b64encode(b":").decode()
    return {"Authorization": f"Basic {encoded}"}


# ---------------------------------------------------------------------------
# 1. Successful pipeline — event types emitted
# ---------------------------------------------------------------------------

class TestSuccessfulPipelineEvents:

    def test_pipeline_started_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.started" in types

    def test_pipeline_completed_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.completed" in types

    def test_step_started_emitted_per_step(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx,
            _cfg([_step("s1", "ok"), _step("s2", "ok")]),
            _registry(("ok", _ok_fn())),
            assets={},
            db=db,
        )

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert types.count("pipeline.step.started") == 2

    def test_step_completed_emitted_per_step(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx,
            _cfg([_step("s1", "ok"), _step("s2", "ok")]),
            _registry(("ok", _ok_fn())),
            assets={},
            db=db,
        )

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert types.count("pipeline.step.completed") == 2

    def test_successful_event_order(self, db):
        """started is first, completed is last."""
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert types[0] == "pipeline.started"
        assert types[-1] == "pipeline.completed"


# ---------------------------------------------------------------------------
# 2. Failed pipeline — event types emitted
# ---------------------------------------------------------------------------

class TestFailedPipelineEvents:

    def test_step_failed_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "fail")]), _registry(("fail", _fail_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.step.failed" in types

    def test_pipeline_failed_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "fail")]), _registry(("fail", _fail_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.failed" in types

    def test_unhandled_exception_emits_step_failed_and_pipeline_failed(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "boom")]), _registry(("boom", _explode_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.step.failed" in types
        assert "pipeline.failed" in types

    def test_on_fail_continue_suppresses_pipeline_failed(self, db):
        """on_fail=CONTINUE: step.failed is emitted but pipeline.failed is not."""
        ctx = _ctx()
        run_pipeline(
            ctx,
            _cfg([_step("s1", "fail", on_fail="CONTINUE"), _step("s2", "ok")]),
            _registry(("fail", _fail_fn()), ("ok", _ok_fn())),
            assets={},
            db=db,
        )

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.step.failed" in types
        assert "pipeline.failed" not in types


# ---------------------------------------------------------------------------
# 3. Needs-review pipeline — event types emitted
# ---------------------------------------------------------------------------

class TestNeedsReviewPipelineEvents:

    def test_step_needs_review_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "rev")]), _registry(("rev", _review_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.step.needs_review" in types

    def test_pipeline_needs_review_emitted(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "rev")]), _registry(("rev", _review_fn())), assets={}, db=db)

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.needs_review" in types

    def test_on_needs_review_continue_suppresses_pipeline_needs_review(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx,
            _cfg([_step("s1", "rev", on_needs_review="CONTINUE"), _step("s2", "ok")]),
            _registry(("rev", _review_fn()), ("ok", _ok_fn())),
            assets={},
            db=db,
        )

        types = [e.event_type for e in _get_events(db, trace_id=ctx.trace_id)]
        assert "pipeline.step.needs_review" in types
        assert "pipeline.needs_review" not in types


# ---------------------------------------------------------------------------
# 4. Correlation fields
# ---------------------------------------------------------------------------

class TestEventCorrelationFields:

    def test_pipeline_started_tenant_lead_trace(self, db):
        ctx = _ctx(tenant_id="ten-abc", vertical_id="paint", lead_id="lead-xyz")
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        ev = next(e for e in _get_events(db, trace_id=ctx.trace_id) if e.event_type == "pipeline.started")
        assert ev.tenant_id == "ten-abc"
        assert ev.lead_id == "lead-xyz"
        assert ev.trace_id == ctx.trace_id
        assert ev.vertical_id == "paint"

    def test_pipeline_started_status_running(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        ev = next(e for e in _get_events(db, trace_id=ctx.trace_id) if e.event_type == "pipeline.started")
        assert ev.status == "RUNNING"

    def test_pipeline_started_has_pipeline_run_id(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        run = _get_run(db, ctx.trace_id)
        ev = next(e for e in _get_events(db, trace_id=ctx.trace_id) if e.event_type == "pipeline.started")
        assert ev.pipeline_run_id == run.id

    def test_all_events_share_pipeline_run_id(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx, _cfg([_step("s1", "ok"), _step("s2", "ok")]),
            _registry(("ok", _ok_fn())), assets={}, db=db,
        )

        run = _get_run(db, ctx.trace_id)
        events = _get_events(db, trace_id=ctx.trace_id)
        assert len(events) > 0
        assert all(e.pipeline_run_id == run.id for e in events)

    def test_step_started_step_name_and_use(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx, _cfg([_step("my_step", "my.use")]),
            _registry(("my.use", _ok_fn())), assets={}, db=db,
        )

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.step.started"
        )
        assert ev.step_name == "my_step"
        assert ev.step_use == "my.use"
        assert ev.status == "RUNNING"

    def test_step_completed_status_and_duration_payload(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.step.completed"
        )
        assert ev.status == "COMPLETED"
        assert ev.payload is not None
        assert "duration_ms" in ev.payload

    def test_step_failed_error_in_payload(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx, _cfg([_step("s1", "fail")]),
            _registry(("fail", _fail_fn("ValueError: bad input"))), assets={}, db=db,
        )

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.step.failed"
        )
        assert ev.status == "FAILED"
        assert ev.payload is not None
        assert "duration_ms" in ev.payload
        assert ev.payload.get("error") == "ValueError: bad input"

    def test_step_failed_error_category_set_for_exception(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "boom")]), _registry(("boom", _explode_fn())), assets={}, db=db)

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.step.failed"
        )
        assert ev.error_category is not None

    def test_pipeline_failed_failure_step_in_payload(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx, _cfg([_step("failing_step", "fail")]),
            _registry(("fail", _fail_fn())), assets={}, db=db,
        )

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.failed"
        )
        assert ev.status == "FAILED"
        assert ev.payload == {"failure_step": "failing_step"}

    def test_pipeline_failed_error_category_propagated(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "boom")]), _registry(("boom", _explode_fn())), assets={}, db=db)

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.failed"
        )
        assert ev.error_category is not None

    def test_pipeline_needs_review_payload(self, db):
        ctx = _ctx()
        run_pipeline(
            ctx, _cfg([_step("review_step", "rev")]),
            _registry(("rev", _review_fn())), assets={}, db=db,
        )

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.needs_review"
        )
        assert ev.status == "NEEDS_REVIEW"
        assert ev.payload == {"failure_step": "review_step"}

    def test_step_needs_review_status(self, db):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "rev")]), _registry(("rev", _review_fn())), assets={}, db=db)

        ev = next(
            e for e in _get_events(db, trace_id=ctx.trace_id)
            if e.event_type == "pipeline.step.needs_review"
        )
        assert ev.status == "NEEDS_REVIEW"

    def test_no_events_without_db_session(self, db):
        ctx = _ctx()
        # run_pipeline must not raise; events must not appear in the DB
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=None)

        events = _get_events(db, trace_id=ctx.trace_id)
        assert events == []


# ---------------------------------------------------------------------------
# 5. GET /api/engine-events endpoint
# ---------------------------------------------------------------------------

class TestEngineEventsEndpoint:

    def test_no_filter_returns_400(self, client, api_auth):
        resp = client.get("/api/engine-events", headers=api_auth)
        assert resp.status_code == 400
        assert "filter" in resp.json()["detail"].lower()

    def test_filter_by_pipeline_run_id(self, client, db, api_auth):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)
        run = _get_run(db, ctx.trace_id)

        resp = client.get(f"/api/engine-events?pipeline_run_id={run.id}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0
        assert all(item["pipeline_run_id"] == run.id for item in body["items"])

    def test_filter_by_lead_id(self, client, db, api_auth):
        lead_id = f"lead-{uuid.uuid4().hex[:8]}"
        ctx = _ctx(lead_id=lead_id)
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        resp = client.get(f"/api/engine-events?lead_id={lead_id}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0
        assert all(item["lead_id"] == lead_id for item in body["items"])

    def test_filter_by_trace_id(self, client, db, api_auth):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        resp = client.get(f"/api/engine-events?trace_id={ctx.trace_id}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0
        assert all(item["trace_id"] == ctx.trace_id for item in body["items"])

    def test_trace_id_filter_isolates_run(self, client, db, api_auth):
        """Events from a different run must not appear under another trace_id."""
        ctx_a = _ctx()
        ctx_b = _ctx()
        run_pipeline(ctx_a, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)
        run_pipeline(ctx_b, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        resp = client.get(f"/api/engine-events?trace_id={ctx_a.trace_id}", headers=api_auth)
        assert resp.status_code == 200
        trace_ids = {item["trace_id"] for item in resp.json()["items"]}
        assert trace_ids == {ctx_a.trace_id}

    def test_response_contains_expected_keys(self, client, db, api_auth):
        ctx = _ctx()
        run_pipeline(ctx, _cfg([_step("s1", "ok")]), _registry(("ok", _ok_fn())), assets={}, db=db)

        resp = client.get(f"/api/engine-events?trace_id={ctx.trace_id}", headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert isinstance(body["items"], list)

        item = body["items"][0]
        expected_keys = {
            "id", "event_type", "occurred_at", "tenant_id", "lead_id",
            "vertical_id", "trace_id", "pipeline_run_id", "pipeline_step_run_id",
            "step_name", "step_use", "status", "error_category", "payload", "meta",
        }
        assert expected_keys.issubset(item.keys())

    def test_limit_caps_results(self, client, db, api_auth):
        # 3 steps → 8 events (started + 3×step.started + 3×step.completed + completed)
        ctx = _ctx()
        run_pipeline(
            ctx,
            _cfg([_step("s1", "ok"), _step("s2", "ok"), _step("s3", "ok")]),
            _registry(("ok", _ok_fn())),
            assets={},
            db=db,
        )

        resp = client.get(f"/api/engine-events?trace_id={ctx.trace_id}&limit=3", headers=api_auth)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 3
