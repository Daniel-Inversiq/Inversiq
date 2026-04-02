# app/routers/router_app.py
from __future__ import annotations

import secrets
import uuid
import datetime as dt
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import logging
import json
import stripe
import os
import re
from urllib.parse import quote, urlencode
from typing import Any

from fastapi import BackgroundTasks
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, Field

from app.auth.deps import require_user_html
from app.db import get_db
from app.models.lead import Lead
from app.models.job import Job
from app.models.user import User
from app.models.tenant import Tenant
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.tenant_settings import TenantSettings
from app.services.storage import get_storage, get_text
from app.models.lead import LeadFile
from app.models.upload_record import UploadRecord, UploadStatus

from app.core.settings import settings
from app.core.stripe_config import (
    APP_BASE_URL,
    ensure_stripe_api_key,
)
from app.core.plan_catalog import (
    CANONICAL_PLAN_CODES,
    DEFAULT_PLAN_CODE,
    PLAN_CATALOG,
    get_plan_item,
    get_stripe_price_id,
)
from app.dependencies import tenant_service
from app.services.usage_service import get_or_create_usage, increment_usage
from app.services.billing_summary_service import (
    get_billing_offer_usage_view,
    get_billing_usage_summary,
)
from app.i18n.service import resolve_language, setup_jinja_i18n, translate
from app.verticals.paintly.google_calendar_service import (
    build_appointment_event_payload,
    create_google_calendar_event_for_tenant,
    fetch_upcoming_calendar_events_merged,
    utc_normalize_appointment_datetime,
)
from app.verticals.paintly.email_render import render_estimate_ready_email
from app.verticals.paintly.estimate_email import (
    send_estimate_ready_email_to_customer,
)
from app.services.email_service import EmailSendError
from app.verticals.paintly.render_estimate import render_estimate_pdf_html
from app.verticals.paintly.review_labels import review_label_nl
from app.utils.slugs import slugify
from app.billing.features import Feature, tenant_has_feature
from app.billing.ui import tenant_entitlements, tenant_feature_flags, tenant_feature_ui
from app.billing.entitlements import Action, check_entitlement
from app.billing.dependencies import (
    require_entitlement,
    require_active_subscription_for_write,
)


router = APIRouter(
    prefix="/app",
    tags=["paintly_app"],
    dependencies=[Depends(require_user_html)],
)
templates = Jinja2Templates(directory="app/verticals/paintly/templates")
templates.env.globals["review_label_nl"] = review_label_nl
setup_jinja_i18n(templates)


def _url_query_quote(value: object) -> str:
    """URL-encode a string for use as a single query value (e.g. wa.me/?text=…)."""
    return quote(str(value), safe="")


templates.env.filters["url_query_quote"] = _url_query_quote

ALLOWED_JOB_STATUSES = {"NEW", "SCHEDULED", "IN_PROGRESS", "DONE", "CANCELLED"}

logger = logging.getLogger(__name__)


def _safe_date_slug(raw_date: str | None) -> str | None:
    if not raw_date:
        return None
    value = str(raw_date).strip()
    if len(value) >= 10:
        value = value[:10]
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None


def _build_pdf_download_filename(
    *,
    lead_id: str,
    estimate: dict | None,
    tenant: Tenant,
    db: Session,
) -> str:
    estimate = estimate or {}
    meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}

    raw_ref = (
        meta.get("estimate_id")
        or estimate.get("estimate_id")
        or meta.get("lead_id")
        or lead_id
    )
    ref_slug = ""
    if raw_ref is not None:
        raw_ref_str = str(raw_ref).strip()
        if raw_ref_str:
            ref_slug = slugify(raw_ref_str[-6:])

    company_name = None
    for candidate in (
        estimate.get("branding_company_name"),
        (estimate.get("company") or {}).get("name")
        if isinstance(estimate.get("company"), dict)
        else None,
        getattr(tenant, "company_name", None),
        getattr(tenant, "name", None),
    ):
        if isinstance(candidate, str) and candidate.strip():
            company_name = candidate.strip()
            break
    if not company_name:
        resolved_name, _ = _resolve_company_name_and_tenant(str(tenant.id), db)
        company_name = resolved_name

    company_slug = slugify(company_name or "")
    date_slug = _safe_date_slug(meta.get("date"))

    parts: list[str] = ["offerte"]
    if ref_slug:
        parts.append(ref_slug)
    if company_slug:
        parts.append(company_slug)
    elif date_slug:
        parts.append(date_slug)
    elif not ref_slug and date_slug:
        parts.append(date_slug)

    filename_base = "-".join([p for p in parts if p]).strip("-")
    if not filename_base:
        filename_base = "offerte"
    return f"{filename_base}.pdf"


# -------------------------
# Tenant / UI context helpers
# -------------------------
def _resolve_company_name_and_tenant(
    tenant_id: str,
    db: Session,
) -> tuple[str, Tenant | TenantSettings | None]:
    """
    Resolve tenant settings + human-friendly company name.

    Priority:
    1) tenant.company_name
    2) tenant.name
    3) "Paintly"
    """
    company_name: str | None = None
    source_obj: Tenant | TenantSettings | None = None

    # 1) Try DB Tenant table (authoritative for onboarded accounts)
    try:
        tenant_db = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    except Exception:
        tenant_db = None

    if tenant_db is not None:
        source_obj = tenant_db
        for attr in ("company_name", "name"):
            val = getattr(tenant_db, attr, None)
            if isinstance(val, str) and val.strip():
                company_name = val.strip()
                break

    # 2) Fallback: in-memory TenantSettings (legacy JSON config)
    if company_name is None:
        try:
            ts = tenant_service.get_tenant(tenant_id)
        except Exception:
            ts = None

        if ts is not None:
            if source_obj is None:
                source_obj = ts
            for attr in ("company_name", "name"):
                val = getattr(ts, attr, None)
                if isinstance(val, str) and val.strip():
                    company_name = val.strip()
                    break

    if not company_name:
        company_name = "Aether Engine"

    return company_name, source_obj


def _dashboard_context(
    request: Request,
    current_user: User,
    db: Session,
    extra: dict | None = None,
) -> dict:
    """
    Shared context for all internal Paintly app templates.
    Ensures multi-tenant company branding per request.
    """
    raw_tenant_id = getattr(current_user, "tenant_id", None)
    tenant_id = str(raw_tenant_id) if raw_tenant_id is not None else "default"

    company_name, tenant_obj = _resolve_company_name_and_tenant(tenant_id, db)

    ctx: dict = {
        "request": request,
        "tenant": tenant_obj,
        "company_name": company_name,
        "is_public": False,
    }
    if extra:
        ctx.update(extra)
    return ctx


def _merge_intake_url_into_context(context: dict) -> None:
    """Set ``intake_url`` for the tenant's public intake page (share/copy in app UI)."""
    tenant_obj = context.get("tenant")
    slug = ""
    if tenant_obj is not None:
        raw_slug = getattr(tenant_obj, "slug", None)
        if isinstance(raw_slug, str) and raw_slug.strip():
            slug = raw_slug.strip()
    base = settings.effective_app_base_url
    context["intake_url"] = f"{base}/intake/{slug}" if slug else ""


# -------------------------
# Time & money helpers
# -------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_tz(tz_name: str | None) -> str:
    tz = (tz_name or "").strip()
    if not tz:
        return "Europe/Amsterdam"
    try:
        ZoneInfo(tz)
        return tz
    except Exception:
        return "Europe/Amsterdam"


def _get_tenant_timezone(current_user: User, job: Job | None = None) -> str:
    # 1) Keep display consistent if job already has a stored timezone
    if job is not None:
        existing = getattr(job, "scheduled_tz", None)
        if existing:
            return _safe_tz(str(existing))

    # 2) Tenant/user setting
    return _safe_tz(getattr(current_user, "timezone", None))


def _parse_datetime_local(value: str) -> datetime:
    # HTML <input type="datetime-local"> gives "YYYY-MM-DDTHH:MM"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


