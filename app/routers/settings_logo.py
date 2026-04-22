from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.billing.dependencies import (
    require_entitlement,
    require_active_subscription_for_write,
)
from app.billing.entitlements import Action
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.services.storage import get_storage

router = APIRouter(tags=["settings"])

_ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg"}


class CompanyUpdate(BaseModel):
    company_name: str
    price_per_m2: float | None = None


@router.post("/settings/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_entitlement(Action.USE_BRANDING.value)),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    _ = tenant
    content_type = (file.content_type or "").strip().lower()
    if content_type not in _ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="unsupported_content_type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")

    ext = ".png" if content_type == "image/png" else ".jpg"
    safe_name = PurePath(file.filename or f"logo{ext}").name
    today = datetime.now(timezone.utc).date().isoformat()
    key = f"settings/logos/{today}/{uuid4().hex}_{safe_name}"

    storage = get_storage()
    try:
        storage.save_bytes(
            tenant_id=str(user.tenant_id),
            key=key,
            data=data,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"logo_upload_failed:{exc}")

    logo_url = storage.public_url(tenant_id=str(user.tenant_id), key=key)
    user.logo_url = logo_url
    db.add(user)
    db.commit()

    return {"logo_url": logo_url}


@router.post("/settings/company")
def update_company(
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_entitlement(Action.USE_BRANDING.value)),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    _ = tenant
    company_name = payload.company_name.strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name_required")

    if payload.price_per_m2 is not None and payload.price_per_m2 <= 0:
        raise HTTPException(status_code=400, detail="price_per_m2_invalid")

    user.company_name = company_name
    tenant_record = db.query(Tenant).filter(Tenant.id == str(user.tenant_id)).first()
    if tenant_record is not None:
        existing = dict(tenant_record.pricing_json or {})
        if payload.price_per_m2 is None:
            existing.pop("price_per_m2", None)
        else:
            existing["price_per_m2"] = float(payload.price_per_m2)
        tenant_record.pricing_json = existing
        db.add(tenant_record)

    db.add(user)
    db.commit()

    return {"success": True}
