# app/routers/app_me.py
from fastapi import APIRouter, Depends, Request

from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.i18n.service import resolve_language
from app.models.tenant import Tenant
from app.models.user import User
from app.services.activity_service import get_latest_activity_events, to_iso_utc
from app.services.billing_app_state import (
    billing_page_state_to_api_payload,
    compute_billing_page_state,
)
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email, "tenant_id": user.tenant_id}


@router.get("/api/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_dashboard_summary(db=db, tenant_id=str(user.tenant_id))


@router.get("/api/billing")
def billing_state(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    send_error = (request.query_params.get("send_error") or "").strip()
    billing_status_error = send_error == "billing_status"
    portal_error = (request.query_params.get("portal_error") or "").strip()
    portal_error_no_customer = portal_error == "no_customer"

    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(user.tenant_id))
        .first()
    )
    request_lang = resolve_language(request)
    state = compute_billing_page_state(
        db=db,
        tenant=tenant,
        request_lang=request_lang,
        billing_status_error=billing_status_error,
        portal_error_no_customer=portal_error_no_customer,
    )
    return billing_page_state_to_api_payload(state)


@router.get("/api/dashboard/activity")
def dashboard_activity(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    events = get_latest_activity_events(db, tenant_id=str(user.tenant_id), limit=5)
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "title": event.title,
                "link_url": event.link_url,
                "created_at": to_iso_utc(event.created_at),
            }
            for event in events
        ]
    }
