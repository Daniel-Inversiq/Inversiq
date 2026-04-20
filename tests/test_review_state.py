"""
tests/test_review_state.py

Tests for GET /api/review-state and POST /api/review-state.

Scenarios covered
-----------------
Default state
  - GET for unknown pipeline_run_id returns status="pending", null timestamps

Create
  - POST creates a new record with the given status and note
  - Created record is retrievable via GET
  - All response fields are present

Update (upsert)
  - POST with same pipeline_run_id updates status and note in-place
  - tenant_id is preserved from the original create

Validation
  - POST with invalid status returns 422

Integration with review inbox
  - review_state field is present on each inbox item
  - review_state reflects the stored state (not always "pending")
  - items without a stored state default to "pending"
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest

from app.models.pipeline_run import PipelineRun
from app.models.run_review_state import RunReviewState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATE_URL = "/api/review-state"
INBOX_URL = "/api/review-inbox"


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
    status: str = "FAILED",
    error_category: Optional[str] = "permanent",
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=tenant_id,
        lead_id=_uid(),
        vertical_id="test_vertical",
        trace_id=_uid(),
        pipeline_name="test_pipeline",
        engine_version="1.0.0",
        status=status,
        error_category=error_category,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Default state — no record exists
# ---------------------------------------------------------------------------


class TestDefaultState:
    def test_unknown_run_returns_pending(self, client, api_auth):
        resp = client.get(STATE_URL, params={"pipeline_run_id": 999999999}, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["pipeline_run_id"] == 999999999

    def test_unknown_run_has_null_timestamps(self, client, api_auth):
        resp = client.get(STATE_URL, params={"pipeline_run_id": 999999998}, headers=api_auth)
        body = resp.json()
        assert body["created_at"] is None
        assert body["updated_at"] is None

    def test_unknown_run_has_null_note(self, client, api_auth):
        resp = client.get(STATE_URL, params={"pipeline_run_id": 999999997}, headers=api_auth)
        body = resp.json()
        assert body["note"] is None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_post_creates_record(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        payload = {
            "pipeline_run_id": run.id,
            "tenant_id": tid,
            "status": "acknowledged",
            "note": "Checked manually, looks fine.",
        }
        resp = client.post(STATE_URL, json=payload, headers=api_auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "acknowledged"
        assert body["note"] == "Checked manually, looks fine."
        assert body["pipeline_run_id"] == run.id
        assert body["tenant_id"] == tid

    def test_created_record_retrievable_via_get(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "resolved"},
            headers=api_auth,
        )
        resp = client.get(STATE_URL, params={"pipeline_run_id": run.id}, headers=api_auth)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_create_response_has_all_fields(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "pending"},
            headers=api_auth,
        )
        body = resp.json()
        required = {"pipeline_run_id", "tenant_id", "status", "note", "created_at", "updated_at"}
        assert required <= set(body.keys())

    def test_create_without_note(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "ignored"},
            headers=api_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["note"] is None

    def test_timestamps_populated_after_create(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "pending"},
            headers=api_auth,
        )
        body = resp.json()
        assert body["created_at"] is not None
        assert body["updated_at"] is not None


# ---------------------------------------------------------------------------
# Update (upsert)
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_second_post_updates_status(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "pending"},
            headers=api_auth,
        )
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "resolved"},
            headers=api_auth,
        )
        assert resp.json()["status"] == "resolved"

    def test_second_post_updates_note(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "pending", "note": "first"},
            headers=api_auth,
        )
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "resolved", "note": "second"},
            headers=api_auth,
        )
        assert resp.json()["note"] == "second"

    def test_upsert_does_not_create_duplicate_row(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        for _ in range(3):
            client.post(
                STATE_URL,
                json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "acknowledged"},
                headers=api_auth,
            )
        count = (
            db.query(RunReviewState)
            .filter(RunReviewState.pipeline_run_id == run.id)
            .count()
        )
        assert count == 1

    def test_get_after_update_reflects_new_status(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "pending"},
            headers=api_auth,
        )
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "ignored"},
            headers=api_auth,
        )
        resp = client.get(STATE_URL, params={"pipeline_run_id": run.id}, headers=api_auth)
        assert resp.json()["status"] == "ignored"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_invalid_status_returns_422(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        resp = client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "bogus"},
            headers=api_auth,
        )
        assert resp.status_code == 422

    def test_all_valid_statuses_accepted(self, client, db, api_auth):
        for status in ("pending", "acknowledged", "resolved", "ignored"):
            tid = _uid()
            run = _make_run(db, tenant_id=tid)
            resp = client.post(
                STATE_URL,
                json={"pipeline_run_id": run.id, "tenant_id": tid, "status": status},
                headers=api_auth,
            )
            assert resp.status_code == 200, f"Expected 200 for status={status}"


# ---------------------------------------------------------------------------
# Integration with review inbox
# ---------------------------------------------------------------------------


class TestReviewInboxIntegration:
    def test_review_state_field_present_on_inbox_item(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(INBOX_URL, params={"tenant_id": tid}, headers=api_auth)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert "review_state" in items[0]

    def test_inbox_item_defaults_to_pending_when_no_state(self, client, db, api_auth):
        tid = _uid()
        _make_run(db, tenant_id=tid)
        resp = client.get(INBOX_URL, params={"tenant_id": tid}, headers=api_auth)
        item = resp.json()["items"][0]
        assert item["review_state"] == "pending"

    def test_inbox_item_reflects_stored_review_state(self, client, db, api_auth):
        tid = _uid()
        run = _make_run(db, tenant_id=tid)
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run.id, "tenant_id": tid, "status": "resolved"},
            headers=api_auth,
        )
        resp = client.get(INBOX_URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        matching = [i for i in items if i["pipeline_run_id"] == run.id]
        assert len(matching) == 1
        assert matching[0]["review_state"] == "resolved"

    def test_inbox_multiple_items_each_have_review_state(self, client, db, api_auth):
        tid = _uid()
        run1 = _make_run(db, tenant_id=tid)
        run2 = _make_run(db, tenant_id=tid, error_category="transient")
        client.post(
            STATE_URL,
            json={"pipeline_run_id": run1.id, "tenant_id": tid, "status": "acknowledged"},
            headers=api_auth,
        )
        resp = client.get(INBOX_URL, params={"tenant_id": tid}, headers=api_auth)
        items = resp.json()["items"]
        assert all("review_state" in i for i in items)
        states_by_id = {i["pipeline_run_id"]: i["review_state"] for i in items}
        assert states_by_id[run1.id] == "acknowledged"
        assert states_by_id[run2.id] == "pending"
