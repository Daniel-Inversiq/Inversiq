from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.verticals.registry import VERTICALS, VerticalNotFoundError, get_vertical

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


class TenantSectorPatchIn(BaseModel):
    sector: str


def _tenant_payload(tenant: Tenant) -> dict:
    vertical = tenant.get_vertical()
    engine_pipeline = (
        vertical.get_engine_pipeline()
        if hasattr(vertical, "get_engine_pipeline")
        else vertical.get_workflows()
        if hasattr(vertical, "get_workflows")
        else []
    )
    ui_workflows = (
        vertical.get_ui_workflows()
        if hasattr(vertical, "get_ui_workflows")
        else []
    )
    workflows = (
        vertical.get_workflows()
        if hasattr(vertical, "get_workflows")
        else []
    )
    features = (
        vertical.get_features()
        if hasattr(vertical, "get_features")
        else {}
    )
    dashboard = (
        vertical.get_dashboard_config()
        if hasattr(vertical, "get_dashboard_config")
        else {}
    )

    payload = {
        "id": tenant.id,
        "sector": tenant.sector,
        "vertical": {
            "key": getattr(vertical, "key", getattr(vertical, "vertical_id", "")),
            "label": getattr(vertical, "label", ""),
            # Backward-compatible field name for existing clients.
            "workflows": workflows,
            "ui_workflows": ui_workflows,
            "engine_pipeline": engine_pipeline,
            "features": features,
            "dashboard": dashboard,
        },
    }
    if hasattr(tenant, "onboarding_completed"):
        payload["onboarding_completed"] = bool(getattr(tenant, "onboarding_completed"))
    return payload


@router.get("/me")
def tenant_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tenant = db.query(Tenant).filter(Tenant.id == str(user.tenant_id)).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return _tenant_payload(tenant)


@router.patch("/sector")
def patch_tenant_sector(
    body: TenantSectorPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    normalized_sector = body.sector.strip().lower()
    if normalized_sector not in VERTICALS:
        raise HTTPException(status_code=400, detail=f"Invalid sector: {body.sector}")

    try:
        get_vertical(normalized_sector)
    except VerticalNotFoundError:
        raise HTTPException(status_code=400, detail=f"Invalid sector: {body.sector}")

    tenant = db.query(Tenant).filter(Tenant.id == str(user.tenant_id)).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.sector = normalized_sector
    if hasattr(tenant, "onboarding_completed"):
        setattr(tenant, "onboarding_completed", True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return _tenant_payload(tenant)
