from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lead import Lead
from app.models.tenant import Tenant, get_tenant_by_slug
from app.verticals.intake import get_intake_adapter_for_tenant

router = APIRouter(tags=["public-intake"])


@router.get("/t/{tenant_id}/intake")
def public_intake_page(
    request: Request,
    tenant_id: str,
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    v = get_intake_adapter_for_tenant(tenant)

    return v.render_intake_form(
        request=request,
        lead_id="",
        tenant_id=tenant.id,
        extra_context={
            "tenant": tenant,
            "tenant_slug": tenant.slug,
        },
    )


@router.get("/p/{tenant_slug}/intake")
def intake_by_slug(
    request: Request,
    tenant_slug: str,
    db: Session = Depends(get_db),
):
    tenant = get_tenant_by_slug(db, tenant_slug)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    v = get_intake_adapter_for_tenant(tenant)

    return v.render_intake_form(
        request=request,
        lead_id="",
        tenant_id=tenant.id,
        extra_context={
            "tenant": tenant,
            "tenant_slug": tenant.slug,
        },
    )


@router.get("/i/{public_token}/intake")
def intake_by_public_token(
    request: Request,
    public_token: str,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.public_token == public_token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    tenant = db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    v = get_intake_adapter_for_tenant(tenant)
    return v.render_intake_form(
        request=request,
        lead_id=str(lead.id),
        tenant_id=tenant.id,
        extra_context={
            "tenant": tenant,
            "tenant_slug": tenant.slug,
        },
    )
