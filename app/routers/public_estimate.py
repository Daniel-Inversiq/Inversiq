# app/routers/public_estimate.py
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
import json
from decimal import Decimal, InvalidOperation

from app.core.settings import settings
from app.db import get_db
from app.models.lead import Lead
from app.models.user import User
from app.models.tenant import Tenant
from app.models.job import Job
from app.services.branding import (
    branding_html_debug_summary,
    is_custom_branding_allowed,
    log_branding_state,
    normalize_plan,
)
from app.services.email_service import send_email, EmailSendError
from app.services.storage import get_storage, get_text, LocalStorage
from app.services.workflow import (
    ensure_job_for_lead,
    mark_lead_accepted,
    mark_lead_viewed,
)
from app.verticals.painting.email_render import (
    render_estimate_accepted_email,
    render_painter_estimate_accepted_email,
)
from app.workflow.status import apply_workflow
from app.i18n.service import setup_jinja_i18n

router = APIRouter(prefix="/e", tags=["public_estimate"])
# Alias router for simple customer-friendly quote URL (/q/{public_token})
router_q = APIRouter(prefix="/q", tags=["public_quote"])
paintly_templates = Jinja2Templates(directory="app/verticals/painting/templates")
setup_jinja_i18n(paintly_templates)

logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    t = (token or "").strip()
    if len(t) <= 8:
        return "***"
    return f"{t[:4]}...{t[-4:]}"


async def send_painter_accept_email(
    *,
    painter_email: str,
    company_name: str,
    lead_name: str,
    lead_email: str,
    lead_phone: str,
    project_description: str,
    square_meters: str,
    job_type: str,
    price_display: str,
    quote_url: str,
    admin_url: str,
) -> None:
    subject = f"Offerte geaccepteerd - {lead_name or 'Onbekende klant'}"

    html_body = render_painter_estimate_accepted_email(
        company_name=company_name,
        lead_name=lead_name,
        lead_email=lead_email,
        lead_phone=lead_phone,
        project_description=project_description,
        square_meters=square_meters,
        job_type=job_type,
        price_display=price_display,
        quote_url=quote_url,
        admin_url=admin_url,
    )

    text_body = (
        "Een klant heeft de offerte geaccepteerd.\n\n"
        f"Klant: {lead_name or '—'}\n"
        f"E-mail: {lead_email or '—'}\n"
        f"Telefoon: {lead_phone or '—'}\n"
        f"Type werk: {job_type or '—'}\n"
        f"Oppervlakte: {square_meters or '—'}\n"
        f"Prijs: {price_display or '—'}\n"
        f"Projectnotities: {project_description or '—'}\n\n"
        f"Dashboard: {admin_url}\n"
        f"Publieke offerte: {quote_url}\n"
    )

    await send_email(
        to=painter_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        tag="painter-accepted",
        metadata={},
    )


