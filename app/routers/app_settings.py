from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/settings/company")
def get_company_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == str(user.tenant_id)).first()
    pricing = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant is not None else {}
    price_per_m2 = pricing.get("price_per_m2")
    try:
        normalized_price = float(price_per_m2) if price_per_m2 is not None else None
    except (TypeError, ValueError):
        normalized_price = None

    return {
        "company_name": user.company_name or "",
        "support_email": user.email,
        "logo_url": user.logo_url,
        "price_per_m2": normalized_price,
    }
