# app/routers/onboarding.py
# TODO: When POST /onboarding/tenant also creates an owner User (same contract as /auth/register),
# schedule `send_welcome_email_task` after commit, mirroring the auth register flow. Today this
# endpoint only creates a Tenant row — welcome mail is triggered from /auth/register.
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.deps import require_user_html
from app.core.settings import settings
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.onboarding import (
    TenantOnboardingCreate,
    TenantOnboardingResponse,
)
from app.i18n.service import setup_jinja_i18n
from app.services.tenant_onboarding import create_tenant_with_pricing

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="app/verticals/paintly/templates")
setup_jinja_i18n(templates)


def _build_intake_urls_for_user(db: Session, current_user: User) -> dict[str, str]:
    """
    Build onboarding intake links from the logged-in user's tenant.
    Preferred URL uses tenant.slug: /intake/{tenant_slug}
    Fallback URL uses tenant_id: /t/{tenant_id}/intake
    """
    tenant_id = str(getattr(current_user, "tenant_id", "") or "").strip()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first() if tenant_id else None

    tenant_slug = ""
    if tenant is not None and isinstance(getattr(tenant, "slug", None), str):
        tenant_slug = tenant.slug.strip()

    intake_path = f"/intake/{tenant_slug}" if tenant_slug else f"/t/{tenant_id}/intake"
    intake_url = f"{settings.effective_app_base_url}{intake_path}"
    wa_message = f"Hallo, via deze link kun je jouw schilderaanvraag invullen: {intake_url}"

    return {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "intake_path": intake_path,
        "intake_url": intake_url,
        "whatsapp_share_url": f"https://wa.me/?text={quote(wa_message, safe='')}",
    }


@router.post("/tenant", response_model=TenantOnboardingResponse)
def onboard_tenant(
    payload: TenantOnboardingCreate,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()

    existing = db.query(Tenant).filter(Tenant.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    tenant = create_tenant_with_pricing(db=db, payload=payload)

    return TenantOnboardingResponse(
        tenant_id=tenant.id,
        company_name=tenant.company_name or tenant.name,
        email=tenant.email or "",
        phone=tenant.phone,
        pricing_json=tenant.pricing_json or {},
    )


@router.get("/link", response_class=HTMLResponse)
def onboarding_link_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    link_ctx = _build_intake_urls_for_user(db=db, current_user=current_user)
    company_name = "Aether Engine"
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(getattr(current_user, "tenant_id", "") or ""))
        .first()
    )
    if tenant is not None:
        company_name = (
            (getattr(tenant, "company_name", None) or "").strip()
            or (getattr(tenant, "name", None) or "").strip()
            or company_name
        )
    pricing_json = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant else {}
    current_wall_rate = pricing_json.get("walls_rate_eur_per_sqm")

    return templates.TemplateResponse(
        "app/onboarding_link.html",
        {
            "request": request,
            "title": "Onboarding",
            "company_name": company_name,
            "tenant": tenant,
            "current_wall_rate": current_wall_rate,
            **link_ctx,
        },
    )


@router.post("/set-rate")
def onboarding_set_rate(
    walls_rate_eur_per_sqm: str | None = Form(default=None),
    next: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    redirect_target = (next or "").strip()
    if not redirect_target.startswith("/"):
        redirect_target = "/onboarding/link"

    tenant_id = str(getattr(current_user, "tenant_id", "") or "").strip()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        return RedirectResponse(url=redirect_target, status_code=303)

    raw_value = (walls_rate_eur_per_sqm or "").strip()
    if raw_value:
        # Keep MVP flow forgiving: only update when a valid positive number is submitted.
        try:
            parsed = float(raw_value.replace(",", "."))
            if parsed > 0:
                pricing_json = dict(getattr(tenant, "pricing_json", {}) or {})
                pricing_json["walls_rate_eur_per_sqm"] = parsed
                tenant.pricing_json = pricing_json
                db.add(tenant)
                db.commit()
        except ValueError:
            pass

    return RedirectResponse(url=redirect_target, status_code=303)