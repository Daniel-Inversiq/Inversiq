"""
app/routers/proposed_change_audit.py

GET /api/proposed-change-audit?change_id=...&tenant_id=...  — fetch audit history (oldest first)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.proposed_change_audit_event import ProposedChangeAuditEvent

router = APIRouter(prefix="/api/proposed-change-audit", tags=["proposed-change-audit"])


def _event_to_dict(event: ProposedChangeAuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "change_id": event.change_id,
        "scope_type": event.scope_type,
        "scope_id": event.scope_id,
        "event_type": event.event_type,
        "previous_status": event.previous_status,
        "new_status": event.new_status,
        "previous_note": event.previous_note,
        "new_note": event.new_note,
        "metadata_json": event.metadata_json,
        "actor": event.actor,
        "created_at": event.created_at,
    }


@router.get("")
def get_proposed_change_audit(
    change_id: str = Query(..., description="Stable change ID"),
    tenant_id: str = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Return the full audit history for a proposed change, oldest first.
    """
    events = (
        db.query(ProposedChangeAuditEvent)
        .filter(
            ProposedChangeAuditEvent.tenant_id == tenant_id,
            ProposedChangeAuditEvent.change_id == change_id,
        )
        .order_by(ProposedChangeAuditEvent.created_at.asc(), ProposedChangeAuditEvent.id.asc())
        .all()
    )
    return [_event_to_dict(e) for e in events]