def _local_naive_to_utc(dt_local_naive: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    dt_local = dt_local_naive.replace(tzinfo=tz)
    return dt_local.astimezone(timezone.utc)


def _utc_to_local_input(dt_utc: datetime | None, tz_name: str) -> str:
    if not dt_utc:
        return ""
    tz = ZoneInfo(tz_name)
    return dt_utc.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def _utc_to_local_human(dt_utc: datetime | None, tz_name: str) -> str:
    if not dt_utc:
        return ""
    tz = ZoneInfo(tz_name)
    return dt_utc.astimezone(tz).strftime("%b %d, %Y %H:%M")


def _parse_followup_datetime(value: str | None, tz_name: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
        except Exception:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _followup_status_label(next_action_at_utc: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    target_local = next_action_at_utc.astimezone(tz)
    if target_local < now_local:
        return "Te laat"
    if target_local.date() == now_local.date():
        return "Vandaag"
    return "Komt eraan"


def build_followup_summary(overrides: dict, tz_name: str) -> dict:
    next_action = str(overrides.get("next_action") or "").strip()
    next_action_at_raw = str(overrides.get("next_action_at") or "").strip()
    next_action_at_utc = _parse_followup_datetime(next_action_at_raw, tz_name)
    next_action_at_human = _utc_to_local_human(next_action_at_utc, tz_name)
    next_action_at_input = _utc_to_local_input(next_action_at_utc, tz_name)

    is_overdue = False
    if next_action_at_utc is not None:
        is_overdue = next_action_at_utc < _utcnow()

    status_label = ""
    status_code = ""
    if next_action_at_utc is not None:
        status_label = _followup_status_label(next_action_at_utc, tz_name)
        status_code = (
            "overdue"
            if status_label == "Te laat"
            else ("today" if status_label == "Vandaag" else "upcoming")
        )

    return {
        "has_followup": bool(next_action),
        "next_action": next_action,
        "next_action_at_raw": next_action_at_raw,
        "next_action_at_human": next_action_at_human,
        "next_action_at_input": next_action_at_input,
        "is_overdue": is_overdue,
        "status_label": status_label,
        "status_code": status_code,
    }


def _bezichtiging_prefill_from_lead(lead: Lead, intake_payload: dict) -> dict[str, str]:
    """Defaults for Agenda appointment form when scheduling a bezichtiging from a lead."""
    name = (getattr(lead, "name", "") or "").strip() or "Klant"
    email = (getattr(lead, "email", "") or "").strip()
    phone = (getattr(lead, "phone", "") or "").strip()
    lid = str(lead.id)
    lead_short = f"Offerte #{lid[-6:].upper()}"

    street = (intake_payload.get("street") or intake_payload.get("address_street") or "").strip()
    city = (intake_payload.get("city") or intake_payload.get("address_city") or "").strip()
    zip_code = (intake_payload.get("zip") or intake_payload.get("postal_code") or "").strip()
    addr_parts = [p for p in [street, zip_code, city] if p]
    address_line = ", ".join(addr_parts) if addr_parts else ""

    if address_line:
        title = f"Bezichtiging — {address_line} — {name}"
    else:
        title = f"Bezichtiging — {name}"
    if len(title) > 1024:
        title = title[:1021] + "..."

    base = settings.effective_app_base_url.rstrip("/")
    lead_url = f"{base}/app/leads/{lead.id}"

    lines = [
        f"Paintly · {lead_short}",
        f"Klant: {name}",
    ]
    if phone:
        lines.append(f"Telefoon: {phone}")
    if email:
        lines.append(f"E-mail: {email}")
    if address_line:
        lines.append(f"Adres: {address_line}")
    notes = (getattr(lead, "notes", "") or "").strip()
    if notes:
        lines.append("")
        lines.append("Notities:")
        lines.append(notes)
    lines.append("")
    lines.append(f"Lead: {lead_url}")

    description = "\n".join(lines)
    if len(description) > 8000:
        description = description[:7997] + "..."

    return {
        "title": title,
        "description": description,
        "email": email,
        "lead_id": str(lead.id),
        "lead_short": lead_short,
        "customer_name": name,
    }


def collect_dashboard_followups(
    db: Session, tenant_id: str, tz_name: str, *, limit: int = 5
) -> list[dict]:
    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id, Lead.estimate_overrides_json.isnot(None))
        .order_by(desc(Lead.updated_at))
        .limit(250)
        .all()
    )

    now_utc = _utcnow()
    rows: list[dict] = []
    for lead in leads:
        overrides = get_estimate_overrides(lead)
        next_action = str(overrides.get("next_action") or "").strip()
        if not next_action:
            continue
        next_action_at_utc = _parse_followup_datetime(
            str(overrides.get("next_action_at") or ""), tz_name
        )
        if next_action_at_utc is None:
            continue

        rows.append(
            {
                "lead_id": str(lead.id),
                "customer_name": (getattr(lead, "name", "") or "Onbekende klant").strip()
                or "Onbekende klant",
                "next_action": next_action,
                "next_action_at_utc": next_action_at_utc,
                "next_action_at_human": _utc_to_local_human(next_action_at_utc, tz_name),
                "is_overdue": next_action_at_utc < now_utc,
                "status_label": _followup_status_label(next_action_at_utc, tz_name),
                "href": f"/app/leads/{lead.id}",
            }
        )

    overdue = sorted(
        [item for item in rows if item["is_overdue"]],
        key=lambda item: item["next_action_at_utc"],
    )
    upcoming = sorted(
        [item for item in rows if not item["is_overdue"]],
        key=lambda item: item["next_action_at_utc"],
    )
    merged = (overdue + upcoming)[:limit]
    for item in merged:
        item.pop("next_action_at_utc", None)
    return merged


def _safe_decimal(val: object) -> Decimal | None:
    """Best-effort conversion to Decimal without raising."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _fmt_eur(amount: Decimal | None) -> str | None:
    """Simple EUR formatting for internal UI only."""
    if amount is None:
        return None
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Basic European-style formatting: 1 234,56
    s = f"{quantized:,.2f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"€ {s}"


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_lines_to_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for line in str(raw).splitlines():
        cleaned = line.strip()
        if cleaned:
            out.append(cleaned)
    return out


def _normalize_line_item(raw_item: dict, index: int) -> dict | None:
    if not isinstance(raw_item, dict):
        return None

    label = str(raw_item.get("label") or "").strip()
    description = str(raw_item.get("description") or "").strip()
    quantity = _safe_float(raw_item.get("quantity"))
    unit = str(raw_item.get("unit") or "job").strip() or "job"
    unit_price = _safe_float(raw_item.get("unit_price"))
    total_raw = _safe_float(raw_item.get("total"))

    if quantity is None or quantity <= 0:
        quantity = 1.0
    if unit_price is None or unit_price < 0:
        unit_price = 0.0

    computed_total = round(float(quantity) * float(unit_price), 2)
    total = round(total_raw, 2) if total_raw is not None and total_raw >= 0 else computed_total

    if not label and not description and unit_price == 0.0 and total == 0.0:
        return None

    item_code = str(raw_item.get("code") or f"item_{index + 1}").strip() or f"item_{index + 1}"
    category = str(raw_item.get("category") or "labor").strip() or "labor"
    if category not in {"labor", "materials", "other"}:
        category = "labor"

    normalized = {
        "code": item_code,
        "label": label or f"Regel {index + 1}",
        "description": description or None,
        "quantity": float(quantity),
        "unit": unit,
        "unit_price": float(round(unit_price, 2)),
        "total": float(total),
        "category": category,
    }
    return normalized


def _parse_line_items_json(raw_line_items: str | None) -> list[dict]:
    if not raw_line_items:
        return []
    try:
        data = json.loads(raw_line_items)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    items: list[dict] = []
    for idx, item in enumerate(data):
        normalized = _normalize_line_item(item, idx)
        if normalized:
            items.append(normalized)
    return items


def _estimate_editor_initial_values(lead: Lead, overrides: dict) -> dict:
    estimate: dict = {}
    raw_est = getattr(lead, "estimate_json", None)
    if isinstance(raw_est, str) and raw_est.strip():
        try:
            parsed = json.loads(raw_est)
            if isinstance(parsed, dict):
                estimate = parsed
        except Exception:
            estimate = {}

    meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
    customer = estimate.get("customer") if isinstance(estimate.get("customer"), dict) else {}
    company = estimate.get("company") if isinstance(estimate.get("company"), dict) else {}
    totals = estimate.get("totals") if isinstance(estimate.get("totals"), dict) else {}
    subtotals = estimate.get("subtotals") if isinstance(estimate.get("subtotals"), dict) else {}

    line_items = estimate.get("line_items") if isinstance(estimate.get("line_items"), list) else []
    normalized_items: list[dict] = []
    for idx, item in enumerate(line_items):
        normalized = _normalize_line_item(item if isinstance(item, dict) else {}, idx)
        if normalized:
            normalized_items.append(normalized)

    return {
        "customer_name": (customer.get("name") or getattr(lead, "name", "") or "").strip(),
        "customer_email": (customer.get("email") or getattr(lead, "email", "") or "").strip(),
        "customer_phone": (customer.get("phone") or getattr(lead, "phone", "") or "").strip(),
        "project_location": (estimate.get("location") or customer.get("location") or customer.get("address") or estimate.get("address") or meta.get("address") or "").strip(),
        "company_name": (company.get("company_name") or company.get("name") or estimate.get("branding_company_name") or "Paintly").strip(),
        "company_email": (company.get("email") or "").strip(),
        "company_phone": (company.get("phone") or "").strip(),
        "reference": (meta.get("reference") or meta.get("estimate_id") or "").strip(),
        "quote_date": (meta.get("date") or "").strip(),
        "valid_until": (meta.get("valid_until") or "").strip(),
        "title": (meta.get("title") or "Offerte schilderwerk").strip(),
        "subtitle": (meta.get("subtitle") or meta.get("intro") or "").strip(),
        "discount_percent": overrides.get("discount_percent"),
        "manual_total": overrides.get("manual_total"),
        "subtotal_excl": _safe_float(totals.get("pre_tax")),
        "vat_rate_percent": (_safe_float(estimate.get("vat_rate")) or _safe_float(estimate.get("tax_rate")) or 0.21) * 100.0,
        "line_items": normalized_items,
        "included_work": "\n".join(estimate.get("included_work") or meta.get("included_work") or []),
        "excluded_notes": "\n".join(estimate.get("excluded_notes") or meta.get("excluded_notes") or []),
        "public_notes": (estimate.get("public_notes") or overrides.get("public_notes") or "").strip(),
        "labor_subtotal": _safe_float(subtotals.get("labor")) or 0.0,
        "materials_subtotal": _safe_float(subtotals.get("materials")) or 0.0,
    }


def _apply_full_estimate_edit(
    *,
    lead: Lead,
    estimate: dict,
    editor_input: dict,
    overrides: dict,
) -> tuple[dict, dict, list[str]]:
    changed_fields: list[str] = []
    estimate = dict(estimate or {})
    meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
    customer = estimate.get("customer") if isinstance(estimate.get("customer"), dict) else {}
    company = estimate.get("company") if isinstance(estimate.get("company"), dict) else {}

    customer_name = str(editor_input.get("customer_name") or "").strip()
    customer_email = str(editor_input.get("customer_email") or "").strip()
    customer_phone = str(editor_input.get("customer_phone") or "").strip()
    project_location = str(editor_input.get("project_location") or "").strip()

    company_name = str(editor_input.get("company_name") or "").strip() or "Paintly"
    company_email = str(editor_input.get("company_email") or "").strip()
    company_phone = str(editor_input.get("company_phone") or "").strip()

    reference = str(editor_input.get("reference") or "").strip()
    quote_date = str(editor_input.get("quote_date") or "").strip()
    valid_until = str(editor_input.get("valid_until") or "").strip()
    title = str(editor_input.get("title") or "").strip() or "Offerte schilderwerk"
    subtitle = str(editor_input.get("subtitle") or "").strip()

    included_work = _parse_lines_to_list(editor_input.get("included_work"))
    excluded_notes = _parse_lines_to_list(editor_input.get("excluded_notes"))
    public_notes = str(editor_input.get("public_notes") or "").strip()
    line_items = _parse_line_items_json(editor_input.get("line_items_json"))

    discount_percent = _safe_float(editor_input.get("discount_percent"))
    manual_total = _safe_float(editor_input.get("manual_total"))
    subtotal_excl = _safe_float(editor_input.get("subtotal_excl"))
    vat_rate_percent = _safe_float(editor_input.get("vat_rate_percent"))

    if vat_rate_percent is None:
        vat_rate_percent = 21.0
    if vat_rate_percent < 0:
        vat_rate_percent = 0.0
    vat_rate = round(vat_rate_percent / 100.0, 4)

    customer["name"] = customer_name
    customer["email"] = customer_email
    customer["phone"] = customer_phone
    customer["address"] = project_location
    customer["location"] = project_location
    estimate["customer"] = customer
    changed_fields.extend(["customer.name", "customer.email", "customer.phone", "customer.address"])

    company["name"] = company_name
    company["company_name"] = company_name
    company["email"] = company_email
    company["phone"] = company_phone
    estimate["company"] = company
    estimate["branding_company_name"] = company_name
    changed_fields.extend(["company.name", "company.email", "company.phone"])

    estimate["location"] = project_location
    estimate["address"] = project_location
    meta["address"] = project_location

    if reference:
        meta["reference"] = reference
    if quote_date:
        meta["date"] = quote_date
    if valid_until:
        meta["valid_until"] = valid_until
    meta["title"] = title
    meta["subtitle"] = subtitle
    meta["intro"] = subtitle
    changed_fields.extend(["meta.reference", "meta.date", "meta.valid_until", "meta.title", "meta.subtitle"])

    estimate["line_items"] = line_items
    changed_fields.append("line_items")

    labor_subtotal = Decimal("0.00")
    materials_subtotal = Decimal("0.00")
    for item in line_items:
        total_dec = Decimal(str(item.get("total") or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cat = str(item.get("category") or "labor")
        if cat == "materials":
            materials_subtotal += total_dec
        else:
            labor_subtotal += total_dec

    if subtotal_excl is None:
        subtotal_excl_dec = (labor_subtotal + materials_subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        subtotal_excl_dec = Decimal(str(subtotal_excl)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    totals = estimate.get("totals") if isinstance(estimate.get("totals"), dict) else {}
    subtotals = estimate.get("subtotals") if isinstance(estimate.get("subtotals"), dict) else {}
    totals["pre_tax"] = float(subtotal_excl_dec)
    totals["grand_total"] = float(subtotal_excl_dec)
    subtotals["labor"] = float(labor_subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    subtotals["materials"] = float(materials_subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    estimate["totals"] = totals
    estimate["subtotals"] = subtotals
    estimate["vat_rate"] = float(vat_rate)
    estimate["tax_rate"] = float(vat_rate)
    changed_fields.extend(["totals.pre_tax", "totals.grand_total", "subtotals.labor", "subtotals.materials", "vat_rate"])

    estimate["included_work"] = included_work
    estimate["excluded_notes"] = excluded_notes
    estimate["public_notes"] = public_notes
    meta["included_work"] = included_work
    meta["excluded_notes"] = excluded_notes
    meta["public_notes"] = public_notes
    changed_fields.extend(["included_work", "excluded_notes", "public_notes"])

    overrides["public_notes"] = public_notes
    overrides["discount_percent"] = discount_percent if discount_percent is not None else None
    overrides["manual_total"] = manual_total if manual_total is not None else None

    estimate["meta"] = meta

    return estimate, overrides, sorted(set(changed_fields))


def _apply_overrides_to_estimate_dict(estimate: dict, overrides: dict) -> dict:
    """
    Build an override-aware copy of the pricing estimate dict.
    Applies manual_total / discount_percent into totals + meta
    so that rendered HTML reflects the internal override UI.
    """
    estimate = dict(estimate or {})
    pricing = estimate  # render_estimate_html expects pricing at top-level

    overrides = dict(overrides or {})
    manual_total = overrides.get("manual_total")
    discount_percent = overrides.get("discount_percent")

    totals = dict(pricing.get("totals") or {})

    # Base total (incl. VAT) from existing estimate
    base_total_incl = totals.get("grand_total") or totals.get("pre_tax") or 0
    try:
        total_dec = Decimal(str(base_total_incl))
    except Exception:
        total_dec = Decimal("0")

    # Apply discount % if present and no explicit manual_total
    if manual_total is None and discount_percent is not None:
        try:
            disc = Decimal(str(discount_percent))
            if disc > 0:
                if disc > 100:
                    disc = Decimal("100")
                factor = (Decimal("100") - disc) / Decimal("100")
                total_dec = (total_dec * factor).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        except Exception:
            # keep base total on parse errors
            pass

    # If manual_total is provided, it wins over discount_percent
    if manual_total is not None:
        try:
            total_dec = Decimal(str(manual_total)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except Exception:
            # fall back to original total on parse errors
            pass

    # Derive VAT breakdown from total_dec using pricing's vat_rate if present
    vat_rate = pricing.get("vat_rate")
    if vat_rate is None:
        vat_rate = pricing.get("tax_rate")
    try:
        vat_rate_dec = (
            Decimal(str(vat_rate)) if vat_rate is not None else Decimal("0.21")
        )
    except Exception:
        vat_rate_dec = Decimal("0.21")

    if total_dec <= 0:
        # nothing usable → return original estimate untouched
        return estimate

    # Reverse-calc excl VAT + VAT amount from total incl.
    one_plus = Decimal("1") + vat_rate_dec
    subtotal_excl = (total_dec / one_plus).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    vat_amount = (total_dec - subtotal_excl).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    totals["pre_tax"] = float(subtotal_excl)
    totals["grand_total"] = float(total_dec)
    pricing["totals"] = totals

    # Surface overrides + explicit override_total_incl_vat in meta
    meta = dict(pricing.get("meta") or {})
    meta["overrides"] = overrides
    meta["override_total_incl_vat"] = float(total_dec)

    # If a manual total or discount was applied, treat this estimate as
    # manually finalized: clear AI review flags so the public quote shows
    # a concrete price instead of "review required"/"nader te bepalen".
    if manual_total is not None or discount_percent is not None:
        pricing["needs_review"] = False
        meta["needs_review"] = False
        meta["needs_review_reasons"] = []
        meta["review_reasons"] = []
        if isinstance(pricing.get("review_reasons"), list):
            pricing["review_reasons"] = []

    pricing["meta"] = meta

    # Debug log adjusted totals for verification
    logger.info(
        "APPLY_OVERRIDES_RESULT overrides=%r totals=%r meta_total=%r",
        overrides,
        totals,
        meta.get("override_total_incl_vat"),
    )

    return pricing


def render_quote_html_for_lead(lead: Lead, estimate: dict, overrides: dict) -> tuple[str | None, bool]:
    """
    Helper used after saving manual overrides.
    Re-renders estimate HTML from lead.estimate_json + overrides,
    writes it to storage and returns the new html_key.
    """
    from app.verticals.paintly.render_estimate import render_estimate_html

    if not isinstance(estimate, dict) or not estimate:
        logger.warning(
            "RENDER_QUOTE_HTML_FOR_LEAD_SKIPPED_INVALID_ESTIMATE lead_id=%s",
            getattr(lead, "id", None),
        )
        return None, False

    logger.info(
        "RENDER_QUOTE_HTML_FOR_LEAD_CALLED lead_id=%s old_html_key=%r",
        getattr(lead, "id", None),
        getattr(lead, "estimate_html_key", None),
    )

    # Apply overrides into pricing totals
    estimate_with_overrides = _apply_overrides_to_estimate_dict(
        estimate, overrides
    )

    logger.info(
        "RENDER_QUOTE_HTML_FOR_LEAD_AFTER_APPLY lead_id=%s totals=%r meta=%r",
        getattr(lead, "id", None),
        (estimate_with_overrides.get("totals") or {}),
        (estimate_with_overrides.get("meta") or {}),
    )

    # Render fresh HTML
    html = render_estimate_html(estimate_with_overrides)

    storage = get_storage()
    today = dt.date.today().isoformat()
    filename = f"estimate_{lead.id}_{uuid.uuid4().hex}.html"
    new_key = f"leads/{lead.id}/estimates/{today}/{filename}"

    storage.save_bytes(
        tenant_id=str(lead.tenant_id),
        key=new_key,
        data=html.encode("utf-8"),
        content_type="text/html; charset=utf-8",
    )

    logger.info(
        "RENDER_QUOTE_HTML_FOR_LEAD_DONE lead_id=%s old_html_key=%r new_html_key=%r",
        getattr(lead, "id", None),
        getattr(lead, "estimate_html_key", None),
        new_key,
    )

    return new_key, True


def rerender_stored_estimate_html_from_json(db: Session, lead: Lead) -> tuple[bool, str | None]:
    """
    Re-run estimate.html (Jinja) from persisted lead.estimate_json + estimate_overrides.

    Does not recompute vision/pricing (no pipeline). Use after template/CSS changes so the
    blob at estimate_html_key matches current render_estimate_html output.
    """
    raw_est = getattr(lead, "estimate_json", None)
    if not isinstance(raw_est, str) or not raw_est.strip():
        return False, "missing_estimate_json"
    try:
        estimate_dict = json.loads(raw_est)
    except Exception:
        return False, "estimate_json_parse_error"
    if not isinstance(estimate_dict, dict) or not estimate_dict:
        return False, "empty_estimate_json"

    overrides = get_estimate_overrides(lead)
    before_key = (getattr(lead, "estimate_html_key", None) or "").strip() or None
    new_key, rendered = render_quote_html_for_lead(lead, estimate_dict, overrides)
    if not rendered or not new_key:
        return False, "render_failed"

    lead.estimate_html_key = new_key
    lead.updated_at = _utcnow()
    db.add(lead)
    db.commit()
    logger.info(
        "ESTIMATE_HTML_RERENDER_FROM_JSON lead_id=%s tenant_id=%s html_key_before=%r html_key_after=%r",
        getattr(lead, "id", None),
        str(getattr(lead, "tenant_id", "")),
        before_key,
        new_key,
    )
    return True, None


def get_estimate_overrides(lead: Lead) -> dict:
    """
    Safely parse estimate_overrides_json from a Lead.
    Never raises; returns {} on any error or missing payload.
    """
    raw = getattr(lead, "estimate_overrides_json", None)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def get_effective_total(lead: Lead) -> Decimal | None:
    """
    Compute override-aware total (incl. VAT) for internal display:
    - If overrides.manual_total present and valid -> use that.
    - Else if overrides.discount_percent present -> apply to base total_incl_vat from estimate_json.
    - Else fall back to base total_incl_vat from estimate_json.
    - Returns None if no usable total.
    """
    overrides = get_estimate_overrides(lead)

    manual_total = _safe_decimal(overrides.get("manual_total"))
    if manual_total is not None:
        return manual_total

    # Parse estimate_json for base total
    base_total: Decimal | None = None
    raw_est = getattr(lead, "estimate_json", None)
    if raw_est:
        try:
            est = json.loads(raw_est)
            if isinstance(est, dict):
                # canonical path used by paintly render_estimate: pricing.meta.vat.total_incl_vat
                totals = est.get("totals") or {}
                vat_block = est.get("vat") or {}
                # prefer vat.total_incl_vat if present, else totals.grand_total, else totals.pre_tax
                for candidate in [
                    vat_block.get("total_incl_vat"),
                    totals.get("grand_total"),
                    totals.get("pre_tax"),
                ]:
                    base_total = _safe_decimal(candidate)
                    if base_total is not None:
                        break
        except Exception:
            base_total = None

    if base_total is None:
        return None

    discount = overrides.get("discount_percent")
    discount_dec = _safe_decimal(discount)
    if discount_dec is None:
        return base_total

    if discount_dec <= 0:
        return base_total

    # Cap at 100% to avoid negative totals
    if discount_dec > 100:
        discount_dec = Decimal("100")

    factor = (Decimal("100") - discount_dec) / Decimal("100")
    return (base_total * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# -------------------------
# Dev helper (optional)
# -------------------------
@router.post("/dev/set_timezone")
def dev_set_timezone(
    tz: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    tz = (tz or "").strip()
    try:
        ZoneInfo(tz)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    current_user.timezone = tz
    db.add(current_user)
    db.commit()
    return RedirectResponse(url="/app/dashboard", status_code=303)


# -------------------------
# Lead status helpers
# -------------------------
def derive_status(lead: Lead) -> str:
    s = (getattr(lead, "status", "") or "").upper()
    if s in {"SENT", "VIEWED", "ACCEPTED", "REJECTED"}:
        return s

    if getattr(lead, "needs_review_hard", False):
        return "NEEDS_REVIEW"
    if getattr(lead, "pricing_ready", False):
        return "SUCCEEDED"
    return "RUNNING"


def public_url_for(request: Request, lead: Lead) -> str | None:
    token = getattr(lead, "public_token", None)
    if not token:
        return None
    return f"{request.base_url}e/{token}"


def compute_next_action(lead: Lead, job: Job | None) -> dict:
    lead_status = derive_status(lead)
    has_estimate = bool(getattr(lead, "estimate_html_key", None))
    has_public = bool(getattr(lead, "public_token", None))

    if not has_estimate:
        return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}

    # Alleen SUCCEEDED mag verstuurd worden; NEEDS_REVIEW blokkeert send.
    if lead_status == "SUCCEEDED":
        return {
            "label": "Send estimate",
            "href": f"/app/leads/{lead.id}/send",
            "method": "POST",
        }

    if lead_status == "SENT":
        return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}

    if lead_status == "VIEWED":
        return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}

    if lead_status == "ACCEPTED":
        if not job:
            return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}
        js = (job.status or "").upper()
        if js in {"NEW", "SCHEDULED", "IN_PROGRESS"}:
            return {"label": "Update job", "href": f"/app/leads/{lead.id}#job"}
        return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}

    return {"label": "Bekijk offerte", "href": f"/app/leads/{lead.id}"}


# -------------------------
# App routes
# -------------------------
@router.get("", include_in_schema=False)
def app_root():
    return RedirectResponse(url="/app/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
def app_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant_id = str(current_user.tenant_id)
    job_counts = dict(
        db.query(Job.status, func.count(Job.id))
        .filter(Job.tenant_id == tenant_id)
        .group_by(Job.status)
        .all()
    )

    kpis = {s: job_counts.get(s, 0) for s in ALLOWED_JOB_STATUSES}

    jobs = (
        db.query(Job)
        .filter(Job.tenant_id == tenant_id)
        .order_by(desc(getattr(Job, "updated_at", Job.id)))
        .limit(25)
        .all()
    )

    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id)
        .order_by(desc(Lead.created_at))
        .limit(40)
        .all()
    )

    jobs_vm = [{"id": j.id, "status": j.status, "lead_id": j.lead_id} for j in jobs]
    leads_vm = [
        {"id": l.id, "name": getattr(l, "name", ""), "status": derive_status(l)}
        for l in leads
    ]

    followups = collect_dashboard_followups(
        db,
        tenant_id,
        _get_tenant_timezone(current_user, None),
        limit=12,
    )

    def _lead_status_ui(raw_status: str) -> tuple[str, str]:
        st = (raw_status or "").upper()
        if st == "SENT":
            return "Verstuurd", "bg-amber-50 text-amber-700"
        if st == "VIEWED":
            return "Bekeken", "bg-sky-50 text-sky-700"
        if st == "SUCCEEDED":
            return "Klaar om te versturen", "bg-indigo-50 text-indigo-700"
        if st == "NEEDS_REVIEW":
            return "Review nodig", "bg-rose-50 text-rose-700"
        if st == "RUNNING":
            return "Wordt voorbereid", "bg-slate-100 text-slate-700"
        if st == "NEW":
            return "Nieuw", "bg-slate-100 text-slate-700"
        return st.title() if st else "Nieuw", "bg-slate-100 text-slate-700"

    open_statuses = {"NEW", "RUNNING", "SUCCEEDED", "SENT", "VIEWED", "NEEDS_REVIEW"}
    open_quotes: list[dict] = []
    for lead in leads:
        raw_status = derive_status(lead)
        if raw_status not in open_statuses:
            continue
        status_label, status_badge = _lead_status_ui(raw_status)
        total_display = _fmt_eur(get_effective_total(lead)) or "Nog niet berekend"
        open_quotes.append(
            {
                "id": lead.id,
                "customer_name": (getattr(lead, "name", "") or "Onbekende klant").strip()
                or "Onbekende klant",
                "status_label": status_label,
                "status_badge": status_badge,
                "total_display": total_display,
            }
        )
    open_quotes = open_quotes[:20]

    tenant = db.query(Tenant).filter(Tenant.id == str(current_user.tenant_id)).first()
    pricing = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant is not None else {}
    wall_rate_value = pricing.get("walls_rate_eur_per_sqm")
    missing_wall_rate = wall_rate_value in (None, "")
    billing_usage_summary = (
        get_billing_usage_summary(db, tenant) if tenant is not None else None
    )

    current_plan_code = getattr(tenant, "plan_code", None) if tenant is not None else None
    current_plan_code = current_plan_code or DEFAULT_PLAN_CODE

    subscription_status = (
        getattr(tenant, "subscription_status", None) if tenant is not None else None
    )
    subscription_status = subscription_status or "inactive"

    trial_ends_at = getattr(tenant, "trial_ends_at", None) if tenant is not None else None
    trial_days_left: int | None
    if not trial_ends_at:
        trial_days_left = None
    else:
        from datetime import datetime, timezone

        if getattr(trial_ends_at, "tzinfo", None) is None:
            trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = trial_ends_at - now
        trial_days_left = max(int(delta.days), 0)

    usage = get_or_create_usage(db, str(current_user.tenant_id))
    quotes_sent_this_month = int(getattr(usage, "quotes_sent", 0) or 0)

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "kpis": kpis,
            "jobs": jobs_vm,
            "leads": leads_vm,
            "billing_usage_summary": billing_usage_summary,
            "current_plan_code": current_plan_code,
            "subscription_status": subscription_status,
            "trial_ends_at": trial_ends_at,
            "trial_days_left": trial_days_left,
            "quotes_sent_this_month": quotes_sent_this_month,
            "feature_flags": tenant_feature_flags(tenant),
            "features": tenant_feature_ui(tenant),
            "entitlements": tenant_entitlements(tenant),
            "tenant_id": tenant_id,
            "followups": followups,
            "open_quotes": open_quotes,
            "missing_wall_rate": missing_wall_rate,
            "current_wall_rate": wall_rate_value,
        },
    )
    _merge_intake_url_into_context(context)
    return templates.TemplateResponse("app/dashboard.html", context)


@router.get("/settings", response_class=HTMLResponse)
def app_settings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(current_user.tenant_id))
        .first()
    )
    pricing = dict(getattr(tenant, "pricing_json", {}) or {})
    google_connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == str(current_user.tenant_id),
            CalendarConnection.provider == "google",
        )
        .first()
    )
    price_per_m2 = pricing.get("price_per_m2", pricing.get("walls_rate_eur_per_sqm"))
    minimum_price = pricing.get("minimum_prijs", pricing.get("minimum_price_eur"))
    travel_cost = pricing.get("voorrijkosten", pricing.get("travel_cost_eur"))
    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "user": current_user,
            "tenant": tenant,
            "account_name": (getattr(tenant, "company_name", None) or ""),
            "account_email": (getattr(current_user, "email", None) or ""),
            "price_per_m2": "" if price_per_m2 is None else str(price_per_m2),
            "minimum_price": "" if minimum_price is None else str(minimum_price),
            "travel_cost": "" if travel_cost is None else str(travel_cost),
            "saved": (request.query_params.get("saved") or "").strip(),
            "google_calendar_connected": bool(google_connection),
            "google_calendar_id": (
                google_connection.calendar_id if google_connection else "primary"
            ),
        },
    )
    return templates.TemplateResponse("app/settings.html", context)


class ScheduleAppointmentBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=1024)
    start_datetime: datetime
    end_datetime: datetime
    description: str | None = Field(None, max_length=8000)
    attendee_emails: list[EmailStr] | None = Field(None, max_length=10)
    quote_id: str | None = Field(None, max_length=100)


@router.post("/calendar/appointments")
def schedule_paintly_appointment(
    body: ScheduleAppointmentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    tenant_id = str(current_user.tenant_id)
    start_utc = utc_normalize_appointment_datetime(body.start_datetime)
    end_utc = utc_normalize_appointment_datetime(body.end_datetime)
    if end_utc <= start_utc:
        raise HTTPException(
            status_code=400,
            detail="end_datetime must be after start_datetime",
        )
    attendees = [str(e) for e in body.attendee_emails] if body.attendee_emails else None
    event_payload = build_appointment_event_payload(
        title=body.title,
        start_utc=start_utc,
        end_utc=end_utc,
        description=body.description,
        attendee_emails=attendees,
    )
    send_updates = "none" if attendees else None
    event = create_google_calendar_event_for_tenant(
        db=db,
        tenant_id=tenant_id,
        event_payload=event_payload,
        send_updates=send_updates,
    )
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        raise HTTPException(status_code=400, detail="Google Calendar event missing id.")
    html_link = event.get("htmlLink")
    html_link_str = html_link if isinstance(html_link, str) else None
    qid = (body.quote_id or "").strip() or None
    if qid:
        lead_ok = (
            db.query(Lead.id)
            .filter(Lead.id == qid, Lead.tenant_id == tenant_id)
            .first()
        )
        if not lead_ok:
            raise HTTPException(status_code=400, detail="Invalid quote_id for this tenant.")
    row = CalendarEvent(
        tenant_id=tenant_id,
        google_event_id=event_id,
        title=body.title.strip(),
        start_datetime=start_utc,
        end_datetime=end_utc,
        html_link=html_link_str,
        quote_id=qid,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {
        "ok": True,
        "event_id": event_id,
        "html_link": html_link_str,
    }


@router.get("/calendar/upcoming-events")
def get_calendar_upcoming_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    days: int = Query(default=30, ge=1, le=90),
):
    tenant_id = str(current_user.tenant_id)
    tz_name = _get_tenant_timezone(current_user, None)
    items = fetch_upcoming_calendar_events_merged(
        db,
        tenant_id,
        tz_name=tz_name,
        days_ahead=days,
        max_results=25,
    )
    return {"items": items}


@router.post("/settings")
async def app_settings_save(
    request: Request,
    section: str = Form(...),
    company_name: str | None = Form(None),
    account_name: str | None = Form(None),
    account_email: str | None = Form(None),
    logo_file: UploadFile | None = File(None),
    price_per_m2: str | None = Form(None),
    minimum_price: str | None = Form(None),
    travel_cost: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    def _parse_money(raw: str | None) -> float | None:
        if raw is None:
            return None
        value = raw.strip().replace(",", ".")
        if not value:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed < 0:
            return None
        return round(parsed, 2)

    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(current_user.tenant_id))
        .first()
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if section == "account":
        logger.info(
            "SETTINGS_ACCOUNT_SAVE_START tenant_id=%s user_id=%s company_name_present=%s logo_filename=%s logo_content_type=%s",
            str(current_user.tenant_id),
            str(getattr(current_user, "id", "")),
            bool((company_name or account_name or "").strip()),
            (logo_file.filename if logo_file is not None else None),
            (logo_file.content_type if logo_file is not None else None),
        )
        resolved_company_name = company_name
        if resolved_company_name is None:
            # Backward compatibility with older template field name.
            resolved_company_name = account_name

        if resolved_company_name is not None:
            cleaned_company_name = resolved_company_name.strip()
            current_user.company_name = cleaned_company_name
            tenant.company_name = cleaned_company_name

        if account_email is not None and account_email.strip():
            current_user.email = account_email.strip()

        if logo_file is not None and (logo_file.filename or "").strip():
            content_type = (logo_file.content_type or "").strip().lower()
            if content_type in {"image/png", "image/jpeg"}:
                payload = await logo_file.read()
                if payload:
                    ext = ".png" if content_type == "image/png" else ".jpg"
                    safe_name = os.path.basename(logo_file.filename or f"logo{ext}")
                    day = datetime.now(timezone.utc).date().isoformat()
                    key = f"settings/logos/{day}/{uuid.uuid4().hex}_{safe_name}"
                    storage = get_storage()
                    storage.save_bytes(
                        tenant_id=str(current_user.tenant_id),
                        key=key,
                        data=payload,
                        content_type=content_type,
                    )
                    current_user.logo_url = storage.public_url(
                        tenant_id=str(current_user.tenant_id),
                        key=key,
                    )
                    logger.info(
                        "SETTINGS_ACCOUNT_LOGO_SAVED tenant_id=%s user_id=%s logo_url=%s",
                        str(current_user.tenant_id),
                        str(getattr(current_user, "id", "")),
                        current_user.logo_url,
                    )
            else:
                logger.warning(
                    "SETTINGS_ACCOUNT_LOGO_SKIPPED_UNSUPPORTED_TYPE tenant_id=%s user_id=%s content_type=%s",
                    str(current_user.tenant_id),
                    str(getattr(current_user, "id", "")),
                    content_type,
                )

        # Refresh stored quote HTML for recent tenant leads so public pages show
        # updated branding (company name/logo) without manual intervention.
        refreshed_count = 0
        refreshed_failed = 0
        leads_to_refresh = (
            db.query(Lead)
            .filter(
                Lead.tenant_id == str(current_user.tenant_id),
                Lead.public_token.isnot(None),
                Lead.estimate_html_key.isnot(None),
                Lead.estimate_json.isnot(None),
            )
            .order_by(Lead.updated_at.desc())
            .limit(20)
            .all()
        )
        logger.info(
            "SETTINGS_ACCOUNT_REFRESH_QUOTES_START tenant_id=%s lead_count=%s",
            str(current_user.tenant_id),
            len(leads_to_refresh),
        )
        for tenant_lead in leads_to_refresh:
            try:
                from app.verticals.paintly.pipeline import compute_quote_for_lead

                before_html_key = (getattr(tenant_lead, "estimate_html_key", None) or "").strip()
                result = compute_quote_for_lead(db=db, lead=tenant_lead, render_html=True)
                estimate_json = result.get("estimate_json")
                after_html_key = (result.get("estimate_html_key") or "").strip()
                branding_company_name = None
                branding_logo_url = None
                if isinstance(estimate_json, dict):
                    company = estimate_json.get("company") if isinstance(estimate_json.get("company"), dict) else {}
                    branding_company_name = (
                        estimate_json.get("branding_company_name")
                        or company.get("company_name")
                        or company.get("name")
                    )
                    branding_logo_url = (
                        estimate_json.get("branding_logo_url")
                        or company.get("logo_url")
                    )

                if estimate_json is not None:
                    tenant_lead.estimate_json = json.dumps(estimate_json, ensure_ascii=False)
                if after_html_key:
                    tenant_lead.estimate_html_key = after_html_key
                tenant_lead.updated_at = _utcnow()
                db.add(tenant_lead)
                refreshed_count += 1
                logger.info(
                    "SETTINGS_ACCOUNT_REFRESH_QUOTE_OK tenant_id=%s lead_id=%s html_key_before=%r html_key_after=%r branding_company_name=%r branding_logo_url=%r",
                    str(current_user.tenant_id),
                    str(getattr(tenant_lead, "id", "")),
                    before_html_key or None,
                    after_html_key or None,
                    branding_company_name,
                    branding_logo_url,
                )
            except Exception:
                refreshed_failed += 1
                logger.exception(
                    "SETTINGS_ACCOUNT_REFRESH_QUOTE_FAILED tenant_id=%s lead_id=%s",
                    str(current_user.tenant_id),
                    str(getattr(tenant_lead, "id", "")),
                )
        logger.info(
            "SETTINGS_ACCOUNT_REFRESH_QUOTES_DONE tenant_id=%s refreshed=%s failed=%s",
            str(current_user.tenant_id),
            refreshed_count,
            refreshed_failed,
        )
    elif section == "pricing":
        pricing = dict(getattr(tenant, "pricing_json", {}) or {})
        parsed_price_per_m2 = _parse_money(price_per_m2)
        parsed_minimum_price = _parse_money(minimum_price)
        parsed_travel_cost = _parse_money(travel_cost)

        pricing["price_per_m2"] = parsed_price_per_m2
        pricing["minimum_prijs"] = parsed_minimum_price
        pricing["voorrijkosten"] = parsed_travel_cost

        # keep existing pricing key used elsewhere in the app
        pricing["walls_rate_eur_per_sqm"] = parsed_price_per_m2
        pricing["minimum_price_eur"] = parsed_minimum_price
        pricing["travel_cost_eur"] = parsed_travel_cost
        tenant.pricing_json = pricing

    db.add(tenant)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    saved_section = section if section in {"account", "pricing"} else "1"
    return RedirectResponse(url=f"/app/settings?saved={saved_section}", status_code=303)


@router.get("/billing", response_class=HTMLResponse)
def app_billing(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    send_error = (request.query_params.get("send_error") or "").strip()
    billing_status_error = send_error == "billing_status"
    portal_error = (request.query_params.get("portal_error") or "").strip()
    portal_error_no_customer = portal_error == "no_customer"

    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(current_user.tenant_id))
        .first()
    )

    current_plan_code = (
        getattr(tenant, "plan_code", None) if tenant is not None else None
    )
    current_plan_code = current_plan_code or DEFAULT_PLAN_CODE

    subscription_status = (
        getattr(tenant, "subscription_status", None) if tenant is not None else None
    )
    subscription_status = subscription_status or "inactive"

    trial_ends_at = getattr(tenant, "trial_ends_at", None) if tenant is not None else None

    trial_days_left: int | None
    if not trial_ends_at:
        trial_days_left = None
    else:
        from datetime import datetime, timezone

        if getattr(trial_ends_at, "tzinfo", None) is None:
            trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = trial_ends_at - now
        trial_days_left = max(int(delta.days), 0)

    is_paid_or_trialing = subscription_status in ("trialing", "active")

    current_plan_item = get_plan_item(current_plan_code) or PLAN_CATALOG[DEFAULT_PLAN_CODE]
    _plan_i18n_keys = {
        "starter_99": "starter",
        "pro_199": "pro",
        "business_399": "business",
    }
    request_lang = resolve_language(request)
    current_plan_price_label = (
        f"{current_plan_item.price_display} {translate('billing.price_period_monthly', lang=request_lang)}".strip()
    )
    current_plan_i18n_key = _plan_i18n_keys.get(current_plan_item.code, "starter")
    current_plan_name = translate(
        f"billing.plan.{current_plan_i18n_key}.name", lang=request_lang
    )
    billing_offer_usage = (
        get_billing_offer_usage_view(db, tenant, lang=request_lang)
        if tenant is not None
        else None
    )

    trial_ends_at_display: str | None = None
    if trial_ends_at is not None:
        te = trial_ends_at
        if getattr(te, "tzinfo", None) is None:
            te = te.replace(tzinfo=timezone.utc)
        trial_ends_at_display = te.astimezone(ZoneInfo("Europe/Amsterdam")).strftime(
            "%d-%m-%Y"
        )

    subscription_status_label = {
        "trialing": translate("billing.status.trialing", lang=request_lang),
        "active": translate("billing.status.active", lang=request_lang),
        "inactive": translate("billing.status.inactive", lang=request_lang),
        "past_due": translate("billing.status.past_due", lang=request_lang),
        "canceled": translate("billing.status.canceled", lang=request_lang),
        "unpaid": translate("billing.status.unpaid", lang=request_lang),
    }.get(
        subscription_status,
        subscription_status.replace("_", " ").title(),
    )

    plans = [
        {
            "code": item.code,
            "name": translate(
                f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.name",
                lang=request_lang,
            ),
            "price_display": item.price_display,
            "price_period": translate("billing.price_period_monthly", lang=request_lang),
            "quote_limit_label": translate(
                f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.limit_label",
                lang=request_lang,
            ),
            "features": [
                translate(
                    f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.features.f1",
                    lang=request_lang,
                ),
                translate(
                    f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.features.f2",
                    lang=request_lang,
                ),
                translate(
                    f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.features.f3",
                    lang=request_lang,
                ),
            ],
            "tagline": translate(
                f"billing.plan.{_plan_i18n_keys.get(item.code, 'starter')}.subtitle",
                lang=request_lang,
            ),
            "is_recommended": item.code == "pro_199",
            "cta_label": {
                "starter_99": translate("billing.cta.choose_starter", lang=request_lang),
                "pro_199": translate("billing.cta.choose_pro", lang=request_lang),
                "business_399": translate("billing.cta.choose_business", lang=request_lang),
            }[item.code],
        }
        for item in (PLAN_CATALOG[c] for c in CANONICAL_PLAN_CODES)
    ]

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "title": translate("billing.title", lang=request_lang),
            "plans": plans,
            "current_plan_code": current_plan_code,
            "current_plan_name": current_plan_name,
            "current_plan_price_label": current_plan_price_label,
            "subscription_status": subscription_status,
            "subscription_status_label": subscription_status_label,
            "trial_ends_at": trial_ends_at,
            "trial_ends_at_display": trial_ends_at_display,
            "trial_days_left": trial_days_left,
            "is_paid_or_trialing": is_paid_or_trialing,
            "billing_status_error": billing_status_error,
            "portal_error_no_customer": portal_error_no_customer,
            "billing_offer_usage": billing_offer_usage,
            "feature_flags": tenant_feature_flags(tenant),
            "features": tenant_feature_ui(tenant),
        },
    )
    return templates.TemplateResponse("app/billing.html", context)


@router.post("/billing/portal")
def app_billing_portal(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == current_user.tenant_id)
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    customer_id = getattr(tenant, "stripe_customer_id", None)
    if not customer_id:
        raise HTTPException(status_code=400, detail="no_customer")

    try:
        ensure_stripe_api_key()
        base = (os.getenv("APP_BASE_URL") or settings.APP_PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base}/app/billing",
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Stripe error during Billing Portal session creation",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stripe configuration error",
        ) from exc

    return {"portal_url": session.url}


@router.post("/billing/upgrade/{plan_code}")
def app_billing_upgrade(
    plan_code: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == current_user.tenant_id)
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    current_plan_code = getattr(tenant, "plan_code", None)
    available_mapping_keys = sorted(PLAN_CATALOG.keys())
    resolved_plan_code, price_id = get_stripe_price_id(plan_code)
    price_id_masked = None if not price_id else f"...{price_id[-6:]}"
    logger.info(
        "billing_upgrade_validation tenant_id=%s current_plan_code=%s requested_plan_code=%s available_mapping_keys=%s price_id_found=%s price_id_masked=%s",
        str(tenant.id),
        current_plan_code,
        plan_code,
        available_mapping_keys,
        bool(price_id),
        price_id_masked,
    )
    if not resolved_plan_code:
        logger.warning(
            "billing_upgrade_validation_failed tenant_id=%s current_plan_code=%s requested_plan_code=%s available_mapping_keys=%s price_id_found=%s reason=%s",
            str(tenant.id),
            current_plan_code,
            plan_code,
            available_mapping_keys,
            bool(price_id),
            "unknown_plan_code",
        )
        raise HTTPException(status_code=400, detail="Invalid or unavailable plan code")
    if not price_id:
        logger.error(
            "billing_upgrade_validation_failed tenant_id=%s current_plan_code=%s requested_plan_code=%s resolved_plan_code=%s available_mapping_keys=%s price_id_found=%s reason=%s",
            str(tenant.id),
            current_plan_code,
            plan_code,
            resolved_plan_code,
            available_mapping_keys,
            False,
            "missing_stripe_price_id_mapping",
        )
        raise HTTPException(status_code=400, detail="Invalid or unavailable plan code")

    try:
        ensure_stripe_api_key()
        base = (
            os.getenv("APP_BASE_URL")
            or settings.APP_PUBLIC_BASE_URL
            or str(request.base_url)
        ).rstrip("/")

        # Existing subscribers must be updated in place. Creating a new subscription
        # here can unintentionally grant a fresh trial period.
        if tenant.stripe_subscription_id:
            subscription = stripe.Subscription.retrieve(
                tenant.stripe_subscription_id,
                expand=["items.data"],
            )
            items = getattr(getattr(subscription, "items", None), "data", []) or []
            if not items:
                raise HTTPException(
                    status_code=400,
                    detail="Stripe subscription has no items to update",
                )
            subscription_item_id = items[0].id

            updated_subscription = stripe.Subscription.modify(
                tenant.stripe_subscription_id,
                items=[{"id": subscription_item_id, "price": price_id}],
                proration_behavior="create_prorations",
                metadata={
                    "tenant_id": str(tenant.id),
                    "plan_code": resolved_plan_code,
                },
            )

            tenant.plan_code = resolved_plan_code
            tenant.subscription_status = (
                getattr(updated_subscription, "status", None) or tenant.subscription_status
            )
            db.add(tenant)
            db.commit()

            return {"redirect_url": f"{base}/app/billing?checkout=success"}

        has_used_trial = tenant.trial_ends_at is not None
        customer_has_subscription = False
        if tenant.stripe_customer_id:
            existing_subs = stripe.Subscription.list(
                customer=tenant.stripe_customer_id,
                status="all",
                limit=1,
            )
            customer_has_subscription = bool(getattr(existing_subs, "data", None))

        allow_trial = (not has_used_trial) and (not customer_has_subscription)

        subscription_data = {
            "metadata": {
                "tenant_id": str(tenant.id),
                "plan_code": resolved_plan_code,
            }
        }
        if allow_trial:
            subscription_data["trial_period_days"] = 14

        checkout_payload: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{base}/app/billing?checkout=success",
            "cancel_url": f"{base}/app/billing?checkout=cancel",
            "client_reference_id": str(tenant.id),
            "metadata": {
                "tenant_id": str(tenant.id),
                "target_plan_code": resolved_plan_code,
            },
            "subscription_data": subscription_data,
        }
        if tenant.stripe_customer_id:
            checkout_payload["customer"] = tenant.stripe_customer_id

        session = stripe.checkout.Session.create(**checkout_payload)
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Stripe error during Checkout session creation",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stripe configuration error",
        ) from exc

    return {"checkout_url": session.url}


@router.get("/leads", response_class=HTMLResponse)
def app_leads(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == str(current_user.tenant_id))
        .order_by(desc(Lead.created_at))
        .limit(100)
        .all()
    )

    # MVP: 1 query per lead OK. Later optimize with join.
    rows = []
    for lead in leads:
        job = (
            db.query(Job)
            .filter(
                Job.lead_id == lead.id, Job.tenant_id == str(current_user.tenant_id)
            )
            .first()
        )
        rows.append(
            {
                "id": lead.id,
                "customer_name": getattr(lead, "name", "") or "—",
                "address": "",
                "status": derive_status(lead),
                "estimate_html_key": getattr(lead, "estimate_html_key", None),
                "public_url": public_url_for(request, lead),
                "next_action": compute_next_action(lead, job),
                "total": getattr(lead, "total", None),
            }
        )

    context = _dashboard_context(
        request,
        current_user,
        db,
        {"leads": rows},
    )
    _merge_intake_url_into_context(context)
    return templates.TemplateResponse("app/leads_list.html", context)


@router.get("/leads/{lead_id}", response_class=HTMLResponse)
def app_lead_detail(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    lang = resolve_language(request)
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        logger.warning("SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=lead_not_found", lead_id)
        raise HTTPException(status_code=404, detail="Lead not found")

    intake_payload_dict = {}

    if lead.intake_payload:
        try:
            intake_payload_dict = json.loads(lead.intake_payload)
        except Exception:
            intake_payload_dict = {}

    # Manual estimate overrides (internal-only)
    overrides = get_estimate_overrides(lead)
    effective_total = get_effective_total(lead)
    effective_total_display = _fmt_eur(effective_total) if effective_total is not None else None

    job = (
        db.query(Job)
        .filter(Job.lead_id == lead.id, Job.tenant_id == str(current_user.tenant_id))
        .first()
    )

    tz_name = _get_tenant_timezone(current_user, job)

    scheduled_input_value = (
        _utc_to_local_input(getattr(job, "scheduled_at", None), tz_name) if job else ""
    )
    scheduled_display = (
        _utc_to_local_human(getattr(job, "scheduled_at", None), tz_name) if job else ""
    )

    started_display = (
        _utc_to_local_human(getattr(job, "started_at", None), tz_name) if job else ""
    )
    done_display = (
        _utc_to_local_human(getattr(job, "done_at", None), tz_name) if job else ""
    )
    sent_display = _utc_to_local_human(getattr(lead, "sent_at", None), tz_name)
    lead_scheduled_start_display = _utc_to_local_human(
        getattr(lead, "scheduled_start", None), tz_name
    )
    lead_scheduled_end_display = _utc_to_local_human(
        getattr(lead, "scheduled_end", None), tz_name
    )

    # -------------------------
    # Photo previews (MVP)
    # -------------------------
    photo_previews: list[dict] = []
    try:
        uploads = (
            db.query(UploadRecord)
            .filter(
                UploadRecord.tenant_id == lead.tenant_id,
                UploadRecord.lead_id == lead.id,
                UploadRecord.status.in_([UploadStatus.uploaded, "uploaded"]),
            )
            .order_by(UploadRecord.id.desc())
            .all()
        )

        storage = get_storage()

        for u in uploads:
            # alleen afbeeldingen tonen
            if hasattr(u, "is_image") and not u.is_image:
                continue

            object_key = (getattr(u, "object_key", "") or "").strip()
            if not object_key:
                continue

            # object_key staat meestal als "<tenant_id>/..."; storage verwacht key zonder tenant prefix
            tenant_prefix = f"{lead.tenant_id}/"
            key = (
                object_key[len(tenant_prefix) :]
                if object_key.startswith(tenant_prefix)
                else object_key
            )

            try:
                if hasattr(storage, "presigned_get_url"):
                    url = storage.presigned_get_url(
                        tenant_id=str(lead.tenant_id),
                        key=key,
                        expires_seconds=3600,
                    )
                else:
                    url = storage.public_url(
                        tenant_id=str(lead.tenant_id),
                        key=key,
                    )

                name = key.split("/")[-1] if key else ""
                photo_previews.append({"url": url, "name": name})
            except Exception:
                # nooit hard falen op previews
                continue
    except Exception:
        # bij problemen met query/storage gewoon geen foto's tonen
        photo_previews = []

    # -------------------------
    # Quote UI flags (MVP)
    # -------------------------
    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    has_estimate_json = bool((getattr(lead, "estimate_json", None) or "").strip())
    has_final_price = getattr(lead, "final_price", None) is not None
    has_quote_output = has_estimate_html or has_estimate_json or has_final_price
    raw_status = (getattr(lead, "status", "") or "").upper()

    if not has_quote_output:
        quote_status = "none"
    elif raw_status == "ACCEPTED":
        quote_status = "accepted"
    elif raw_status == "NEEDS_REVIEW":
        quote_status = "review"
    elif raw_status in {"SENT", "VIEWED"}:
        quote_status = "sent"
    else:
        quote_status = "generated"

    public_quote_url = public_url_for(request, lead)

    can_generate = not has_quote_output
    can_view = has_estimate_html
    # Allow sending (and re-sending) while the estimate is ready and not accepted, with a valid email
    can_send = (
        has_estimate_html
        and raw_status in {"SUCCEEDED", "SENT", "VIEWED", "REJECTED"}
        and bool((getattr(lead, "email", "") or "").strip())
    )
    # Keep edit available in all quote phases except accepted/planning phase
    can_edit = has_quote_output and raw_status != "ACCEPTED"
    # Allow regeneration while not accepted
    can_regenerate = has_quote_output and raw_status != "ACCEPTED"
    # Public-link is primarily useful once customer flow started
    can_copy_link = bool(public_quote_url) and raw_status in {
        "SENT",
        "VIEWED",
        "REJECTED",
        "ACCEPTED",
    }
    # PDF: same inputs as export-pdf route (HTML and/or JSON), any lifecycle stage
    can_download_pdf = has_estimate_html or has_estimate_json

    total_price_value = (
        effective_total_display
        or getattr(lead, "final_price", None)
        or getattr(lead, "total_amount_display", None)
    )
    needs_review = bool(raw_status == "NEEDS_REVIEW")
    has_total_price = bool(total_price_value)
    price_mode = "priced" if (has_total_price and not needs_review) else "tbd"
    pricing_ready = bool((raw_status == "SUCCEEDED") and (not needs_review) and has_total_price)
    is_provisional = False
    show_prices = bool(pricing_ready and price_mode == "priced")

    quote_ui = {
        "has_estimate": has_estimate_html,
        "has_quote_output": has_quote_output,
        "quote_status": quote_status,
        "can_generate": can_generate,
        "can_view": can_view,
        "can_edit": can_edit,
        "can_regenerate": can_regenerate,
        "can_send": can_send,
        "can_copy_link": can_copy_link,
        "can_download_pdf": can_download_pdf,
        "public_quote_url": public_quote_url,
        "needs_review": needs_review,
        "lead_status": raw_status,
        "total_price": total_price_value,
        "price_mode": price_mode,
        "pricing_ready": pricing_ready,
        "is_provisional": is_provisional,
        "show_prices": show_prices,
        "is_public": False,
    }
    logger.info(
        "[UI_MODE] estimate_id=%s is_public=%s route=%s",
        str(getattr(lead, "id", "")),
        False,
        f"GET {request.url.path}",
    )
    logger.info(
        "QUOTE_OUTPUT_DECISION lead_id=%s needs_review=%s lead_status=%s pricing_status=%s total_price=%r price_mode=%s template=%s review_page=%s show_prices=%s pricing_ready=%s is_provisional=%s review_reasons=%r",
        getattr(lead, "id", None),
        needs_review,
        raw_status,
        quote_status,
        total_price_value,
        price_mode,
        "app/lead_detail.html",
        bool(quote_status == "review"),
        show_prices,
        pricing_ready,
        is_provisional,
        None,
    )

    # Tenant-level entitlements for per-lead UI (PDF export button, etc.).
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(current_user.tenant_id))
        .first()
    )
    google_connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == str(current_user.tenant_id),
            CalendarConnection.provider == "google",
        )
        .first()
    )

    from app.verticals.paintly.router_htmx import timeline_rows_for_lead

    internal_notes_val = str(overrides.get("internal_notes") or "")
    followup_summary = build_followup_summary(overrides, tz_name)
    tenant_pricing = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant is not None else {}
    current_wall_rate = tenant_pricing.get("walls_rate_eur_per_sqm")
    missing_wall_rate = current_wall_rate in (None, "")
    show_missing_wall_rate_prompt = (
        missing_wall_rate
        and (request.query_params.get("missing_wall_rate") or "").strip().lower()
        in {"1", "true", "yes"}
    )

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "lead": lead,
            "job": job,
            "intake_payload_dict": intake_payload_dict,
            "quote_ui": quote_ui,
            "show_prices": show_prices,
            "pricing_ready": pricing_ready,
            "is_provisional": is_provisional,
            "price_mode": price_mode,
            "needs_review": needs_review,
            "total_price": total_price_value,
            "lead_status": raw_status,
            "photo_previews": photo_previews,
            "tz_name": tz_name,
            "scheduled_input_value": scheduled_input_value,
            "scheduled_display": scheduled_display,
            "started_display": started_display,
            "done_display": done_display,
            "sent_display": sent_display,
            "lead_scheduled_start_display": lead_scheduled_start_display,
            "lead_scheduled_end_display": lead_scheduled_end_display,
            "estimate_overrides": overrides,
            "effective_total_display": effective_total_display,
            "entitlements": tenant_entitlements(tenant),
            "google_calendar_connected": bool(google_connection),
            "timeline_rows": timeline_rows_for_lead(lead, tz_name, lang=lang),
            "internal_notes": internal_notes_val,
            "followup_summary": followup_summary,
            "current_wall_rate": current_wall_rate,
            "missing_wall_rate": missing_wall_rate,
            "show_missing_wall_rate_prompt": show_missing_wall_rate_prompt,
        },
    )
    return templates.TemplateResponse("app/lead_detail.html", context)


@router.get("/leads/{lead_id}/estimate")
def app_lead_estimate(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    html_key = getattr(lead, "estimate_html_key", None)
    if not html_key:
        raise HTTPException(status_code=404, detail="Estimate HTML not found")

    logger.info(
        "APP_LEAD_ESTIMATE_ROUTE lead_id=%s html_key=%r",
        getattr(lead, "id", None),
        html_key,
    )
    logger.info(
        "[UI_MODE] estimate_id=%s is_public=%s route=%s",
        str(getattr(lead, "id", "")),
        False,
        f"GET {request.url.path}",
    )

    return RedirectResponse(url=f"/app/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/refresh")
def app_lead_refresh_estimate(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    # Full pipeline recompute + new HTML. For template-only refreshes use POST .../rerender-estimate-html.
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.verticals.paintly.pipeline import compute_quote_for_lead

    before_html_key = (getattr(lead, "estimate_html_key", None) or "").strip()
    result = compute_quote_for_lead(db=db, lead=lead, render_html=True)
    estimate_json = result.get("estimate_json")
    estimate_html_key = result.get("estimate_html_key")
    branding_company_name = None
    branding_logo_url = None
    if isinstance(estimate_json, dict):
        company = estimate_json.get("company") if isinstance(estimate_json.get("company"), dict) else {}
        branding_company_name = (
            estimate_json.get("branding_company_name")
            or company.get("company_name")
            or company.get("name")
        )
        branding_logo_url = (
            estimate_json.get("branding_logo_url")
            or company.get("logo_url")
        )

    if estimate_json is not None:
        lead.estimate_json = json.dumps(estimate_json, ensure_ascii=False)
    if estimate_html_key:
        lead.estimate_html_key = estimate_html_key
    lead.updated_at = _utcnow()
    db.add(lead)
    db.commit()
    logger.info(
        "APP_LEAD_REFRESH_DONE tenant_id=%s lead_id=%s html_key_before=%r html_key_after=%r branding_company_name=%r branding_logo_url=%r",
        str(current_user.tenant_id),
        str(getattr(lead, "id", "")),
        before_html_key or None,
        (estimate_html_key or None),
        branding_company_name,
        branding_logo_url,
    )

    return RedirectResponse(url=f"/app/leads/{lead_id}/estimate", status_code=303)


@router.post("/leads/{lead_id}/rerender-estimate-html")
def app_lead_rerender_estimate_html(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    """
    Re-materialize stored estimate HTML from estimate_json + overrides only (no AI/pipeline).
    Use after Jinja/template changes; updates estimate_html_key to a new storage object.
    """
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    ok, err = rerender_stored_estimate_html_from_json(db, lead)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail=f"Could not rerender estimate HTML: {err}",
        )
    return RedirectResponse(url=f"/app/leads/{lead_id}", status_code=303)


@router.get("/leads/{lead_id}/export-pdf")
def export_lead_estimate_pdf(
    lead_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_entitlement(Action.EXPORT_PDF.value)),
):
    """
    Download the lead estimate as PDF (premium: requires EXPORT_PDF entitlement).

    Returns 403 with entitlement payload if the tenant does not have PDF export.

    Smoke test: GET /app/leads/<lead_id>/export-pdf
    - As Pro/Business tenant with a lead that has estimate_html_key -> 200 + PDF.
    - As Starter (or inactive) -> 403 with detail.error "entitlement_denied".
    - Missing lead or no estimate -> 404.
    """
    logger.info(
        "PDF_EXPORT_ROUTE_ACCESS tenant_id=%s lead_id=%s plan_code=%s subscription_status=%s action=%s",
        getattr(tenant, "id", None),
        lead_id,
        getattr(tenant, "plan_code", None),
        getattr(tenant, "subscription_status", None),
        Action.EXPORT_PDF.value,
    )
    route_ent = check_entitlement(tenant, Action.EXPORT_PDF.value)
    logger.info(
        "PDF_EXPORT_ROUTE_ENTITLEMENT tenant_id=%s lead_id=%s action=%s allowed=%s reason=%s plan_code=%s subscription_status=%s",
        getattr(tenant, "id", None),
        lead_id,
        Action.EXPORT_PDF.value,
        route_ent.allowed,
        route_ent.reason,
        route_ent.plan_code,
        route_ent.subscription_status,
    )

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == tenant.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Prefer structured estimate_json for PDF rendering; fall back to stored HTML only
    # when JSON is unavailable for legacy records.
    estimate_json = getattr(lead, "estimate_json", None)
    estimate_data: dict | None = None
    html_content: str | None = None

    if estimate_json:
        try:
            estimate = json.loads(estimate_json)
        except Exception as e:
            logger.warning(
                "export_pdf_estimate_json_parse_failed lead_id=%s reason=%s",
                lead_id,
                type(e).__name__,
            )
        else:
            estimate_data = estimate if isinstance(estimate, dict) else None
            try:
                html_content = render_estimate_pdf_html(estimate)
            except Exception as e:
                logger.exception(
                    "export_pdf_render_estimate_pdf_html_failed lead_id=%s",
                    lead_id,
                )
                raise HTTPException(
                    status_code=500, detail="PDF template rendering failed"
                ) from e

    if html_content is None:
        html_key = (getattr(lead, "estimate_html_key", None) or "").strip()
        if not html_key:
            raise HTTPException(status_code=404, detail="Estimate not found")

        tenant_id = str(tenant.id)
        storage = get_storage()
        try:
            html_content = get_text(storage, tenant_id=tenant_id, key=html_key)
        except Exception as e:
            logger.warning(
                "export_pdf_get_html_failed lead_id=%s reason=%s",
                lead_id,
                type(e).__name__,
            )
            raise HTTPException(status_code=404, detail="Estimate file not found") from e

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_content).write_pdf()
    except OSError as e:
        # Typical root cause: missing native libs (eg on Windows dev or slim Linux images)
        # such as libgobject-2.0-0 / cairo / pango.
        logger.error(
            "export_pdf_native_deps_missing lead_id=%s err=%s",
            lead_id,
            str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="PDF generation is temporarily unavailable on this server.",
        ) from e
    except Exception as e:
        logger.exception("export_pdf_render_failed lead_id=%s", lead_id)
        raise HTTPException(status_code=500, detail="PDF generation failed") from e

    download_filename = _build_pdf_download_filename(
        lead_id=lead_id,
        estimate=estimate_data,
        tenant=tenant,
        db=db,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store",
        },
    )


class BrandingUpdate(BaseModel):
    """
    Small payload for updating tenant branding (logo URL).

    Backend enforcement is via USE_BRANDING entitlement; UI usage of logo_url
    in templates/PDFs should always respect the same entitlement.
    """

    logo_url: str | None = None


@router.post("/settings/branding")
def update_branding_settings(
    payload: BrandingUpdate,
    current_user: User = Depends(require_user_html),
    tenant: Tenant = Depends(require_entitlement(Action.USE_BRANDING.value)),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    """
    Update branding settings (currently: logo_url) for the current tenant.

    - Protected by USE_BRANDING entitlement.
    - Writes into the shared TenantService config used by Paintly.

    Smoke test:
    - Starter tenant: 403 with error \"entitlement_denied\".
    - Pro/Business tenant: 200 and JSON payload with updated logo_url.
    """
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant id missing")

    # TenantService keeps in-memory + JSON-backed TenantSettings.
    # We only update when a concrete TenantSettings exists for this tenant id.
    updated = tenant_service.update_tenant(str(tenant_id), logo_url=payload.logo_url)
    if updated is None:
        raise HTTPException(status_code=404, detail="Tenant settings not found")

    logger.info("branding_updated tenant_id=%s", tenant_id)
    return {"logo_url": updated.logo_url}


from fastapi import BackgroundTasks


def _paintly_hx_toast(level: str, title: str, message: str = "") -> HTMLResponse:
    return HTMLResponse(
        "",
        headers={
            "HX-Trigger": json.dumps(
                {"show-toast": {"level": level, "title": title, "message": message}}
            )
        },
    )


@router.post("/leads/{lead_id}/send")
def send_estimate(
    lead_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    lang = (
        getattr(current_user, "lang", None)
        or getattr(current_user, "language", None)
        or resolve_language(request)
        or "nl"
    )
    logger.info(
        "SEND_ESTIMATE_ROUTE_HIT lead_id=%s user_id=%s tenant_id=%s",
        lead_id,
        str(getattr(current_user, "id", "")),
        str(getattr(current_user, "tenant_id", "")),
    )

    is_htmx = (request.headers.get("hx-request") or "").lower() == "true"
    logger.info("SEND_ESTIMATE_REQUEST_MODE lead_id=%s is_htmx=%s", lead_id, is_htmx)

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "SEND_ESTIMATE_LEAD_FOUND lead_id=%s tenant_id=%s status=%s",
        lead_id,
        str(getattr(lead, "tenant_id", "")),
        str(getattr(lead, "status", "")),
    )

    tenant = db.query(Tenant).filter(Tenant.id == lead.tenant_id).first()
    if not tenant:
        logger.warning("SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=tenant_not_found", lead_id)
        raise HTTPException(status_code=404, detail="Tenant not found")
    logger.info("SEND_ESTIMATE_TENANT_FOUND lead_id=%s tenant_id=%s", lead_id, str(lead.tenant_id))

    # Usage context for centralized entitlement + monthly volume gating.
    plan_code = getattr(tenant, "plan_code", None) if tenant is not None else None
    plan_key = plan_code or DEFAULT_PLAN_CODE
    plan_item = get_plan_item(plan_key)
    monthly_offer_limit = getattr(plan_item, "monthly_offer_limit", None)

    usage = get_or_create_usage(db, str(lead.tenant_id))

    logger.info(
        "SEND_ESTIMATE_USAGE_ANALYTICS lead_id=%s tenant_id=%s tenant_plan_code=%s "
        "plan_key=%s quotes_sent=%s monthly_offer_limit=%s",
        lead.id,
        lead.tenant_id,
        plan_code,
        plan_key,
        getattr(usage, "quotes_sent", None),
        monthly_offer_limit,
    )

    # Centralized entitlement check (subscription + feature + usage/paywall)
    class _SendQuoteContext:
        def __init__(self, tenant_obj: Tenant, quotes_sent: int | None):
            self.plan_code = getattr(tenant_obj, "plan_code", None)
            self.subscription_status = getattr(tenant_obj, "subscription_status", None)
            self.trial_ends_at = getattr(tenant_obj, "trial_ends_at", None)
            self.quotes_sent = quotes_sent
            self.monthly_usage_baseline = monthly_offer_limit

    ctx = _SendQuoteContext(
        tenant_obj=tenant,
        quotes_sent=getattr(usage, "quotes_sent", None),
    )
    ent = check_entitlement(ctx, Action.SEND_QUOTE.value)
    logger.info(
        "SEND_ESTIMATE_ENTITLEMENT lead_id=%s allowed=%s reason=%s",
        lead_id,
        bool(getattr(ent, "allowed", False)),
        str(getattr(ent, "reason", "") or ""),
    )
    if not ent.allowed:
        lang = resolve_language(request)
        # Preserve existing UX while using centralized reasoning
        if ent.reason == "subscription_inactive":
            if is_htmx:
                logger.info(
                    "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=subscription_inactive response=hx_toast",
                    lead_id,
                )
                return _paintly_hx_toast(
                    "error",
                    translate("lead_detail.send.subscription_title", lang=lang),
                    translate("lead_detail.send.subscription_inactive", lang=lang),
                )
            logger.info(
                "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=subscription_inactive response=redirect",
                lead_id,
            )
            return RedirectResponse(
                url="/app/billing?send_error=billing_status",
                status_code=303,
            )
        if ent.reason == "monthly_offer_limit_reached":
            limit = int(ent.usage_limit or monthly_offer_limit or 25)
            msg = translate("errors.offer_limit_message", lang=lang, limit=limit)
            if is_htmx:
                logger.info(
                    "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=monthly_offer_limit_reached response=hx_toast",
                    lead_id,
                )
                return _paintly_hx_toast(
                    "error",
                    translate("errors.offer_limit_title", lang=lang),
                    msg,
                )
            accepts_json = "application/json" in (
                request.headers.get("accept", "").lower()
            )
            if accepts_json:
                logger.info(
                    "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=monthly_offer_limit_reached response=http_403_json",
                    lead_id,
                )
                raise HTTPException(status_code=403, detail=msg)
            logger.info(
                "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=monthly_offer_limit_reached response=redirect",
                lead_id,
            )
            return RedirectResponse(
                url=f"/app/leads/{lead_id}?send_error=offer_limit",
                status_code=303,
            )

        upgrade_url = ent.upgrade_url or f"/app/billing?upgrade=1&feature={Feature.BASIC_SENDING.value}"
        if is_htmx:
            logger.info(
                "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=entitlement_denied response=hx_toast",
                lead_id,
            )
            return _paintly_hx_toast(
                "error",
                translate("lead_detail.send.not_allowed_title", lang=lang),
                translate("lead_detail.send.not_allowed_message", lang=lang),
            )
        logger.info(
            "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=entitlement_denied response=redirect",
            lead_id,
        )
        return RedirectResponse(url=upgrade_url, status_code=303)

    has_estimate_html = bool((getattr(lead, "estimate_html_key", None) or "").strip())
    logger.info(
        "SEND_ESTIMATE_ARTIFACT_CHECK lead_id=%s has_estimate_html=%s",
        lead_id,
        has_estimate_html,
    )
    if not has_estimate_html:
        # Geen offerte beschikbaar om te versturen -> nette melding op lead detail
        if is_htmx:
            logger.info(
                "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=no_estimate_html response=hx_toast",
                lead_id,
            )
            return _paintly_hx_toast(
                "error",
                translate("lead_detail.send.no_quote_title", lang=lang),
                translate("lead_detail.send.no_quote_message", lang=lang),
            )
        logger.info(
            "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=no_estimate_html response=redirect",
            lead_id,
        )
        return RedirectResponse(
            url=f"/app/leads/{lead_id}?send_error=no_estimate",
            status_code=303,
        )

    # ensure public token
    had_public_token = bool((getattr(lead, "public_token", None) or "").strip())
    if not had_public_token:
        lead.public_token = secrets.token_hex(16)
        logger.info("SEND_ESTIMATE_PUBLIC_TOKEN_GENERATED lead_id=%s", lead_id)
    else:
        logger.info("SEND_ESTIMATE_PUBLIC_TOKEN_EXISTS lead_id=%s", lead_id)

    # build public quote url
    base = (settings.APP_PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
    quote_url = f"{base}/e/{lead.public_token}"

    # must have email
    to_email = (getattr(lead, "email", "") or "").strip()
    logger.info("SEND_ESTIMATE_RECIPIENT_CHECK lead_id=%s has_recipient=%s", lead_id, bool(to_email))
    if not to_email:
        # Geen klant e-mail -> nette melding op lead detail
        if is_htmx:
            logger.info(
                "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=no_recipient_email response=hx_toast",
                lead_id,
            )
            return _paintly_hx_toast(
                "error",
                translate("lead_detail.send.no_email_title", lang=lang),
                translate("lead_detail.send.no_email_message", lang=lang),
            )
        logger.info(
            "SEND_ESTIMATE_EARLY_RETURN lead_id=%s reason=no_recipient_email response=redirect",
            lead_id,
        )
        return RedirectResponse(
            url=f"/app/leads/{lead_id}?send_error=no_email",
            status_code=303,
        )

    company_name = "Paintly"
    customer_name = getattr(lead, "name", "") or ""

    async def _send():
        logger.info("Sending estimate email to %s", to_email)
        await send_estimate_ready_email_to_customer(
            to_email=to_email,
            customer_name=customer_name,
            quote_url=quote_url,
            company_name=company_name,
            lead_id=lead.id,
            tenant_id=str(lead.tenant_id),
        )

    try:
        asyncio.run(_send())
    except EmailSendError:
        logger.exception("SEND_ESTIMATE_EMAIL_SEND_FAILED lead_id=%s", lead_id)
        if is_htmx:
            return _paintly_hx_toast(
                "error",
                translate("lead_detail.send.not_allowed_title", lang=lang),
                "Kon offerte niet verzenden. Probeer het opnieuw.",
            )
        return RedirectResponse(url=f"/app/leads/{lead_id}?send_error=1", status_code=303)
    except Exception:
        logger.exception("SEND_ESTIMATE_UNEXPECTED_SEND_EXCEPTION lead_id=%s", lead_id)
        if is_htmx:
            return _paintly_hx_toast(
                "error",
                translate("lead_detail.send.not_allowed_title", lang=lang),
                "Kon offerte niet verzenden. Probeer het opnieuw.",
            )
        return RedirectResponse(url=f"/app/leads/{lead_id}?send_error=1", status_code=303)
    logger.info("SEND_ESTIMATE_BACKGROUND_TASK_SCHEDULED lead_id=%s to=%s", lead_id, to_email)

    # Increment usage only after a successful send has been scheduled
    increment_usage(db, str(lead.tenant_id))

    # mark as sent
    lead.status = "SENT"
    lead.sent_at = _utcnow()

    db.add(lead)
    db.commit()
    db.refresh(lead)

    if is_htmx:
        from app.verticals.paintly.router_htmx import render_quote_oob_response

        resp = render_quote_oob_response(
            request,
            db,
            current_user,
            lead_id,
            toast_title=translate("lead_detail.send.toast_sent_title", lang=lang),
            toast_message=translate("lead_detail.send.toast_sent_message", lang=lang),
        )
        resp.background = background_tasks
        logger.info("SEND_ESTIMATE_RESPONSE lead_id=%s response=htmx_oob", lead_id)
        return resp

    response = RedirectResponse(
        url=f"/app/leads/{lead_id}?sent=1",
        status_code=303,
    )
    response.background = background_tasks
    logger.info("SEND_ESTIMATE_RESPONSE lead_id=%s response=redirect", lead_id)
    return response


# -------------------------
# Jobs
# -------------------------
def _get_job_or_404(db: Session, job_id: int, tenant_id: str) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == tenant_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _sync_lead_schedule_window(
    *,
    db: Session,
    tenant_id: str,
    lead_id: str,
    start_utc: datetime | None,
    duration_hours: int = 4,
) -> None:
    lead = (
        db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
    )
    if not lead:
        return

    lead.scheduled_start = start_utc
    if start_utc is None:
        lead.scheduled_end = None
    else:
        lead.scheduled_end = start_utc + timedelta(hours=duration_hours)
    db.add(lead)


@router.post("/jobs/{job_id}/status")
def app_job_set_status(
    request: Request,
    job_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    s = (status or "").upper().strip()
    if s not in ALLOWED_JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    job.status = s
    db.add(job)
    db.commit()

    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.get("/jobs", response_class=HTMLResponse)
def app_jobs_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    status: str | None = Query(default=None),
):
    tenant_id = str(current_user.tenant_id)

    counts_rows = (
        db.query(Job.status, func.count(Job.id))
        .filter(Job.tenant_id == tenant_id)
        .group_by(Job.status)
        .all()
    )
    counts_map = {str(s): int(c) for s, c in counts_rows}
    counts = {s: counts_map.get(s, 0) for s in sorted(ALLOWED_JOB_STATUSES)}

    q = db.query(Job).filter(Job.tenant_id == tenant_id)

    status_norm = (status or "").upper().strip() if status else None
    if status_norm:
        if status_norm not in ALLOWED_JOB_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        q = q.filter(Job.status == status_norm)

    order_col = (
        getattr(Job, "updated_at", None) or getattr(Job, "created_at", None) or Job.id
    )
    jobs = q.order_by(desc(order_col)).limit(200).all()

    lead_ids = [j.lead_id for j in jobs]
    leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all() if lead_ids else []
    lead_map = {l.id: l for l in leads}

    tz_name = _get_tenant_timezone(current_user, None)

    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz).date()
    tomorrow_local = today_local + timedelta(days=1)

    rows = []
    for j in jobs:
        l = lead_map.get(j.lead_id)

        when_label = ""
        if getattr(j, "scheduled_at", None):
            d = j.scheduled_at.astimezone(tz).date()
            if d == today_local:
                when_label = "Today"
            elif d == tomorrow_local:
                when_label = "Tomorrow"

        rows.append(
            {
                "id": j.id,
                "status": (j.status or "").upper(),
                "lead_id": j.lead_id,
                "customer": (getattr(l, "name", "") or "—") if l else "—",
                "email": (getattr(l, "email", "") or "") if l else "",
                "scheduled_at": getattr(j, "scheduled_at", None),
                "scheduled_at_local": (
                    _utc_to_local_human(getattr(j, "scheduled_at", None), tz_name)
                    if getattr(j, "scheduled_at", None)
                    else ""
                ),
                "scheduled_tz": getattr(j, "scheduled_tz", None),
                "when_label": when_label,
                "updated_at": getattr(j, "updated_at", None),
            }
        )

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "jobs": rows,
            "counts": counts,
            "active_status": status_norm,
        },
    )
    return templates.TemplateResponse("app/jobs_list.html", context)


@router.post("/jobs/{job_id}/schedule")
def job_schedule(
    job_id: int,
    scheduled_at_local: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    # guard: block closed jobs
    if (job.status or "").upper() in ("DONE", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Cannot schedule a closed job")

    tz_name = _get_tenant_timezone(current_user, job)

    dt_local_naive = _parse_datetime_local(scheduled_at_local)
    dt_utc = _local_naive_to_utc(dt_local_naive, tz_name)

    job.scheduled_at = dt_utc

    # Store tz if field exists
    if hasattr(job, "scheduled_tz"):
        job.scheduled_tz = tz_name
    _sync_lead_schedule_window(
        db=db,
        tenant_id=str(current_user.tenant_id),
        lead_id=job.lead_id,
        start_utc=dt_utc,
    )

    # Auto status
    if (job.status or "").upper() in ("NEW", "SCHEDULED"):
        job.status = "SCHEDULED"

    db.add(job)
    db.commit()
    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.post("/jobs/{job_id}/quick_schedule")
def job_quick_schedule(
    job_id: int,
    day_offset: int = Form(...),  # 0 = today, 1 = tomorrow, 2 = +2
    hhmm: str = Form(...),  # "09:00" / "13:00"
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    if (job.status or "").upper() in ("DONE", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Cannot schedule a closed job")

    tz_name = _get_tenant_timezone(current_user, job)
    tz = ZoneInfo(tz_name)

    # Build local datetime: (today + offset) at hh:mm, in tenant tz
    now_local = datetime.now(tz)
    base_date = now_local.date() + timedelta(days=int(day_offset))

    try:
        hh, mm = hhmm.split(":")
        hour = int(hh)
        minute = int(mm)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid time")

    dt_local = datetime(
        year=base_date.year,
        month=base_date.month,
        day=base_date.day,
        hour=hour,
        minute=minute,
        tzinfo=tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)

    job.scheduled_at = dt_utc
    if hasattr(job, "scheduled_tz"):
        job.scheduled_tz = tz_name
    _sync_lead_schedule_window(
        db=db,
        tenant_id=str(current_user.tenant_id),
        lead_id=job.lead_id,
        start_utc=dt_utc,
    )

    if (job.status or "").upper() in ("NEW", "SCHEDULED"):
        job.status = "SCHEDULED"

    db.add(job)
    db.commit()

    # Redirect back to calendar by default
    dest = return_to or "/app/calendar"
    return RedirectResponse(url=dest, status_code=303)


@router.post("/jobs/{job_id}/unschedule")
def job_unschedule(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    if (job.status or "").upper() in ("DONE", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Cannot unschedule a closed job")

    job.scheduled_at = None
    if hasattr(job, "scheduled_tz"):
        job.scheduled_tz = _get_tenant_timezone(current_user, job)
    _sync_lead_schedule_window(
        db=db,
        tenant_id=str(current_user.tenant_id),
        lead_id=job.lead_id,
        start_utc=None,
    )

    if (job.status or "").upper() == "SCHEDULED":
        job.status = "NEW"

    db.add(job)
    db.commit()
    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.post("/jobs/{job_id}/schedule_now")
def job_schedule_now(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    now = _utcnow()
    if not getattr(job, "scheduled_at", None):
        job.scheduled_at = now
        _sync_lead_schedule_window(
            db=db,
            tenant_id=str(current_user.tenant_id),
            lead_id=job.lead_id,
            start_utc=now,
        )

    if hasattr(job, "scheduled_tz") and not getattr(job, "scheduled_tz", None):
        job.scheduled_tz = _get_tenant_timezone(current_user, job)

    if (job.status or "").upper() == "NEW":
        job.status = "SCHEDULED"

    db.add(job)
    db.commit()
    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.post("/jobs/{job_id}/start")
def job_start(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    # Guardrail: require scheduling before starting
    if not getattr(job, "scheduled_at", None):
        raise HTTPException(status_code=400, detail="Schedule the job first")

    now = _utcnow()
    if not getattr(job, "started_at", None):
        job.started_at = now

    job.status = "IN_PROGRESS"

    db.add(job)
    db.commit()
    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.post("/jobs/{job_id}/done")
def job_done(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    job = _get_job_or_404(db, job_id, tenant_id=str(current_user.tenant_id))

    now = _utcnow()
    if not getattr(job, "done_at", None):
        job.done_at = now

    job.status = "DONE"

    db.add(job)
    db.commit()
    return RedirectResponse(url=f"/app/leads/{job.lead_id}#job", status_code=303)


@router.get("/calendar", response_class=HTMLResponse)
def app_calendar_week(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    week: str | None = Query(default=None),
    show_done: int = Query(default=0),
    intent: str | None = Query(default=None),
    lead_id: str | None = Query(default=None),
):
    tenant_id = str(current_user.tenant_id)
    tz_name = _get_tenant_timezone(current_user, None)
    tz = ZoneInfo(tz_name)

    now_local = datetime.now(tz)

    # -------- week start bepalen
    if week:
        try:
            year_str, w_str = week.split("-W")
            year = int(year_str)
            week_no = int(w_str)
            week_start_local = datetime.fromisocalendar(year, week_no, 1).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
            )
        except Exception:
            week_start_local = (
                now_local - timedelta(days=now_local.weekday())
            ).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        week_start_local = (now_local - timedelta(days=now_local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    week_end_local = week_start_local + timedelta(days=7)

    week_start_utc = week_start_local.astimezone(timezone.utc)
    week_end_utc = week_end_local.astimezone(timezone.utc)

    # -------- status filter (toggle DONE)
    include_statuses = {"SCHEDULED", "IN_PROGRESS"}
    if show_done:
        include_statuses.add("DONE")

    # -------- scheduled jobs
    jobs = (
        db.query(Job)
        .filter(
            Job.tenant_id == tenant_id,
            Job.scheduled_at.isnot(None),
            Job.scheduled_at >= week_start_utc,
            Job.scheduled_at < week_end_utc,
            Job.status.in_(list(include_statuses)),
        )
        .order_by(Job.scheduled_at.asc())
        .all()
    )

    # -------- unscheduled NEW jobs (sidebar)
    unscheduled = (
        db.query(Job)
        .filter(
            Job.tenant_id == tenant_id,
            Job.scheduled_at.is_(None),
            Job.status == "NEW",
        )
        .order_by(desc(getattr(Job, "updated_at", Job.id)))
        .limit(50)
        .all()
    )

    # -------- leads ophalen
    lead_ids = [j.lead_id for j in jobs] + [u.lead_id for u in unscheduled]
    lead_ids = list({lid for lid in lead_ids if lid})
    leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all() if lead_ids else []
    lead_map = {l.id: l for l in leads}

    # -------- dagen bouwen
    days = []
    for i in range(7):
        dt = week_start_local + timedelta(days=i)
        days.append(
            {
                "date": dt.date().isoformat(),
                "title": dt.strftime("%a"),
                "is_today": dt.date() == now_local.date(),
                "items": [],
                "counts": {"TOTAL": 0, "SCHEDULED": 0, "IN_PROGRESS": 0, "DONE": 0},
            }
        )

    def day_index(dt_utc: datetime) -> int:
        dt_local = dt_utc.astimezone(tz)
        return (dt_local.date() - week_start_local.date()).days

    # -------- jobs per dag
    for j in jobs:
        idx = day_index(j.scheduled_at)
        if idx < 0 or idx > 6:
            continue

        lead = lead_map.get(j.lead_id)
        dt_local = j.scheduled_at.astimezone(tz)

        item = {
            "job_id": j.id,
            "lead_id": j.lead_id,
            "status": (j.status or "").upper(),
            "time": dt_local.strftime("%H:%M"),
            "customer": (getattr(lead, "name", "") or "—") if lead else "—",
            "notes": (getattr(lead, "notes", "") or "") if lead else "",
        }

        days[idx]["items"].append(item)

        st = item["status"]
        days[idx]["counts"]["TOTAL"] += 1
        if st in days[idx]["counts"]:
            days[idx]["counts"][st] += 1

    # sort times
    for d in days:
        d["items"].sort(key=lambda x: x["time"])

    # -------- unscheduled vm
    unscheduled_vm = []
    for u in unscheduled:
        lead = lead_map.get(u.lead_id)
        unscheduled_vm.append(
            {
                "job_id": u.id,
                "lead_id": u.lead_id,
                "customer": (getattr(lead, "name", "") or "—") if lead else "—",
                "notes": (getattr(lead, "notes", "") or "") if lead else "",
            }
        )

    # -------- nav
    iso = week_start_local.isocalendar()
    year, week_no, _ = iso

    prev_start = week_start_local - timedelta(days=7)
    next_start = week_start_local + timedelta(days=7)

    prev_iso = prev_start.isocalendar()
    next_iso = next_start.isocalendar()

    prev_week = f"{prev_iso.year}-W{prev_iso.week:02d}"
    next_week = f"{next_iso.year}-W{next_iso.week:02d}"

    week_label = (
        f"Week {week_no} · {week_start_local.date()} → "
        f"{(week_end_local - timedelta(days=1)).date()}"
    )

    now_chip = now_local.strftime("%a %b %d · %H:%M")

    toggle_done_url = (
        f"/app/calendar?week={year}-W{week_no:02d}&show_done={0 if show_done else 1}"
    )

    bezichtiging_prefill: dict[str, str] | None = None
    calendar_nav_qs = ""
    raw_intent = (intent or "").strip().lower()
    raw_lead_id = (lead_id or "").strip()
    if raw_intent == "bezichtiging" and raw_lead_id:
        lead_bz = (
            db.query(Lead)
            .filter(Lead.id == raw_lead_id, Lead.tenant_id == tenant_id)
            .first()
        )
        if lead_bz:
            intake_dict: dict = {}
            raw_pl = getattr(lead_bz, "intake_payload", None)
            if raw_pl:
                try:
                    parsed = json.loads(raw_pl)
                    if isinstance(parsed, dict):
                        intake_dict = parsed
                except Exception:
                    intake_dict = {}
            bezichtiging_prefill = _bezichtiging_prefill_from_lead(lead_bz, intake_dict)
            calendar_nav_qs = urlencode(
                {"intent": "bezichtiging", "lead_id": str(lead_bz.id)}
            )
            toggle_done_url += f"&{calendar_nav_qs}"

    google_connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == tenant_id,
            CalendarConnection.provider == "google",
        )
        .first()
    )

    upcoming_calendar_events: list[dict[str, Any]] = []
    if google_connection:
        upcoming_calendar_events = fetch_upcoming_calendar_events_merged(
            db,
            tenant_id,
            tz_name=tz_name,
            days_ahead=30,
            max_results=25,
        )

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "tz_name": tz_name,
            "week_label": week_label,
            "now_chip": now_chip,
            "days": days,
            "prev_week": prev_week,
            "next_week": next_week,
            "unscheduled": unscheduled_vm,
            "show_done": show_done,
            "toggle_done_url": toggle_done_url,
            "google_calendar_connected": bool(google_connection),
            "google_calendar_id": (
                google_connection.calendar_id if google_connection else "primary"
            ),
            "bezichtiging_prefill": bezichtiging_prefill,
            "calendar_nav_qs": calendar_nav_qs,
            "upcoming_calendar_events": upcoming_calendar_events,
        },
    )
    return templates.TemplateResponse("app/calendar_week.html", context)


@router.get("/reviews", response_class=HTMLResponse)
def app_reviews_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant = str(current_user.tenant_id)

    # Gebruik dezelfde businessregel als derive_status:
    # - expliciete status NEEDS_REVIEW
    # - of needs_review_hard-flag actief
    leads = (
        db.query(Lead)
        .filter(
            or_(
                Lead.status == "NEEDS_REVIEW",
                getattr(Lead, "needs_review_hard", None) == True,  # noqa: E712
            ),
            or_(Lead.tenant_id == tenant, Lead.tenant_id == "public"),
        )
        # Sorteer op aanmaakmoment (nieuwste eerst), onafhankelijk van updates
        .order_by(desc(Lead.created_at), desc(Lead.id))
        .limit(200)
        .all()
    )

    try:
        lead_statuses = sorted({getattr(l, "status", None) for l in leads})
    except Exception:
        lead_statuses = []
    logger.debug(
        "APP_REVIEWS_LIST_DEBUG tenant=%s leads_count=%s lead_statuses=%r needs_review_hard_present=%s",
        tenant,
        len(leads),
        lead_statuses,
        any(getattr(l, "needs_review_hard", None) for l in leads),
    )

    # Extra debug: how many leads exist per tenant filter and what we selected.
    try:
        needs_review_count_current_tenant = (
            db.query(Lead)
            .filter(
                Lead.status == "NEEDS_REVIEW",
                Lead.tenant_id == tenant,
            )
            .count()
        )
        needs_review_count_public = (
            db.query(Lead)
            .filter(
                Lead.status == "NEEDS_REVIEW",
                Lead.tenant_id == "public",
            )
            .count()
        )
    except Exception:
        needs_review_count_current_tenant = None
        needs_review_count_public = None

    try:
        selected_lead_rows = [
            {
                "id": getattr(l, "id", None),
                "tenant_id": getattr(l, "tenant_id", None),
                "status": getattr(l, "status", None),
            }
            for l in leads[:50]
        ]
    except Exception:
        selected_lead_rows = []

    logger.debug(
        "APP_REVIEWS_LIST_DEBUG counts tenant_needs_review=%r public_needs_review=%r selected_leads_first50=%r",
        needs_review_count_current_tenant,
        needs_review_count_public,
        selected_lead_rows,
    )

    context = _dashboard_context(
        request,
        current_user,
        db,
        {"leads": leads},
    )
    return templates.TemplateResponse("app/reviews_list.html", context)


@router.get("/reviews/{lead_id}", response_class=HTMLResponse)
def app_review_detail(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    lead = (
        db.query(Lead)
        .filter(
            Lead.id == lead_id,
            Lead.tenant_id == str(current_user.tenant_id),
        )
        .first()
    )
    if not lead:
        # DEBUG: bestaat lead_id überhaupt (los van tenant)?
        lead_any = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead_any:
            raise HTTPException(
                status_code=404,
                detail=f"Lead exists but tenant mismatch. lead.tenant_id={lead_any.tenant_id} user.tenant_id={str(current_user.tenant_id)}",
            )
        raise HTTPException(status_code=404, detail="Lead id not found in DB")

    # reasons MVP: uit estimate_json.meta.needs_review_reasons
    reasons = []
    try:
        if lead.estimate_json:
            est = json.loads(lead.estimate_json)
            reasons = (est.get("meta") or {}).get("needs_review_reasons") or []
    except Exception:
        reasons = []

    # uploads (upload_records) voor debug/preview
    uploads = (
        db.query(UploadRecord)
        .filter(
            UploadRecord.tenant_id == lead.tenant_id,
            UploadRecord.lead_id == lead.id,
            UploadRecord.status.in_([UploadStatus.uploaded, "uploaded"]),
        )
        .order_by(UploadRecord.id.desc())
        .all()
    )

    storage = get_storage()

    # photo preview urls (uit upload_records.object_key)
    photo_urls = []
    for u in uploads:
        object_key = (getattr(u, "object_key", "") or "").strip()
        if not object_key:
            continue

        # object_key staat bij jou als "public/uploads/...."
        # storage verwacht meestal key ZONDER tenant prefix:
        tenant_prefix = f"{lead.tenant_id}/"
        key = object_key
        # Some historical records may contain the tenant prefix multiple times.
        while key.startswith(tenant_prefix):
            key = key[len(tenant_prefix) :]
        key = key.lstrip("/")

        try:
            if hasattr(storage, "presigned_get_url"):
                url = storage.presigned_get_url(
                    tenant_id=str(lead.tenant_id),
                    key=key,
                    expires_seconds=3600,
                )
            else:
                url = storage.public_url(
                    tenant_id=str(lead.tenant_id),
                    key=key,
                )
            photo_urls.append(url)
        except Exception:
            # nooit hard failen op preview
            continue

    # estimate preview url
    estimate_preview_url = None
    html_key = (getattr(lead, "estimate_html_key", None) or "").strip()
    if html_key:
        try:
            if hasattr(storage, "presigned_get_url"):
                estimate_preview_url = storage.presigned_get_url(
                    tenant_id=str(lead.tenant_id),
                    key=html_key,
                    expires_seconds=300,
                )
            else:
                estimate_preview_url = storage.public_url(
                    tenant_id=str(lead.tenant_id),
                    key=html_key,
                )
        except Exception:
            estimate_preview_url = None

    can_preview = bool(html_key)

    intake = {}
    try:
        if getattr(lead, "intake_payload", None):
            intake = json.loads(lead.intake_payload)
    except Exception:
        intake = {}

    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == str(current_user.tenant_id))
        .first()
    )
    tenant_pricing = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant is not None else {}
    current_wall_rate = tenant_pricing.get("walls_rate_eur_per_sqm")
    missing_wall_rate = current_wall_rate in (None, "")
    has_missing_wall_rate_reason = "missing_wall_rate" in reasons
    show_missing_wall_rate_prompt = missing_wall_rate or has_missing_wall_rate_reason
    if (request.query_params.get("missing_wall_rate") or "").strip().lower() in {"1", "true", "yes"}:
        show_missing_wall_rate_prompt = True

    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "lead": lead,
            "reasons": reasons,
            "uploads": uploads,
            "photo_urls": photo_urls,
            "can_preview": can_preview,
            "estimate_preview_url": estimate_preview_url,
            "intake": intake,
            "current_wall_rate": current_wall_rate,
            "missing_wall_rate": missing_wall_rate,
            "show_missing_wall_rate_prompt": show_missing_wall_rate_prompt,
        },
    )
    return templates.TemplateResponse("app/review_detail.html", context)


@router.post("/reviews/{lead_id}/generate-estimate")
def app_review_generate_estimate(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Reset -> laat quotes status page opnieuw publishen via autostart JS
    lead.status = "NEW"
    lead.error_message = None
    lead.estimate_json = None
    lead.estimate_html_key = None
    lead.updated_at = _utcnow()

    # ✅ Manual override flag
    payload = {}
    try:
        if getattr(lead, "intake_payload", None):
            payload = json.loads(lead.intake_payload)
    except Exception:
        payload = {}

    payload["manual_override"] = True
    lead.intake_payload = json.dumps(payload, ensure_ascii=False)

    db.add(lead)
    db.commit()

    return RedirectResponse(url=f"/processing/{lead_id}", status_code=303)


@router.post("/app/reviews/{lead_id}/generate-estimate")
def app_review_generate_estimate(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Reset -> laat quotes status page opnieuw publishen via autostart JS
    lead.status = "NEW"
    lead.error_message = None
    lead.estimate_json = None
    lead.estimate_html_key = None
    lead.updated_at = _utcnow()

    # ✅ Manual override flag
    payload = {}
    try:
        if getattr(lead, "intake_payload", None):
            payload = json.loads(lead.intake_payload)
    except Exception:
        payload = {}

    payload["manual_override"] = True
    lead.intake_payload = json.dumps(payload, ensure_ascii=False)

    db.add(lead)
    db.commit()

    return RedirectResponse(url=f"/processing/{lead_id}", status_code=303)


@router.post("/reviews/{lead_id}/overrides")
def app_review_save_overrides(
    lead_id: str,
    square_meters: float | None = Form(default=None),
    job_type: str | None = Form(default=None),
    project_description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    payload = {}
    try:
        if getattr(lead, "intake_payload", None):
            payload = json.loads(lead.intake_payload)
    except Exception:
        payload = {}

    # -------------------------
    # ✅ Area override (EU: m²)
    # -------------------------
    if square_meters is not None:
        sqm = float(square_meters)

        # keep both keys for compatibility
        payload["square_meters"] = sqm
        payload["area_sqm"] = sqm

        if hasattr(lead, "square_meters"):
            lead.square_meters = sqm

        # cleanup old/US keys (do NOT remove square_meters)
        payload.pop("sqft", None)
        payload.pop("sqm", None)

    # -------------------------
    # Job type override
    # -------------------------
    if job_type:
        payload["job_type"] = job_type
        if hasattr(lead, "job_type"):
            lead.job_type = job_type

    # -------------------------
    # Description override
    # -------------------------
    if project_description is not None:
        payload["project_description"] = project_description
        if hasattr(lead, "notes"):
            lead.notes = project_description

    # -------------------------
    # ✅ Manual override flag (so needs_review can be skipped)
    # -------------------------
    payload["manual_override"] = True

    # Persist updated payload
    lead.intake_payload = json.dumps(payload, ensure_ascii=False)

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return RedirectResponse(url=f"/app/reviews/{lead.id}", status_code=303)


@router.get("/leads/{lead_id}/edit-estimate", response_class=HTMLResponse)
def edit_estimate_get(
    lead_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    overrides = get_estimate_overrides(lead)
    editor = _estimate_editor_initial_values(lead, overrides)
    context = _dashboard_context(
        request,
        current_user,
        db,
        {
            "lead": lead,
            "overrides": overrides,
            "editor": editor,
        },
    )
    return templates.TemplateResponse("app/estimate_edit.html", context)


@router.post("/leads/{lead_id}/edit-estimate")
def edit_estimate_post(
    lead_id: str,
    customer_name: str | None = Form(default=None),
    customer_email: str | None = Form(default=None),
    customer_phone: str | None = Form(default=None),
    project_location: str | None = Form(default=None),
    company_name: str | None = Form(default=None),
    company_email: str | None = Form(default=None),
    company_phone: str | None = Form(default=None),
    reference: str | None = Form(default=None),
    quote_date: str | None = Form(default=None),
    valid_until: str | None = Form(default=None),
    title: str | None = Form(default=None),
    subtitle: str | None = Form(default=None),
    line_items_json: str | None = Form(default=None),
    included_work: str | None = Form(default=None),
    excluded_notes: str | None = Form(default=None),
    public_notes: str | None = Form(default=None),
    discount_percent: float | None = Form(default=None),
    manual_total: float | None = Form(default=None),
    subtotal_excl: float | None = Form(default=None),
    vat_rate_percent: float | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
    _subscription_guard: Tenant = Depends(require_active_subscription_for_write),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == str(current_user.tenant_id))
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    overrides = get_estimate_overrides(lead)
    estimate_dict: dict = {}
    raw_est = getattr(lead, "estimate_json", None)
    if isinstance(raw_est, str) and raw_est.strip():
        try:
            parsed = json.loads(raw_est)
            if isinstance(parsed, dict):
                estimate_dict = parsed
        except Exception:
            estimate_dict = {}

    old_html_key = getattr(lead, "estimate_html_key", None)
    has_json = bool(estimate_dict)
    logger.info(
        "EDIT_ESTIMATE_POST_START lead_id=%s old_html_key=%r has_estimate_json=%s",
        getattr(lead, "id", None),
        old_html_key,
        has_json,
    )

    editor_input = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "project_location": project_location,
        "company_name": company_name,
        "company_email": company_email,
        "company_phone": company_phone,
        "reference": reference,
        "quote_date": quote_date,
        "valid_until": valid_until,
        "title": title,
        "subtitle": subtitle,
        "line_items_json": line_items_json,
        "included_work": included_work,
        "excluded_notes": excluded_notes,
        "public_notes": public_notes,
        "discount_percent": discount_percent,
        "manual_total": manual_total,
        "subtotal_excl": subtotal_excl,
        "vat_rate_percent": vat_rate_percent,
    }
    estimate_dict, overrides, changed_fields = _apply_full_estimate_edit(
        lead=lead,
        estimate=estimate_dict,
        editor_input=editor_input,
        overrides=overrides,
    )

    logger.info(
        "[ESTIMATE_EDIT_DEBUG] estimate_id=%s fields_changed=%s",
        getattr(lead, "id", None),
        changed_fields,
    )

    lead.estimate_json = json.dumps(estimate_dict, ensure_ascii=False)
    lead.estimate_overrides_json = json.dumps(overrides, ensure_ascii=False)
    lead.updated_at = _utcnow()

    # If a manual total or discount is applied, also mark the intake payload
    # as manually overridden so future pipeline runs can skip AI-driven review.
    if overrides["manual_total"] is not None or overrides["discount_percent"] is not None:
        try:
            payload = {}
            raw_payload = getattr(lead, "intake_payload", None)
            if isinstance(raw_payload, str) and raw_payload.strip():
                payload = json.loads(raw_payload)
            elif isinstance(raw_payload, dict):
                payload = dict(raw_payload)

            payload["manual_override"] = True
            lead.intake_payload = json.dumps(payload, ensure_ascii=False)
        except Exception:
            # Non-fatal: if we can't update intake_payload, continue with overrides only.
            pass

    # Re-render quote HTML with overrides applied, if possible
    logger.info("[ESTIMATE_EDIT_DEBUG] estimate_id=%s rerender_started", getattr(lead, "id", None))
    new_html_key, rendered = render_quote_html_for_lead(lead, estimate_dict, overrides)
    if rendered and new_html_key:
        lead.estimate_html_key = new_html_key
    logger.info(
        "[ESTIMATE_EDIT_DEBUG] estimate_id=%s rerender_completed rendered=%s new_html_key=%r",
        getattr(lead, "id", None),
        rendered,
        new_html_key,
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    logger.info(
        "EDIT_ESTIMATE_POST_DONE lead_id=%s old_html_key=%r new_html_key=%r rendered=%s",
        getattr(lead, "id", None),
        old_html_key,
        getattr(lead, "estimate_html_key", None),
        rendered,
    )

    return RedirectResponse(url=f"/app/leads/{lead_id}/edit-estimate", status_code=303)
