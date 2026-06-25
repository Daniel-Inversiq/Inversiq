from __future__ import annotations

import logging
import zlib

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_user_html
from app.billing.features import is_subscription_accessible
from app.db import get_db
from app.billing.dependencies import require_active_subscription_for_write
from app.models import Lead
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["processing"])


def _friendly_processing_error(_: str | None = None) -> str:
    return "Er ging iets mis bij het opstellen van je offerte. Probeer het opnieuw of ga terug."


def _short_customer_reference(lead: Lead | None, lead_id: str | None) -> str | None:
    """
    Display-only short reference for customer-facing pages.
    Keeps internal lead_id unchanged.
    """
    raw = (lead_id or "").strip()
    if not raw:
        return None

    # Stable 4-digit numeric suffix based on internal id.
    number = (zlib.crc32(raw.encode("utf-8")) % 9000) + 1000
    year = datetime.now(timezone.utc).year

    if lead is not None:
        created_at = getattr(lead, "created_at", None)
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            year = created_at.year

    return f"PA-{year}-{number}"


def _map_lead_status_for_ui(
    *, lead_status: str, lead_id: str
) -> tuple[str, str | None, str | None]:
    """
    UI status flow:
    queued -> running -> done -> failed
    """
    s = (lead_status or "").upper()
    if s == "NEW":
        return "queued", None, None
    if s == "RUNNING":
        return "running", None, None
    if s in {"SUCCEEDED", "NEEDS_REVIEW", "CONFIG_NEEDED"}:
        # SUCCEEDED: quote HTML
        # NEEDS_REVIEW: internal review queue/detail (not an error state)
        # CONFIG_NEEDED: tenant pricing was missing; send users to offer detail (SPA)
        # where they can fix settings and recalculate.
        redirect_url = (
            f"/quotes/{lead_id}/html"
            if s == "SUCCEEDED"
            else (
                f"/offertes/{lead_id}"
                if s == "CONFIG_NEEDED"
                else f"/app/reviews/{lead_id}"
            )
        )
        return "done", redirect_url, None
    if s == "FAILED":
        return "failed", None, None
    # Fallback: als er onbekende statuses bestaan, behandelen we die als "running".
    return "running", None, None


def _load_lead_by_public_token(db: Session, flow_token: str) -> Lead | None:
    token = (flow_token or "").strip()
    if not token:
        return None
    return db.query(Lead).filter(Lead.public_token == token).first()


def _public_redirect_for_lead(lead: Lead) -> str | None:
    token = str(getattr(lead, "public_token", "") or "").strip()
    if not token:
        return None
    return f"/e/{token}"


def _public_needs_review_without_estimate(
    lead_status: str, has_estimate_html: bool
) -> bool:
    return (lead_status or "").upper() == "NEEDS_REVIEW" and not has_estimate_html


