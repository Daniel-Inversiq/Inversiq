"""
app/routers/proposed_change_apply_intents.py

Read-only API for ProposedChangeApplyIntent records.

Endpoints:
  GET /api/proposed-change-apply-intents
  GET /api/proposed-change-apply-intents/{change_id}

These endpoints expose the persisted apply intent objects that are created
when a proposal is moved to ready_for_apply. They capture the governance
snapshot and proposal context at the time the intent was created.

Read-only. No state mutations.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent

router = APIRouter(
    prefix="/api/proposed-change-apply-intents",
    tags=["proposed-change-apply-intents"],
)


def _to_dict(intent: ProposedChangeApplyIntent, *, include_snapshots: bool = True) -> dict[str, Any]:
    governance = None
    if intent.governance_snapshot:
        try:
            governance = json.loads(intent.governance_snapshot)
        except Exception:
            governance = {"raw": intent.governance_snapshot}

    result: dict[str, Any] = {
        "id": intent.id,
        "tenant_id": intent.tenant_id,
        "change_id": intent.change_id,
        "scope_type": intent.scope_type,
        "scope_id": intent.scope_id,
        "status": intent.status,
        "change_type": intent.change_type,
        "title": intent.title,
        "governance_snapshot": governance,
        "has_apply_plan": intent.apply_plan_snapshot is not None,
        "has_preflight": intent.preflight_snapshot is not None,
        "has_rollback": intent.rollback_snapshot is not None,
        "created_at": intent.created_at,
        "updated_at": intent.updated_at,
    }

    if include_snapshots:
        result["proposal_payload"] = (
            json.loads(intent.proposal_payload) if intent.proposal_payload else None
        )
        result["apply_plan_snapshot"] = (
            json.loads(intent.apply_plan_snapshot) if intent.apply_plan_snapshot else None
        )
        result["preflight_snapshot"] = (
            json.loads(intent.preflight_snapshot) if intent.preflight_snapshot else None
        )
        result["rollback_snapshot"] = (
            json.loads(intent.rollback_snapshot) if intent.rollback_snapshot else None
        )

    return result


@router.get("")
def list_apply_intents(
    tenant_id: str = Query(..., description="Filter by tenant"),
    status: Optional[str] = Query(None, description="Filter by status (ready_for_apply | cancelled)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List apply intent records for a tenant."""
    q = db.query(ProposedChangeApplyIntent).filter(
        ProposedChangeApplyIntent.tenant_id == tenant_id
    )
    if status is not None:
        q = q.filter(ProposedChangeApplyIntent.status == status)

    intents = q.order_by(ProposedChangeApplyIntent.created_at.desc()).all()

    return {
        "tenant_id": tenant_id,
        "total": len(intents),
        "items": [_to_dict(i, include_snapshots=False) for i in intents],
    }


@router.get("/{change_id:path}")
def get_apply_intent(
    change_id: str,
    tenant_id: str = Query(..., description="Tenant that owns this intent"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the apply intent for a specific proposal."""
    intent = (
        db.query(ProposedChangeApplyIntent)
        .filter(
            ProposedChangeApplyIntent.tenant_id == tenant_id,
            ProposedChangeApplyIntent.change_id == change_id,
        )
        .first()
    )
    if intent is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No apply intent found for change_id='{change_id}', "
                f"tenant_id='{tenant_id}'."
            ),
        )
    return _to_dict(intent, include_snapshots=True)
