"""
tests/test_painting_orchestration_baseline.py

Phase 0B safety baseline for the painting orchestration layer.

Scope:
  - adapter.compute_quote()    : status transitions + estimate persistence
  - publish_quote()            : idempotency early-exit guard

These tests characterize *existing behavior* so future extraction cannot
silently change how status transitions and data persistence work.

External dependencies mocked in all compute tests:
  - compute_quote_for_lead_v15  (engine: vision + pricing + HTML render + S3)
  - capture_ml_data             (ML training side-effect, never fails production)

The DB fixture (SQLite, from conftest) is used as-is — no DB mocking.
"""
from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from fastapi.responses import RedirectResponse

from app.models import Lead, LeadFile
from app.verticals.construction.adapter import ConstructionAdapter

# ---------------------------------------------------------------------------
# Patch targets (module-level constants so they stay in sync with imports)
#
# After Phase 1A extraction, compute_quote_for_lead_v15 and capture_ml_data
# are imported by quote_service, not adapter — patches must reflect that.
# ---------------------------------------------------------------------------

_ENGINE_PATCH = "app.verticals.construction.quote_service.compute_quote_for_lead_v15"
_ML_PATCH     = "app.verticals.construction.quote_service.capture_ml_data"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_ESTIMATE = {
    "meta": {},
    "line_items": [
        {
            "code": "walls",
            "label": "Wanden schilderen",
            "quantity": 50.0,
            "unit": "sqm",
            "unit_price": 23.4,
            "total": 1170.0,
            "category": "labor",
        }
    ],
    "subtotals": {"labor": "1170.00", "materials": "0.00"},
    "totals": {"pre_tax": "1170.00", "grand_total": "1170.00"},
    "total_eur": "1170.00",
    "currency": "EUR",
}


def _fake_engine(*, needs_review: bool = False) -> dict:
    """Minimal dict that adapter.compute_quote() accepts from the engine facade."""
    return {
        "estimate_json": _MINIMAL_ESTIMATE,
        "estimate_html_key": "uploads/test-estimate.html",
        "needs_review": needs_review,
        "engine_status": "NEEDS_REVIEW" if needs_review else "SUCCEEDED",
        "trace_id": "baseline-trace-001",
        "debug_pricing_raw": None,
    }


def _make_lead(
    db,
    *,
    status: str = "NEW",
    intake_payload: dict | None = None,
) -> Lead:
    """
    Insert a Lead + one LeadFile into the test DB.

    LeadFile is required because adapter.compute_quote() raises 400
    if the lead has no attached files.
    """
    lead = Lead(
        id=uuid4().hex,
        tenant_id=f"tenant-{uuid4().hex[:8]}",
        vertical="construction",
        name="Baseline Customer",
        email="baseline@example.com",
        status=status,
        intake_payload=json.dumps(intake_payload) if intake_payload else None,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    db.add(
        LeadFile(
            lead_id=lead.id,
            s3_key="uploads/baseline-photo.jpg",
            size_bytes=5000,
            content_type="image/jpeg",
        )
    )
    db.commit()
    return lead


# ---------------------------------------------------------------------------
# 1. adapter.compute_quote() — status transitions and estimate persistence
#
# This is the real orchestration seam: the function that calls the engine
# and writes estimate_json + estimate_html_key + status back to the DB.
# ---------------------------------------------------------------------------

_ADAPTER = ConstructionAdapter()


class TestAdapterComputeQuote:

    def test_success_path_sets_succeeded_and_persists_estimate(self, db):
        """
        Engine returns needs_review=False →
          lead.status must be SUCCEEDED
          lead.estimate_html_key must be written
          lead.estimate_json must be non-empty
          returned dict must echo the persisted values
        """
        lead = _make_lead(db)

        with patch(_ENGINE_PATCH, return_value=_fake_engine(needs_review=False)), \
             patch(_ML_PATCH):
            result = _ADAPTER.compute_quote(db, lead.id)

        db.refresh(lead)

        assert lead.status == "SUCCEEDED"
        assert lead.estimate_html_key == "uploads/test-estimate.html"
        assert lead.estimate_json is not None

        assert result["needs_review"] is False
        assert result["estimate_html_key"] == "uploads/test-estimate.html"

    def test_needs_review_path_sets_needs_review_status(self, db):
        """
        Engine returns needs_review=True →
          lead.status must be NEEDS_REVIEW
          estimate must still be persisted (review leads still carry an estimate)
        """
        lead = _make_lead(db)

        with patch(_ENGINE_PATCH, return_value=_fake_engine(needs_review=True)), \
             patch(_ML_PATCH):
            result = _ADAPTER.compute_quote(db, lead.id)

        db.refresh(lead)

        assert lead.status == "NEEDS_REVIEW"
        assert result["needs_review"] is True
        # Estimate data is written even for review leads
        assert lead.estimate_json is not None
        assert lead.estimate_html_key is not None

    def test_demo_force_review_flag_overrides_engine_decision(self, db):
        """
        intake_payload.demo_force_review = True must override needs_review=False.

        This pins the demo/test override mechanism: if a lead's intake payload
        explicitly requests forced review, the engine's own needs_review=False
        result must be ignored and lead.status must be NEEDS_REVIEW.
        """
        lead = _make_lead(db, intake_payload={"demo_force_review": True})

        with patch(_ENGINE_PATCH, return_value=_fake_engine(needs_review=False)), \
             patch(_ML_PATCH):
            result = _ADAPTER.compute_quote(db, lead.id)

        db.refresh(lead)

        # Engine said False, flag says True → override must win
        assert lead.status == "NEEDS_REVIEW"
        assert result["needs_review"] is True


# ---------------------------------------------------------------------------
# 2. publish_quote() — idempotency guard
#
# When a lead is already in a terminal state (SUCCEEDED / NEEDS_REVIEW),
# publish_quote() must short-circuit immediately and not re-invoke the engine.
# ---------------------------------------------------------------------------

class TestPublishQuoteIdempotency:

    def test_already_succeeded_redirects_without_calling_engine(self, db):
        """
        Lead status = SUCCEEDED → publish_quote() returns a redirect to the
        public estimate view immediately, without invoking compute_quote_for_lead_v15.

        This is the "don't bill the customer twice / don't reprocess" guard.
        """
        from app.routers.quotes import publish_quote

        lead = _make_lead(db, status="SUCCEEDED")
        lead.estimate_json = json.dumps(_MINIMAL_ESTIMATE)
        lead.estimate_html_key = "uploads/existing.html"
        db.add(lead)
        db.commit()

        with patch(_ENGINE_PATCH) as mock_engine:
            response = publish_quote(
                lead_id=str(lead.id),
                background=BackgroundTasks(),
                db=db,
                request=None,   # no HTTP context → public flow
                tenant_id=None,
            )

        # Engine must be untouched
        mock_engine.assert_not_called()

        # Must redirect to the public estimate URL (not the dashboard)
        assert isinstance(response, RedirectResponse)
        location = response.headers["location"]
        assert str(lead.id) in location
        assert location.startswith("/offerte/"), (
            f"Expected public /offerte/ redirect, got: {location!r}"
        )