@router.get("/leads/{lead_id}/status")
def lead_status_json(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant=Depends(require_active_subscription_for_write),
) -> dict:
    tenant_id = str(current_user.tenant_id)
    lead = (
        db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[SECURITY_FIX] processing_status tenant-scoped user_id=%s tenant_id=%s lead_id=%s",
        current_user.id,
        tenant_id,
        lead_id,
    )

    # Autostart: als de lead nog nooit is gestart (NEW), start dan de quote
    # zodat /processing/{lead_id} ook werkt als een oude redirect ooit nog
    # naar dit endpoint leidt.
    if (getattr(lead, "status", "") or "").upper() == "NEW":
        try:
            from app.routers.quotes import publish_quote

            publish_quote(
                lead_id=lead.id,
                background=BackgroundTasks(),
                db=db,
                tenant_id=tenant_id,
            )
            lead = (
                db.query(Lead)
                .filter(Lead.id == lead_id, Lead.tenant_id == tenant_id)
                .first()
            )
        except Exception as e:
            lead.status = "FAILED"
            lead.error_message = str(e)
            lead.updated_at = datetime.now(timezone.utc)
            db.add(lead)
            db.commit()
            db.refresh(lead)

    # 1) Lead niet bestaat: handled hierboven.
    # 2) Verwerking gefaald: lead.status == FAILED (of error_message aanwezig).
    lead_status = (getattr(lead, "status", "") or "").upper()
    error_message = getattr(lead, "error_message", None) or None

    if lead_status == "FAILED" or error_message:
        response = {
            "lead_id": str(lead.id),
            "status": "failed",
            "redirect_url": None,
            "error": None,
            "user_message": _friendly_processing_error(error_message),
            "can_retry": True,
            "back_url": "/",
        }
        logger.info(
            "PROCESSING_STATUS_RESPONSE lead_id=%s status=%s redirect_url=%s route=%s",
            response["lead_id"],
            response["status"],
            response["redirect_url"],
            "/processing/{lead_id}",
        )
        return response

    # 3) Done/final redirect decisions (single processing page flow).
    mapped_status, redirect_url, _ = _map_lead_status_for_ui(
        lead_status=lead_status, lead_id=str(lead.id)
    )
    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    is_done_available = (lead_status == "SUCCEEDED" and has_estimate_html) or (
        lead_status == "NEEDS_REVIEW"
    ) or (lead_status == "CONFIG_NEEDED")
    if mapped_status == "done" and is_done_available:
        response = {
            "lead_id": str(lead.id),
            "status": "done",
            "redirect_url": redirect_url,
            "error": None,
        }
        logger.info(
            "PROCESSING_STATUS_RESPONSE lead_id=%s status=%s redirect_url=%s route=%s",
            response["lead_id"],
            response["status"],
            response["redirect_url"],
            (
                "/quotes/{lead_id}/html"
                if str(redirect_url).startswith("/quotes/")
                else "/thank-you"
            ),
        )
        return response

    # 4) Anders => running.
    #    Watchdog: als de backend blijft hangen op RUNNING, ontgrendelen we de UX.
    if lead_status == "RUNNING":
        updated_at = getattr(lead, "updated_at", None)
        if isinstance(updated_at, datetime):
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - updated_at
            if age > timedelta(minutes=15):
                lead.status = "FAILED"
                lead.error_message = "We konden je aanvraag niet op tijd verwerken. Probeer het later opnieuw."
                lead.updated_at = datetime.now(timezone.utc)
                db.add(lead)
                db.commit()
                db.refresh(lead)

                response = {
                    "lead_id": str(lead.id),
                    "status": "failed",
                    "redirect_url": None,
                    "error": None,
                    "user_message": _friendly_processing_error(lead.error_message),
                    "can_retry": True,
                    "back_url": "/",
                }
                logger.info(
                    "PROCESSING_STATUS_RESPONSE lead_id=%s status=%s redirect_url=%s route=%s",
                    response["lead_id"],
                    response["status"],
                    response["redirect_url"],
                    "/processing/{lead_id}",
                )
                return response

    response = {
        "lead_id": str(lead.id),
        "status": "running",
        "redirect_url": None,
        "error": None,
        "user_message": None,
        "can_retry": False,
        "back_url": "/",
    }
    logger.info(
        "PROCESSING_STATUS_RESPONSE lead_id=%s status=%s redirect_url=%s route=%s",
        response["lead_id"],
        response["status"],
        response["redirect_url"],
        "/processing/{lead_id}",
    )
    return response


@router.get("/processing/{lead_id}", response_class=HTMLResponse)
def processing_page(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _tenant=Depends(require_active_subscription_for_write),
) -> HTMLResponse:
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # UX polish: if this route is hit again after completion, skip rendering
    # processing.html and redirect immediately to final route to avoid flash.
    lead_status = (getattr(lead, "status", "") or "").upper()
    mapped_status, redirect_url, _ = _map_lead_status_for_ui(
        lead_status=lead_status, lead_id=str(lead.id)
    )
    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    is_done_available = (lead_status == "SUCCEEDED" and has_estimate_html) or (
        lead_status == "NEEDS_REVIEW"
    ) or (lead_status == "CONFIG_NEEDED")
    if mapped_status == "done" and is_done_available and redirect_url:
        logger.info(
            "PROCESSING_ROUTE_EARLY_REDIRECT lead_id=%s status=%s redirect_url=%s",
            str(lead.id),
            lead_status,
            redirect_url,
        )
        return RedirectResponse(url=str(redirect_url), status_code=303)

    logger.info(
        "PROCESSING_TEMPLATE_RENDER lead_id=%s template=%s",
        str(lead.id),
        "processing.html",
    )
    return request.app.state.templates.TemplateResponse(
        "processing.html",
        {
            "request": request,
            "lead_id": str(lead.id),
            "status_endpoint": f"/leads/{lead.id}/status",
            "retry_endpoint": f"/quotes/publish/{lead.id}",
        },
    )