def _fmt_price_eur(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "—"
    amount = amount.quantize(Decimal("0.01"))
    s = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"EUR {s}"


def _extract_quote_summary(lead: Lead) -> tuple[str, str, str, str]:
    notes = (getattr(lead, "notes", "") or "").strip()
    square_meters = ""
    job_type = ""
    price_display = "—"
    intake_raw = getattr(lead, "intake_payload", None)
    if isinstance(intake_raw, str) and intake_raw.strip():
        try:
            intake = json.loads(intake_raw)
        except Exception:
            intake = {}
        if isinstance(intake, dict):
            square_meters = str(
                intake.get("square_meters")
                or intake.get("area_sqm")
                or intake.get("sqm")
                or ""
            ).strip()
            job_type = str(intake.get("job_type") or "").strip()
            if not notes:
                notes = str(intake.get("project_description") or "").strip()

    final_price = getattr(lead, "final_price", None)
    if final_price is not None:
        price_display = _fmt_price_eur(final_price)
    else:
        estimate_raw = getattr(lead, "estimate_json", None)
        if isinstance(estimate_raw, str) and estimate_raw.strip():
            try:
                estimate = json.loads(estimate_raw)
            except Exception:
                estimate = {}
            if isinstance(estimate, dict):
                totals = estimate.get("totals") or {}
                value = totals.get("grand_total") or totals.get("pre_tax")
                if value is not None:
                    price_display = _fmt_price_eur(value)

    square_meters_display = f"{square_meters} m2" if square_meters else "—"
    return notes or "—", square_meters_display, job_type or "—", price_display


def _derive_ui_status(*, lead_status: str, mode: str) -> str:
    """
    Canonical UI status for quote page shell (labels/banners, not accept/reject).
    - draft: concept / pre-send on public link
    - published: sent or viewed by customer (post-send)
    - accepted: terminal customer accepted state
    """
    status = (lead_status or "").upper()
    ui_mode = (mode or "").strip().lower() or "internal"

    if status == "ACCEPTED":
        return "accepted"

    if ui_mode == "public":
        # Public /e/{token}: same link exists before send; shell stays "draft" until SENT/VIEWED.
        if status in {"SENT", "VIEWED"}:
            return "published"
        return "draft"

    if status in {"SENT", "VIEWED"}:
        return "published"

    return "draft"


def _can_customer_act(lead_status: str) -> bool:
    """Accept/reject only after painter explicitly sent (dashboard send → SENT; first view may→ VIEWED)."""
    return (lead_status or "").upper() in {"SENT", "VIEWED"}


def _is_pre_send_public_status(lead_status: str) -> bool:
    """Quote may exist (e.g. SUCCEEDED) but customer actions are not open yet."""
    st = (lead_status or "").upper()
    return st in {"SUCCEEDED", "NEEDS_REVIEW", "NEW", "RUNNING", "FAILED"}


@router.get("/{token}", response_class=HTMLResponse)
def public_estimate(token: str, request: Request, db: Session = Depends(get_db), preview: bool = False):
    lead = db.query(Lead).filter(Lead.public_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")

    # DEMO-SAFE OVERRIDE:
    # - Als de lead in NEEDS_REVIEW staat, of als de estimate-meta aangeeft
    #   dat er duidelijke wandschade / heavy prep aanwezig is, tonen we geen
    #   volledige offerte maar een simpele "review vereist"-pagina.
    try:
        status_upper = (lead.status or "").upper()
        meta_reasons = []
        raw_json_lower = ""
        try:
            import json as _json

            raw = getattr(lead, "estimate_json", None)
            if isinstance(raw, str) and raw.strip():
                raw_json_lower = raw.lower()
                est = _json.loads(raw)
                if isinstance(est, dict):
                    meta = est.get("meta") or {}
                    if isinstance(meta, dict):
                        rr = meta.get("needs_review_reasons") or []
                        if isinstance(rr, list):
                            meta_reasons = rr
        except Exception:
            meta_reasons = []

        severe_structural_reasons = {
            "substrate_visible",
            "peeling_wallcovering_detected",
            "repair_work_required",
            "surface_damage_detected",
        }

        # Sterke string-gebaseerde fallback voor demo:
        damage_keywords = [
            "wallpaper",
            "wallpaper_removal",
            "peeling",
            "exposed_plaster",
            "substrate",
            "damaged",
            "repair",
            "heavy_prep",
            "plaster_visible",
            "loose_wallcovering",
        ]
        strong_damage_hit = bool(
            raw_json_lower
            and any(kw in raw_json_lower for kw in damage_keywords)
        )

        meta_has_wall_repair = "wall_repair_or_wallpaper_likely" in meta_reasons

        if (
            (status_upper == "NEEDS_REVIEW")
            and (
                any(r in severe_structural_reasons for r in meta_reasons)
                or meta_has_wall_repair
            )
        ) or strong_damage_hit:
            logger.info(
                "QUOTE_OUTPUT_DECISION lead_id=%s needs_review=%s lead_status=%s pricing_status=%s total_price=%r price_mode=%s template=%s review_page=%s show_prices=%s pricing_ready=%s is_provisional=%s review_reasons=%r",
                getattr(lead, "id", None),
                True,
                status_upper,
                "public_estimate",
                None,
                "tbd",
                "inline_review_html",
                True,
                False,
                False,
                False,
                meta_reasons,
            )
            return HTMLResponse(
                content=f"""
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Offerte in review — Inversiq</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-gray-50 text-slate-900 antialiased">
  <div class="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6">
    <div class="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-lg">
      <div class="flex items-center gap-4">
        <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200">
          <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <p class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Inversiq bevestiging</p>
          <h1 class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            Bedankt, we gaan uw aanvraag controleren
          </h1>
        </div>
      </div>

      <p class="mt-4 text-sm leading-relaxed text-slate-600 sm:text-base">
        We hebben uw foto's goed ontvangen. Omdat dit project extra controle vraagt,
        bekijkt een specialist de situatie handmatig. U ontvangt daarna zo snel mogelijk
        een nauwkeurige prijsinschatting.
      </p>

      <div class="mt-4 flex flex-wrap gap-2">
        <span class="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">Foto's ontvangen</span>
        <span class="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">Handmatige controle</span>
        <span class="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">Reactie zo snel mogelijk</span>
      </div>

      <div class="my-6 h-px w-full bg-slate-200"></div>

      <div class="text-center">
        <p class="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Aanvraagnummer</p>
        <span class="mt-2 inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-4 py-1.5 text-sm font-semibold tracking-wide text-slate-800">
          #{str(getattr(lead, "id", ""))[-8:].upper()}
        </span>
      </div>

      <div class="mt-6 rounded-2xl bg-amber-50 px-5 py-4 text-center text-sm text-amber-900 ring-1 ring-amber-200">
        In de meeste gevallen ontvangt u binnen korte tijd een bijgewerkte offerte per e-mail.
      </div>
    </div>
  </div>
</body>
</html>
                """,
                status_code=200,
            )
    except Exception:
        # Failsafe: als de review-check faalt, val terug op normale render-flow.
        pass

    html_key = (getattr(lead, "estimate_html_key", None) or "").strip()
    if not html_key:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if not preview:
        mark_lead_viewed(db, lead)
        db.commit()

    # Normaliseer tenant_id + key op dezelfde manier als de interne HTML-flow:
    # - tenant_id fallback naar "default"
    # - strip eventuele tenant-prefix uit html_key
    tenant_id = str((lead.tenant_id or "").strip() or "default")
    key = html_key
    prefix = f"{tenant_id}/"
    if key.startswith(prefix):
        key = key[len(prefix) :]

    logger.info(
        "PUBLIC_ESTIMATE_ROUTE lead_id=%s token=%s html_key_raw=%r key_norm=%r",
        getattr(lead, "id", None),
        _mask_token(token),
        html_key,
        key,
    )

    storage = get_storage()

    # ================
    # HTML laden
    # ================
    html = None
    iframe_url = None

    # Gedetailleerde debug-logging vóór het laden
    logger.info(
        "PUBLIC_ESTIMATE_LOAD_ATTEMPT lead_id=%s tenant_raw=%r tenant_norm=%s "
        "html_key_raw=%r key_norm=%r storage=%s",
        getattr(lead, "id", None),
        getattr(lead, "tenant_id", None),
        tenant_id,
        html_key,
        key,
        type(storage).__name__,
    )

    if isinstance(storage, LocalStorage):
        # LocalStorage: gebruik dezelfde publieke URL-strategie als de interne flow
        # (public_url) in plaats van download/get_text, om local_not_found issues te vermijden.
        try:
            iframe_url = storage.public_url(tenant_id=tenant_id, key=key)
        except Exception as e:
            logger.exception(
                "PUBLIC_ESTIMATE_LOCAL_URL_FAILED lead_id=%s tenant=%s key=%s exc=%r",
                getattr(lead, "id", None),
                tenant_id,
                key,
                e,
            )
            return HTMLResponse(
                content=f"""
<div style="max-width:900px;margin:40px auto;font-family:system-ui;">
  <h2>Estimate temporarily unavailable</h2>
  <p class="muted">We couldn't build a public URL for this estimate file.</p>
  <pre style="background:#f6f6f6;padding:12px;border-radius:10px;overflow:auto;">{html_key}</pre>
  <p>Please contact the contractor and ask them to resend the estimate.</p>
</div>
""",
                status_code=200,
            )
    else:
        try:
            html = get_text(storage, tenant_id=tenant_id, key=key)
        except Exception as e:
            # Log de exacte exception + traceback met alle relevante context
            logger.exception(
                "PUBLIC_ESTIMATE_LOAD_FAILED lead_id=%s tenant_raw=%r tenant_norm=%s "
                "html_key_raw=%r key_norm=%r storage=%s exc=%r",
                getattr(lead, "id", None),
                getattr(lead, "tenant_id", None),
                tenant_id,
                html_key,
                key,
                type(storage).__name__,
                e,
            )
            return HTMLResponse(
                content=f"""
<div style="max-width:900px;margin:40px auto;font-family:system-ui;">
  <h2>Estimate temporarily unavailable</h2>
  <p class="muted">We couldn't load this estimate file.</p>
  <pre style="background:#f6f6f6;padding:12px;border-radius:10px;overflow:auto;">{html_key}</pre>
  <p>Please contact the contractor and ask them to resend the estimate.</p>
</div>
""",
                status_code=200,
            )

    logger.info(
        "ESTIMATE_HTML_SNAPSHOT_LOAD lead_id=%s html_key_raw=%r key_norm=%r delivery=%s bytes=%s",
        getattr(lead, "id", None),
        html_key,
        key,
        "iframe_url" if iframe_url else "inline_body",
        len((html or "").encode("utf-8")) if isinstance(html, str) and html and not iframe_url else None,
    )

    lead_status = (lead.status or "").upper()
    ui_mode = "public"
    ui_status = _derive_ui_status(lead_status=lead_status, mode=ui_mode)
    can_customer_act = _can_customer_act(lead_status)
    is_pre_send = _is_pre_send_public_status(lead_status)
    logger.info(
        "[QUOTE_STATE] estimate_id=%s token=%s status=%s is_public=%s can_customer_act=%s ui_status=%s is_pre_send=%s",
        str(getattr(lead, "id", "")),
        _mask_token(token),
        lead_status,
        True,
        can_customer_act,
        ui_status,
        is_pre_send,
    )
    logger.info(
        "[UI_MODE] estimate_id=%s is_public=%s route=%s",
        str(getattr(lead, "id", "")),
        True,
        f"GET /e/{token}",
    )

    # Bodycontent: inline HTML (S3) of iframe (LocalStorage)
    if iframe_url:
        body_html = f"""
<iframe src="{iframe_url}" style="width:100%;border:0;display:block;" loading="lazy"></iframe>
"""
    else:
        body_html = html

    tenant_company_name = ""
    tenant_logo_url = ""
    tenant_user = (
        db.query(User)
        .filter(User.tenant_id == str(lead.tenant_id), User.is_active == True)  # noqa: E712
        .order_by(User.created_at.desc(), User.id.desc())
        .first()
    )
    tenant_row = db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()
    # Prefer tenant-level branding for public pages; fall back to user branding.
    if tenant_row is not None:
        tenant_company_name = (getattr(tenant_row, "company_name", None) or "").strip()
        tenant_logo_url = (getattr(tenant_row, "logo_url", None) or "").strip()
    if (not tenant_company_name or not tenant_logo_url) and tenant_user is not None:
        user_company_name = (getattr(tenant_user, "company_name", None) or "").strip()
        user_logo_url = (getattr(tenant_user, "logo_url", None) or "").strip()
        if not tenant_company_name:
            tenant_company_name = user_company_name
        if not tenant_logo_url:
            tenant_logo_url = user_logo_url

    plan_raw = getattr(tenant_row, "plan_code", None) if tenant_row is not None else None
    plan_normalized = normalize_plan(plan_raw)
    branding_allowed = is_custom_branding_allowed(plan_raw)
    chosen_custom_name = tenant_company_name or ((getattr(tenant_user, "company_name", None) or "").strip())
    chosen_custom_logo = tenant_logo_url or ((getattr(tenant_user, "logo_url", None) or "").strip())
    if branding_allowed and chosen_custom_name:
        branding_company_name = chosen_custom_name
        branding_logo_url = chosen_custom_logo or None
        branding_source = "tenant" if tenant_company_name else "user"
        fallback_reason = None if branding_logo_url else "logo_missing"
    else:
        branding_company_name = "Inversiq"
        branding_logo_url = None
        branding_source = "default"
        fallback_reason = "tier_not_allowed" if not branding_allowed else "company_name_missing"

    header_phone = ""
    header_email = ""
    if tenant_row is not None:
        header_phone = (getattr(tenant_row, "phone", None) or "").strip()
        header_email = (getattr(tenant_row, "email", None) or "").strip()
    if not header_email and tenant_user is not None:
        header_email = (getattr(tenant_user, "email", None) or "").strip()

    log_branding_state(
        logger,
        "settings_loaded_public",
        {
            "lead_id": str(getattr(lead, "id", "")),
            "user_id": str(getattr(tenant_user, "id", "")) if tenant_user is not None else None,
            "tenant_id": str(getattr(lead, "tenant_id", "")),
            "user_company_name": (getattr(tenant_user, "company_name", None) if tenant_user is not None else None),
            "tenant_company_name": (getattr(tenant_row, "company_name", None) if tenant_row is not None else None),
            "user_logo_url": (getattr(tenant_user, "logo_url", None) if tenant_user is not None else None),
            "tenant_logo_url": (getattr(tenant_row, "logo_url", None) if tenant_row is not None else None),
            "plan_raw": plan_raw,
            "plan_normalized": plan_normalized,
            "branding_allowed": branding_allowed,
        },
    )
    log_branding_state(
        logger,
        "tier_gating_public",
        {
            "tier_source": "tenant.plan_code",
            "plan_raw": plan_raw,
            "plan_normalized": plan_normalized,
            "branding_allowed": branding_allowed,
        },
    )
    log_branding_state(
        logger,
        "public_render_input",
        {
            "lead_id": str(getattr(lead, "id", "")),
            "branding_company_name": branding_company_name,
            "branding_logo_url": branding_logo_url,
            "branding_allowed": branding_allowed,
            "branding_source": branding_source,
            "fallback_reason": fallback_reason,
        },
    )
    logger.info(
        "PUBLIC_BRANDING_RESOLVE lead_id=%s tenant_id=%s selected_user_id=%s selected_user_email=%r selected_user_company_name=%r selected_user_logo_url=%r tenant_company_name=%r tenant_logo_url=%r plan_raw=%r plan_normalized=%r branding_allowed=%s final_branding_company_name=%r final_branding_logo_url=%r fallback_reason=%r",
        str(getattr(lead, "id", "")),
        str(getattr(lead, "tenant_id", "")),
        str(getattr(tenant_user, "id", "")) if tenant_user is not None else None,
        (getattr(tenant_user, "email", None) if tenant_user is not None else None),
        (getattr(tenant_user, "company_name", None) if tenant_user is not None else None),
        (getattr(tenant_user, "logo_url", None) if tenant_user is not None else None),
        (getattr(tenant_row, "company_name", None) if tenant_row is not None else None),
        (getattr(tenant_row, "logo_url", None) if tenant_row is not None else None),
        plan_raw,
        plan_normalized,
        branding_allowed,
        branding_company_name,
        branding_logo_url,
        fallback_reason,
    )

    if isinstance(body_html, str):
        log_branding_state(
            logger,
            "public_html_loaded",
            {
                "lead_id": str(getattr(lead, "id", "")),
                "token": _mask_token(token),
                "estimate_html_key": html_key,
                **branding_html_debug_summary(body_html, branding_name=branding_company_name),
            },
        )

    page_html = paintly_templates.env.get_template("public/customer_quote_page.html").render(
        token=lead.public_token,
        can_customer_act=bool(can_customer_act),
        is_pre_send=bool(is_pre_send),
        lead_status=lead_status,
        ui_status=ui_status,
        ui_mode=ui_mode,
        is_public=True,
        is_preview=bool(preview),
        iframe_url=iframe_url,
        body_html=body_html or "",
        branding_company_name=branding_company_name,
        branding_logo_url=branding_logo_url,
        header_phone=header_phone or None,
        header_email=header_email or None,
    )
    logger.info(
        "QUOTE_OUTPUT_DECISION lead_id=%s needs_review=%s lead_status=%s pricing_status=%s total_price=%r price_mode=%s template=%s review_page=%s show_prices=%s pricing_ready=%s is_provisional=%s review_reasons=%r",
        getattr(lead, "id", None),
        bool(lead_status == "NEEDS_REVIEW"),
        lead_status,
        "public_quote_page",
        None,
        "unknown",
        "public/customer_quote_page.html",
        False,
        None,
        None,
        None,
        None,
    )
    return HTMLResponse(content=page_html)


@router_q.get("/{token}", response_class=HTMLResponse)
def public_quote_alias(token: str):
    """
    MVP-public route for customers: /q/{public_token}
    Keeps implementation DRY by delegating to existing /e/{token} handler.
    """
    # Use a 302 redirect so bookmarks continue to work even if /e implementation evolves.
    return RedirectResponse(url=f"/e/{token}", status_code=302)


@router.post("/{token}/accept")
def public_accept(
    token: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.public_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")

    st = (lead.status or "").upper()
    if st != "ACCEPTED" and not _can_customer_act(st):
        logger.info(
            "[QUOTE_STATE] estimate_id=%s token=%s status=%s is_public=%s can_customer_act=False action=accept_blocked",
            str(getattr(lead, "id", "")),
            _mask_token(token),
            st,
            True,
        )
        raise HTTPException(
            status_code=403,
            detail="Deze offerte kan nog niet worden geaccepteerd. Wacht tot uw schilder de offerte heeft verzonden.",
        )

    if (lead.status or "").upper() != "ACCEPTED":
        mark_lead_accepted(db, lead)
        lead.reject_reason = None
        apply_workflow(db, lead)
        db.commit()

        override_email = (
            getattr(settings, "PAINTER_NOTIFICATION_OVERRIDE_EMAIL", "") or ""
        ).strip()

        try:
            painter = (
                db.query(User)
                .filter(User.tenant_id == lead.tenant_id)
                .filter(User.email.isnot(None))
                .filter(User.email != "")
                .order_by(User.id.asc())
                .first()
            )
            db_painter_email = (getattr(painter, "email", "") or "").strip()
        except Exception:
            db_painter_email = ""

        painter_email = override_email or db_painter_email

        if painter_email:
            base = (
                settings.APP_PUBLIC_BASE_URL
                or str(getattr(settings, "APP_PUBLIC_BASE_URL", ""))
                or ""
            ).rstrip("/")

            if not base:
                quote_url = f"/e/{lead.public_token}"
                admin_url = f"/app/leads/{lead.id}"
            else:
                quote_url = f"{base}/e/{lead.public_token}"
                admin_url = f"{base}/app/leads/{lead.id}"
            project_description, square_meters, job_type, price_display = (
                _extract_quote_summary(lead)
            )

            background.add_task(
                send_painter_accept_email,
                painter_email=painter_email,
                company_name="Inversiq",
                lead_name=getattr(lead, "name", "") or "—",
                lead_email=getattr(lead, "email", "") or "",
                lead_phone=getattr(lead, "phone", "") or "",
                project_description=project_description,
                square_meters=square_meters,
                job_type=job_type,
                price_display=price_display,
                quote_url=quote_url,
                admin_url=admin_url,
            )

        if getattr(settings, "SEND_ACCEPT_CONFIRMATION_EMAIL", True):
            to_email = (getattr(lead, "email", "") or "").strip()
            if to_email:
                base = (settings.APP_PUBLIC_BASE_URL or "").rstrip("/")
                public_url = (
                    f"{base}/e/{lead.public_token}"
                    if base
                    else f"/e/{lead.public_token}"
                )
                customer_name = getattr(lead, "name", "") or ""
                company_name = "Inversiq"

                async def _send():
                    html_body = render_estimate_accepted_email(
                        customer_name=customer_name,
                        quote_url=public_url,
                        company_name=company_name,
                    )
                    text_body = (
                        f"Beste {customer_name or 'klant'},\n\n"
                        "Bedankt, uw akkoord op de offerte is ontvangen.\n"
                        "We nemen binnenkort contact met u op om de planning te bevestigen.\n\n"
                        f"Bekijk uw offerte: {public_url}\n"
                    )
                    try:
                        await send_email(
                            to=to_email,
                            subject="Uw akkoord is ontvangen",
                            html_body=html_body,
                            text_body=text_body,
                            tag="customer-accepted",
                            metadata={
                                "lead_id": str(lead.id),
                                "tenant_id": str(lead.tenant_id),
                            },
                        )
                    except EmailSendError:
                        return

                background.add_task(_send)

    redirect_url = f"/e/{token}/accepted"

    if (request.headers.get("hx-request") or "").lower() == "true":
        return HTMLResponse("", headers={"HX-Redirect": redirect_url})

    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept:
        return JSONResponse({"ok": True, "redirect": redirect_url})

    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/{token}/reject")
def public_reject(
    token: str,
    request: Request,
    reject_reason: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.public_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")
    if (lead.status or "").upper() == "ACCEPTED":
        redirect_url = f"/e/{token}/accepted"
        if (request.headers.get("hx-request") or "").lower() == "true":
            return HTMLResponse("", headers={"HX-Redirect": redirect_url})
        accept = (request.headers.get("accept") or "").lower()
        if "application/json" in accept:
            return JSONResponse({"ok": True, "redirect": redirect_url})
        return RedirectResponse(url=redirect_url, status_code=303)

    st = (lead.status or "").upper()
    if not _can_customer_act(st):
        logger.info(
            "[QUOTE_STATE] estimate_id=%s token=%s status=%s is_public=%s can_customer_act=False action=reject_blocked",
            str(getattr(lead, "id", "")),
            _mask_token(token),
            st,
            True,
        )
        raise HTTPException(
            status_code=403,
            detail="Deze offerte kan nog niet worden afgewezen. Wacht tot uw schilder de offerte heeft verzonden.",
        )

    lead.status = "REJECTED"
    reason = (reject_reason or "").strip()
    lead.reject_reason = reason[:1000] if reason else None
    db.add(lead)
    db.commit()

    redirect_url = f"/e/{token}/rejected"
    if (request.headers.get("hx-request") or "").lower() == "true":
        return HTMLResponse("", headers={"HX-Redirect": redirect_url})
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept:
        return JSONResponse({"ok": True, "redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/{token}/accepted", response_class=HTMLResponse)
def public_accepted_confirmation(token: str, request: Request, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.public_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")
    return paintly_templates.TemplateResponse(
        "public/quote_accepted_confirmation.html",
        {
            "request": request,
            "token": token,
        },
    )


@router.get("/{token}/rejected", response_class=HTMLResponse)
def public_rejected_confirmation(token: str, request: Request, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.public_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")
    return paintly_templates.TemplateResponse(
        "public/quote_rejected_confirmation.html",
        {
            "request": request,
            "token": token,
        },
    )
