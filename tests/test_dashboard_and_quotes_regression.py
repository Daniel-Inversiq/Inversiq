from __future__ import annotations

import uuid

from app.models.lead import Lead
from app.services.dashboard_service import get_dashboard_summary
from app.verticals.construction.router_app import _compatible_vertical_ids_for_workflow


def _tid(prefix: str = "dash") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _make_lead(db, *, tenant_id: str, status: str, vertical: str | None = None) -> Lead:
    lead = Lead(
        tenant_id=tenant_id,
        name=f"Customer {status}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        status=status,
        vertical=vertical,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_dashboard_summary_counts_offer_and_review_flow_statuses_as_pending(db):
    tenant_id = _tid("summary")
    # These statuses should remain visible as "open" in dashboard summary KPIs/charts.
    _make_lead(db, tenant_id=tenant_id, status="NEW")
    _make_lead(db, tenant_id=tenant_id, status="RUNNING")
    _make_lead(db, tenant_id=tenant_id, status="NEEDS_REVIEW")

    summary = get_dashboard_summary(db=db, tenant_id=tenant_id)

    assert summary["kpis"]["pending_count"] == 3
    status_map = {row["label"]: row["value"] for row in summary["status_distribution"]}
    assert status_map["pending"] == 3


def test_painting_workflow_accepts_legacy_vertical_ids():
    compatible = _compatible_vertical_ids_for_workflow("construction")
    assert "paintly" in compatible
    assert "construction" in compatible
    assert "painters_nl" in compatible