@router.get("/public/processing/{flow_token}", response_class=HTMLResponse)
def public_processing_page(
    request: Request,
    flow_token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    logger.info("[SECURITY_FIX] public_processing_requested")
    lead = _load_lead_by_public_token(db, flow_token)
    if not lead:
        logger.warning("[SECURITY_FIX] public_flow_token_invalid")
        raise HTTPException(status_code=404, detail="Not found")
    logger.info("[SECURITY_FIX] public_flow_token_valid")

    lead_status = (getattr(lead, "status", "") or "").upper()
    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    public_redirect = _public_redirect_for_lead(lead)

    if _public_needs_review_without_estimate(lead_status, has_estimate_html):
        return RedirectResponse(
            url=f"/thank-you?lead_id={lead.id}&review=1",
            status_code=303,
        )

    is_done_available = (lead_status == "SUCCEEDED" and has_estimate_html) or (
        lead_status == "NEEDS_REVIEW" and has_estimate_html
    )
    if is_done_available and public_redirect:
        return RedirectResponse(url=public_redirect, status_code=303)

    return request.app.state.templates.TemplateResponse(
        "processing.html",
        {
            "request": request,
            "lead_id": str(lead.id),
            "status_endpoint": f"/public/leads/{flow_token}/status",
            "retry_endpoint": f"/public/processing/{flow_token}/retry",
        },
    )


@router.get("/public/leads/{flow_token}/status")
def public_processing_status(flow_token: str, db: Session = Depends(get_db)) -> dict:
    logger.info("[SECURITY_FIX] public_processing_status_requested")
    lead = _load_lead_by_public_token(db, flow_token)
    if not lead:
        logger.warning("[SECURITY_FIX] public_flow_token_invalid")
        raise HTTPException(status_code=404, detail="Not found")
    logger.info("[SECURITY_FIX] public_flow_token_valid")

    lead_status = (getattr(lead, "status", "") or "").upper()
    if lead_status == "NEW":
        try:
            from app.routers.quotes import publish_quote

            publish_quote(
                lead_id=str(lead.id),
                background=BackgroundTasks(),
                db=db,
                tenant_id=str(lead.tenant_id),
            )
            db.refresh(lead)
            lead_status = (getattr(lead, "status", "") or "").upper()
        except Exception as e:
            lead.status = "FAILED"
            lead.error_message = str(e)
            lead.updated_at = datetime.now(timezone.utc)
            db.add(lead)
            db.commit()
            db.refresh(lead)
            lead_status = "FAILED"

    error_message = getattr(lead, "error_message", None) or None
    if lead_status == "FAILED" or error_message:
        return {
            "status": "failed",
            "redirect_url": None,
            "error": None,
            "user_message": _friendly_processing_error(error_message),
            "can_retry": True,
            "back_url": "/",
        }

    # CONFIG_NEEDED: publish_quote exits before the engine (missing tenant pricing).
    # Without this branch the public page polls "running" forever (see lead_status_json
    # which maps CONFIG_NEEDED to a terminal state for logged-in flows).
    if lead_status == "CONFIG_NEEDED":
        logger.info(
            "PROCESSING_STATUS_PUBLIC_CONFIG_NEEDED lead_id=%s tenant_id=%s",
            str(lead.id),
            str(getattr(lead, "tenant_id", "") or ""),
        )
        return {
            "status": "review_pending",
            "redirect_url": None,
            "error": None,
            "user_message": (
                "Je aanvraag is ontvangen. De schilder moet nog een prijs per m² instellen "
                "voordat je offerte automatisch kan worden berekend. Je hoort snel van hen."
            ),
            "can_retry": False,
            "back_url": "/",
        }

    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    public_redirect = _public_redirect_for_lead(lead)
    is_done_available = (lead_status == "SUCCEEDED" and has_estimate_html) or (
        lead_status == "NEEDS_REVIEW" and has_estimate_html
    )
    if is_done_available and public_redirect:
        return {
            "status": "done",
            "redirect_url": public_redirect,
            "error": None,
        }

    if _public_needs_review_without_estimate(lead_status, has_estimate_html):
        return {
            "status": "done",
            "redirect_url": f"/thank-you?lead_id={lead.id}&review=1",
            "error": None,
            "user_message": "Er is nog een extra controle nodig voordat we de offerte kunnen tonen.",
            "can_retry": False,
            "back_url": "/",
        }

    # Same watchdog as /leads/{id}/status: stuck RUNNING should not spin forever in the browser.
    if lead_status == "RUNNING":
        updated_at = getattr(lead, "updated_at", None)
        if isinstance(updated_at, datetime):
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - updated_at
            if age > timedelta(minutes=15):
                lead.status = "FAILED"
                lead.error_message = (
                    "We konden je aanvraag niet op tijd verwerken. Probeer het later opnieuw."
                )
                lead.updated_at = datetime.now(timezone.utc)
                db.add(lead)
                db.commit()
                db.refresh(lead)
                logger.warning(
                    "PROCESSING_STATUS_PUBLIC_RUNNING_WATCHDOG lead_id=%s age=%s",
                    str(lead.id),
                    age,
                )
                return {
                    "status": "failed",
                    "redirect_url": None,
                    "error": None,
                    "user_message": _friendly_processing_error(lead.error_message),
                    "can_retry": True,
                    "back_url": "/",
                }

    return {
        "status": "running",
        "redirect_url": None,
        "error": None,
        "user_message": None,
        "can_retry": False,
        "back_url": "/",
    }


@router.post("/public/processing/{flow_token}/retry", response_model=None)
def public_processing_retry(
    flow_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("[SECURITY_FIX] public_processing_requested")
    lead = _load_lead_by_public_token(db, flow_token)
    if not lead:
        logger.warning("[SECURITY_FIX] public_flow_token_invalid")
        raise HTTPException(status_code=404, detail="Not found")
    logger.info("[SECURITY_FIX] public_flow_token_valid")

    tenant = db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()
    subscription_status = (
        getattr(tenant, "subscription_status", None) if tenant else None
    )
    trial_ends_at = getattr(tenant, "trial_ends_at", None) if tenant else None
    if not is_subscription_accessible(subscription_status, trial_ends_at):
        # Public retry is blocked for trial-expired/inactive tenants:
        # no publish trigger, return controlled response.
        wants_html = "text/html" in (request.headers.get("accept") or "")
        if wants_html:
            return HTMLResponse(
                content="<div class='text-sm text-slate-600'>Retry is niet beschikbaar: abonnement niet actief.</div>",
                status_code=200,
            )
        raise HTTPException(status_code=403, detail="subscription_inactive")

    try:
        from app.routers.quotes import publish_quote

        publish_quote(
            lead_id=str(lead.id),
            background=BackgroundTasks(),
            db=db,
            tenant_id=str(lead.tenant_id),
        )
    except Exception:
        pass
    return {"ok": True}


@router.get("/offerte/{lead_id}")
def offerte_redirect(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    """
    Interne offerte-URL voor ingelogde gebruikers.
    Verwijst naar de preview-route (ruwe offerte-HTML), niet naar de klantpagina /e/{token}.
    """
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        logger.info(
            "OFFERTE_REDIRECT_REJECT lead_id=%s reason=%s",
            lead_id,
            "lead_not_found",
        )
        raise HTTPException(status_code=404, detail="Lead not found")

    logger.info(
        "OFFERTE_REDIRECT_CHECK lead_id=%s status=%s public_token=%r estimate_html_key=%r",
        str(getattr(lead, "id", lead_id)),
        str(getattr(lead, "status", None)),
        getattr(lead, "public_token", None),
        getattr(lead, "estimate_html_key", None),
    )

    if not getattr(lead, "public_token", None):
        logger.info(
            "OFFERTE_REDIRECT_REJECT lead_id=%s status=%s public_token=%r estimate_html_key=%r reason=%s",
            str(getattr(lead, "id", lead_id)),
            str(getattr(lead, "status", None)),
            getattr(lead, "public_token", None),
            getattr(lead, "estimate_html_key", None),
            "missing_public_token",
        )
        raise HTTPException(status_code=404, detail="Offerte nog niet beschikbaar")

    target = f"/app/leads/{lead_id}/estimate"
    logger.info(
        "OFFERTE_REDIRECT_OK lead_id=%s status=%s public_token=%r estimate_html_key=%r redirect=%s",
        str(getattr(lead, "id", lead_id)),
        str(getattr(lead, "status", None)),
        getattr(lead, "public_token", None),
        getattr(lead, "estimate_html_key", None),
        target,
    )
    return RedirectResponse(url=target, status_code=303)


@router.get("/thank-you", response_class=HTMLResponse)
def thank_you_page(
    request: Request,
    lead_id: str | None = None,
    review: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    is_review_mode = (review or "").strip().lower() in {"1", "true", "yes"}
    lead = None
    if lead_id:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
    short_reference = _short_customer_reference(lead, lead_id)

    return request.app.state.templates.TemplateResponse(
        "thank_you.html",
        {
            "request": request,
            "lead_id": lead_id,
            "customer_reference": short_reference,
            "is_review_mode": is_review_mode,
        },
    )
