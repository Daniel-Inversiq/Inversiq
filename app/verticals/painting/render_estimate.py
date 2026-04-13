# app/verticals/painting/render_estimate.py
from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.storage import get_storage
from app.verticals.painting.assumptions import PAINTLY_SCOPE_ASSUMPTIONS
from app.verticals.painting.copy import PAINTLY_ESTIMATE_COPY, fmt_qty
from app.verticals.painting.disclaimer import PAINTLY_ESTIMATE_DISCLAIMER
from app.verticals.painting.locale_eu import fmt_eur
from app.verticals.painting.needs_review import PAINTLY_NEEDS_REVIEW_COPY
from app.verticals.painting.review_labels import review_label_nl

TEMPLATE_DIR = Path(__file__).parent / "templates"
DEFAULT_VAT_RATE = 0.21
PROVISIONAL_MINIMUM_EXCL_VAT = Decimal("500.00")
MONEY_Q = Decimal("0.01")
logger = logging.getLogger(__name__)


def _d(x: Any) -> Decimal:
    if x is None:
        return Decimal("0.00")
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0.00")


def _money(x: Any) -> Decimal:
    return _d(x).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _as_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, tuple):
        return [str(x) for x in val]
    if isinstance(val, str):
        parts = [p.strip() for p in val.splitlines()]
        return [p for p in parts if p]
    return [str(val)]


def _compact_alnum(value: Any) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", txt)


def get_public_estimate_reference(estimate: Dict[str, Any]) -> str:
    """
    Build a short, customer-facing estimate reference.

    Priority:
    1) Existing short public code (e.g. F3F585).
    2) Any configured reference field if it is already compact.
    3) Fallback: last 6 alphanumeric chars from estimate/lead identifiers.
    """
    estimate = estimate or {}
    meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
    lead_obj = estimate.get("lead") if isinstance(estimate.get("lead"), dict) else {}

    short_candidates = [
        meta.get("public_reference"),
        meta.get("quote_reference"),
        meta.get("estimate_reference"),
        meta.get("reference"),
        estimate.get("public_reference"),
        estimate.get("quote_reference"),
        estimate.get("estimate_reference"),
        estimate.get("reference"),
    ]
    for c in short_candidates:
        compact = _compact_alnum(c).upper()
        if 4 <= len(compact) <= 10 and len(compact) <= 8:
            return compact

    id_candidates = [
        meta.get("estimate_id"),
        estimate.get("estimate_id"),
        meta.get("lead_id"),
        estimate.get("lead_id"),
        lead_obj.get("id"),
        estimate.get("id"),
    ]
    for raw in id_candidates:
        txt = str(raw or "").strip()
        if not txt:
            continue
        if txt.lower().startswith("lead_"):
            txt = txt[5:]
        compact = _compact_alnum(txt).upper()
        if len(compact) >= 6:
            return compact[-6:]
        if compact:
            return compact

    return "OFF000"


def _build_pdf_logo_data_url(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None
    url = str(raw_url).strip()
    if not url:
        return None
    if url.lower().startswith("data:"):
        return url

    try:
        parsed = urlparse(url)
        path_candidate = parsed.path or url
        storage = None

        # 1) Local/internal file endpoint: /files/{tenant_id}/{key...}
        #    Resolve through storage so this works for both local and S3 backends.
        files_marker = "/files/"
        marker_idx = path_candidate.find(files_marker)
        if marker_idx >= 0:
            files_part = path_candidate[marker_idx + len(files_marker) :].lstrip("/")
            parts = [p for p in files_part.split("/") if p]
            if len(parts) >= 2:
                tenant_id = parts[0]
                key = "/".join(parts[1:])
                try:
                    storage = storage or get_storage()
                    tmp_path = storage.download_to_temp_path(tenant_id=tenant_id, key=key)
                    tmp = Path(tmp_path)
                    image_bytes = tmp.read_bytes()
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                    if image_bytes:
                        content_type, _ = mimetypes.guess_type(key)
                        content_type = content_type or "image/png"
                        encoded = base64.b64encode(image_bytes).decode("ascii")
                        return f"data:{content_type};base64,{encoded}"
                except Exception:
                    pass

        # 2) Absolute/relative file path fallback.
        #    Useful for local dev or when logo_url is stored as filesystem path.
        direct_path = Path(url)
        if direct_path.exists() and direct_path.is_file():
            image_bytes = direct_path.read_bytes()
            if image_bytes:
                content_type, _ = mimetypes.guess_type(str(direct_path))
                content_type = content_type or "image/png"
                encoded = base64.b64encode(image_bytes).decode("ascii")
                return f"data:{content_type};base64,{encoded}"

        # 3) Remote URL fallback (http/https).
        if url.lower().startswith("http://") or url.lower().startswith("https://"):
            req = Request(url, headers={"User-Agent": "Paintly-PDF-Renderer/1.0"})
            with urlopen(req, timeout=8) as resp:
                content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
                image_bytes = resp.read()
            if image_bytes:
                if not content_type.startswith("image/"):
                    guessed_type, _ = mimetypes.guess_type(url)
                    content_type = guessed_type or "image/png"
                encoded = base64.b64encode(image_bytes).decode("ascii")
                return f"data:{content_type};base64,{encoded}"
    except Exception:
        return None
    return None


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    # template uses fmt_eur + fmt_qty
    env.globals["fmt_eur"] = fmt_eur
    env.globals["fmt_qty"] = fmt_qty
    env.globals["review_label_nl"] = review_label_nl
    return env


def _pick_vat_rate(pricing: Dict[str, Any]) -> Decimal:
    # allow override later via pricing["vat_rate"] or pricing["tax_rate"]
    v = pricing.get("vat_rate")
    if v is None:
        v = pricing.get("tax_rate")
    if v is None:
        v = DEFAULT_VAT_RATE
    return _d(v)


def _calc_vat(pricing: Dict[str, Any]) -> Dict[str, float]:
    """
    Your estimate_json already contains:
      totals.pre_tax
      totals.grand_total (usually same for now)
    We compute VAT from totals.pre_tax (excl btw).
    """
    totals = pricing.get("totals") if isinstance(pricing.get("totals"), dict) else {}
    pre_tax = totals.get("pre_tax")

    subtotal_excl = _money(pre_tax)

    # bulletproof fallback
    if subtotal_excl <= 0:
        subtotal_excl = PROVISIONAL_MINIMUM_EXCL_VAT

    vat_rate = _pick_vat_rate(pricing)
    vat_amount = _money(subtotal_excl * vat_rate)
    total_incl = _money(subtotal_excl + vat_amount)

    return {
        "subtotal_excl_vat": float(subtotal_excl),
        "vat_rate": float(vat_rate),
        "vat_amount": float(vat_amount),
        "total_incl_vat": float(total_incl),
    }


def render_estimate_html_v2(
    *,
    pricing: Dict[str, Any],
    project: Dict[str, Any],
    company: Dict[str, Any],
    branding_company_name: Optional[str] = None,
    branding_logo_url: Optional[str] = None,
    lead: Optional[Dict[str, Any]] = None,
    customer: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    scope_bullets: Optional[List[str]] = None,
    exclusions: Optional[List[str]] = None,
) -> str:
    pricing = pricing or {}

    # pricing_ready: treat as ready unless explicitly flagged for review
    meta = pricing.get("meta") if isinstance(pricing.get("meta"), dict) else {}

    # NEW canonical fields (from pricing_engine patch)
    needs_review_raw = pricing.get("needs_review", None)
    if needs_review_raw is None:
        needs_review_raw = meta.get("needs_review", False)
    needs_review_flag = bool(needs_review_raw)

    review_reasons = pricing.get("review_reasons")
    if review_reasons is None:
        # backwards compat (older meta key)
        review_reasons = (
            meta.get("needs_review_reasons") or meta.get("review_reasons") or []
        )
    if isinstance(review_reasons, str):
        review_reasons = [review_reasons]
    elif not isinstance(review_reasons, list):
        review_reasons = [str(review_reasons)]

    # ensure list[str]
    review_reasons = [str(x) for x in review_reasons if x is not None]
    review_reasons_display = [review_label_nl(x) for x in review_reasons]

    # scope + exclusions blocks
    if scope_bullets is None:
        scope_bullets = _as_list(getattr(PAINTLY_SCOPE_ASSUMPTIONS, "included", None))
    if not scope_bullets:
        scope_bullets = [
            "Voorbereiding van oppervlakken waar nodig (licht schuren/bijwerken).",
            "Aanbrengen van afwerklagen op de genoemde oppervlakken.",
            "Standaard afplakken/beschermen en oplever-schoonmaak.",
        ]

    if exclusions is None:
        exclusions = _as_list(getattr(PAINTLY_ESTIMATE_DISCLAIMER, "bullets", None))

    # buckets shown in sidebar
    subtotals = (
        pricing.get("subtotals") if isinstance(pricing.get("subtotals"), dict) else {}
    )
    pricing_labor = float(_money(subtotals.get("labor")))
    pricing_materials = float(_money(subtotals.get("materials")))

    # Explainability (Step B)
    decision_vars = pricing.get("decision_vars")
    if decision_vars is None and isinstance(meta.get("decision_vars"), dict):
        decision_vars = meta.get("decision_vars")

    # Optional: for template: show on sidebar or "Assumptions"
    assumptions_ctx = {
        "prep_level": (decision_vars or {}).get("prep_level"),
        "complexity_level": (decision_vars or {}).get("complexity_level"),
        "access_risk": (decision_vars or {}).get("access_risk"),
        "review_reasons": review_reasons_display,
        "needs_review": needs_review_flag,
    }

    # If an explicit override_total_incl_vat is present in meta, recompute VAT from that.
    override_total = None
    try:
        if isinstance(meta, dict) and meta.get("override_total_incl_vat") is not None:
            override_total = _money(meta.get("override_total_incl_vat"))
    except Exception:
        override_total = None

    if override_total is not None and override_total > 0:
        # Reverse-calc VAT components from override_total
        vat_rate = _pick_vat_rate(pricing)
        one_plus = Decimal("1") + vat_rate
        subtotal_excl = (override_total / one_plus).quantize(
            MONEY_Q, rounding=ROUND_HALF_UP
        )
        vat_amount = (override_total - subtotal_excl).quantize(
            MONEY_Q, rounding=ROUND_HALF_UP
        )
        vat = {
            "subtotal_excl_vat": float(subtotal_excl),
            "vat_rate": float(vat_rate),
            "vat_amount": float(vat_amount),
            "total_incl_vat": float(override_total),
        }
    else:
        vat = _calc_vat(pricing)

    total_price = vat.get("total_incl_vat") if isinstance(vat, dict) else None
    lead_status = str(
        (
            ((lead or {}).get("status") if isinstance(lead, dict) else None)
            or pricing.get("lead_status")
            or meta.get("lead_status")
            or ""
        )
    ).upper()
    has_final_total = bool(total_price is not None and float(total_price) > 0)
    price_mode = str(
        pricing.get("price_mode")
        or (meta.get("price_mode") if isinstance(meta, dict) else None)
        or ("priced" if (has_final_total and not needs_review_flag) else "tbd")
    ).lower()
    NON_BLOCKING_RENDER_REASONS = {"surface_preparation_required"}
    blocking_review_reasons = [
        r for r in review_reasons if r not in NON_BLOCKING_RENDER_REASONS
    ]
    # Render guard: when a definitive total exists and only non-blocking prep
    # reasons remain, force priced/SUCCEEDED presentation.
    if has_final_total and (not blocking_review_reasons):
        if not lead_status:
            lead_status = "SUCCEEDED"
        if price_mode != "priced":
            price_mode = "priced"
    if lead_status == "SUCCEEDED" and price_mode == "priced" and has_final_total:
        needs_review_flag = False

    # Final template-facing toggles (derived after all normalizations above).
    pricing_ready = not needs_review_flag
    is_provisional = needs_review_flag

    show_prices = not needs_review_flag

    # Debug: log final pricing/meta/vat snapshot before templating
    try:
        from app.verticals.painting.router_app import logger as paintly_logger  # type: ignore
    except Exception:
        paintly_logger = None

    if paintly_logger:
        try:
            paintly_logger.info(
                "RENDER_ESTIMATE_HTML_V2_SNAPSHOT totals=%r meta=%r vat=%r",
                pricing.get("totals"),
                meta,
                vat,
            )
            paintly_logger.info(
                "QUOTE_OUTPUT_DECISION lead_id=%s needs_review=%s lead_status=%s pricing_status=%s total_price=%r price_mode=%s template=%s review_page=%s show_prices=%s pricing_ready=%s is_provisional=%s review_reasons=%r",
                ((lead or {}).get("id") if isinstance(lead, dict) else None),
                needs_review_flag,
                ((lead or {}).get("status") if isinstance(lead, dict) else None),
                "render_estimate_html_v2",
                total_price,
                price_mode,
                "estimate.html",
                bool(needs_review_flag),
                show_prices,
                pricing_ready,
                is_provisional,
                review_reasons,
            )
            paintly_logger.info(
                "WEB_ESTIMATE_RENDER_CONTEXT lead_id=%s needs_review_flag=%s show_prices=%s lead_status=%s price_mode=%s total_price=%r review_reasons=%r",
                ((lead or {}).get("id") if isinstance(lead, dict) else None),
                needs_review_flag,
                show_prices,
                lead_status,
                price_mode,
                total_price,
                review_reasons,
            )
        except Exception:
            pass

    tmpl = _jinja_env().get_template("estimate.html")
    html = tmpl.render(
        is_public=False,
        pricing_ready=pricing_ready,
        pricing=pricing,  # template uses pricing.line_items, pricing.meta, pricing.subtotals, pricing.totals
        vat=vat,
        pricing_labor=pricing_labor,
        pricing_materials=pricing_materials,
        copy=PAINTLY_ESTIMATE_COPY,
        scope_bullets=scope_bullets,
        exclusions=exclusions,
        project=project,
        company=company,
        branding_company_name=branding_company_name,
        branding_logo_url=branding_logo_url,
        lead=lead or {},
        customer=customer or {},
        token=token,
        needs_review_flag=needs_review_flag,
        review_reasons=review_reasons_display,
        lead_status=lead_status,
        price_mode=price_mode,
        total_price=total_price,
        decision_vars=decision_vars or {},
        assumptions_ctx=assumptions_ctx,
        show_prices=show_prices,
        is_provisional=is_provisional,
    )

    # Guard: avoid serving unrendered template content
    if "{{" in html or "{%" in html:
        raise RuntimeError("Estimate HTML still contains Jinja tags.")
    return html


# -------------------------
# Pipeline compatibility wrapper
# -------------------------
def render_estimate_html(estimate: Dict[str, Any]) -> str:
    """
    Pipeline calls: render_estimate_html(estimate_json_dict) -> html
    Here `estimate` is already your canonical pricing output schema dict.
    """
    estimate = estimate or {}
    if not isinstance(estimate, dict):
        raise TypeError("estimate must be dict")

    pricing = estimate  # <-- key change: template reads pricing.* directly

    meta = pricing.get("meta") if isinstance(pricing.get("meta"), dict) else {}

    title = (
        (meta.get("title") if isinstance(meta, dict) else None)
        or estimate.get("title")
        or "Offerte schilderwerk"
    )
    subtitle = (
        (meta.get("subtitle") if isinstance(meta, dict) else None)
        or (meta.get("intro") if isinstance(meta, dict) else None)
        or estimate.get("subtitle")
        or ""
    )
    reference = get_public_estimate_reference(estimate)
    project = {
        "lead_id": meta.get("lead_id") or estimate.get("lead_id"),
        "estimate_id": meta.get("estimate_id") or estimate.get("estimate_id"),
        "location": estimate.get("location") or "—",
        "date": meta.get("date"),
        "valid_until": meta.get("valid_until"),
        "square_meters": meta.get("area_m2") or estimate.get("square_meters"),
        "description": estimate.get("description"),
        "address": estimate.get("address") or meta.get("address"),
        "title": title,
        "subtitle": subtitle,
        "reference": reference,
    }

    company = estimate.get("company") or estimate.get("tenant") or {}
    branding_company_name = (
        estimate.get("branding_company_name")
        if isinstance(estimate.get("branding_company_name"), str)
        else None
    )
    branding_company_name = (branding_company_name or "").strip() or "Inversiq"
    branding_logo_url = (
        estimate.get("branding_logo_url")
        if isinstance(estimate.get("branding_logo_url"), str)
        else None
    )
    branding_logo_url = (branding_logo_url or "").strip() or None
    lead = estimate.get("lead") or {}
    customer = estimate.get("customer") or {}
    # Stored estimate HTML is shown in dashboard preview and inside the public /e iframe.
    # Customer accept/reject lives on public/customer_quote_page only — never embed public CTAs here.
    token = None

    included_override = estimate.get("included_work") or meta.get("included_work")
    excluded_override = estimate.get("excluded_notes") or meta.get("excluded_notes")
    public_notes = estimate.get("public_notes") or meta.get("public_notes")
    if isinstance(public_notes, str) and public_notes.strip():
        estimate = dict(estimate)
        estimate["public_notes"] = public_notes.strip()

    if included_override is not None:
        if isinstance(included_override, str):
            scope_override = [p.strip() for p in included_override.splitlines() if p.strip()]
        elif isinstance(included_override, list):
            scope_override = [str(p) for p in included_override if str(p).strip()]
        else:
            scope_override = [str(included_override)]
    else:
        scope_override = None

    if excluded_override is not None:
        if isinstance(excluded_override, str):
            exclusions_override = [p.strip() for p in excluded_override.splitlines() if p.strip()]
        elif isinstance(excluded_override, list):
            exclusions_override = [str(p) for p in excluded_override if str(p).strip()]
        else:
            exclusions_override = [str(excluded_override)]
    else:
        exclusions_override = None

    return render_estimate_html_v2(
        pricing=pricing,
        project=project,
        company=company,
        branding_company_name=branding_company_name,
        branding_logo_url=branding_logo_url,
        lead=lead,
        customer=customer,
        token=token,
        scope_bullets=scope_override,
        exclusions=exclusions_override,
    )


def render_estimate_pdf_html(estimate: Dict[str, Any]) -> str:
    """
    Dedicated PDF-friendly HTML renderer for WeasyPrint.

    Uses a simpler, document-style template (estimate_pdf.html) instead of the
    web-optimized dashboard template.
    """
    estimate = estimate or {}
    if not isinstance(estimate, dict):
        raise TypeError("estimate must be dict")

    pricing = estimate
    meta = pricing.get("meta") if isinstance(pricing.get("meta"), dict) else {}

    title = (
        (meta.get("title") if isinstance(meta, dict) else None)
        or estimate.get("title")
        or "Offerte schilderwerk"
    )
    subtitle = (
        (meta.get("subtitle") if isinstance(meta, dict) else None)
        or (meta.get("intro") if isinstance(meta, dict) else None)
        or estimate.get("subtitle")
        or ""
    )
    reference = get_public_estimate_reference(estimate)
    project = {
        "lead_id": meta.get("lead_id") or estimate.get("lead_id"),
        "estimate_id": meta.get("estimate_id") or estimate.get("estimate_id"),
        "location": estimate.get("location") or "—",
        "date": meta.get("date"),
        "valid_until": meta.get("valid_until"),
        "square_meters": meta.get("area_m2") or estimate.get("square_meters"),
        "description": estimate.get("description"),
        "address": estimate.get("address") or meta.get("address"),
        "title": title,
        "subtitle": subtitle,
        "reference": reference,
    }

    company = estimate.get("company") or estimate.get("tenant") or {}
    lead = estimate.get("lead") or {}
    customer = estimate.get("customer") or {}
    token = estimate.get("token")
    branding_company_name = (
        estimate.get("branding_company_name")
        if isinstance(estimate.get("branding_company_name"), str)
        else None
    )
    branding_company_name = (branding_company_name or "").strip() or None
    branding_logo_url = (
        estimate.get("branding_logo_url")
        if isinstance(estimate.get("branding_logo_url"), str)
        else None
    )
    branding_logo_url = (branding_logo_url or "").strip() or None
    branding_logo_data_url = _build_pdf_logo_data_url(branding_logo_url)
    logger.info(
        "[PDF_LOGO_DEBUG] raw_url=%r data_url_created=%s",
        branding_logo_url,
        bool(branding_logo_data_url),
    )

    pricing = pricing or {}
    pdf_pricing = pricing  # reuse existing helpers

    # Reuse existing computation helpers from render_estimate_html_v2
    meta = pdf_pricing.get("meta") if isinstance(pdf_pricing.get("meta"), dict) else {}
    needs_review_flag = bool(pdf_pricing.get("needs_review", False))
    review_reasons = pdf_pricing.get("review_reasons")
    if review_reasons is None:
        review_reasons = (
            meta.get("needs_review_reasons") or meta.get("review_reasons") or []
        )
    if isinstance(review_reasons, str):
        review_reasons = [review_reasons]
    elif not isinstance(review_reasons, list):
        review_reasons = [str(review_reasons)]
    review_reasons = [str(x) for x in review_reasons if x is not None]
    review_reasons_display = [review_label_nl(x) for x in review_reasons]
    pricing_ready = not needs_review_flag

    included_override = estimate.get("included_work") or meta.get("included_work")
    if included_override is not None:
        scope_bullets = _as_list(included_override)
    else:
        scope_bullets = _as_list(getattr(PAINTLY_SCOPE_ASSUMPTIONS, "included", None))
    if not scope_bullets:
        scope_bullets = [
            "Voorbereiding van oppervlakken waar nodig (licht schuren/bijwerken).",
            "Aanbrengen van afwerklagen op de genoemde oppervlakken.",
            "Standaard afplakken/beschermen en oplever-schoonmaak.",
        ]

    excluded_override = estimate.get("excluded_notes") or meta.get("excluded_notes")
    if excluded_override is not None:
        exclusions = _as_list(excluded_override)
    else:
        exclusions = _as_list(getattr(PAINTLY_ESTIMATE_DISCLAIMER, "bullets", None))

    subtotals = (
        pdf_pricing.get("subtotals")
        if isinstance(pdf_pricing.get("subtotals"), dict)
        else {}
    )
    pricing_labor = float(_money(subtotals.get("labor")))
    pricing_materials = float(_money(subtotals.get("materials")))

    decision_vars = pdf_pricing.get("decision_vars")
    if decision_vars is None and isinstance(meta.get("decision_vars"), dict):
        decision_vars = meta.get("decision_vars")

    assumptions_ctx = {
        "prep_level": (decision_vars or {}).get("prep_level"),
        "complexity_level": (decision_vars or {}).get("complexity_level"),
        "access_risk": (decision_vars or {}).get("access_risk"),
        "review_reasons": review_reasons_display,
        "needs_review": needs_review_flag,
    }

    override_total = None
    try:
        if isinstance(meta, dict) and meta.get("override_total_incl_vat") is not None:
            override_total = _money(meta.get("override_total_incl_vat"))
    except Exception:
        override_total = None

    if override_total is not None and override_total > 0:
        vat_rate = _pick_vat_rate(pdf_pricing)
        one_plus = Decimal("1") + vat_rate
        subtotal_excl = (override_total / one_plus).quantize(
            MONEY_Q, rounding=ROUND_HALF_UP
        )
        vat_amount = (override_total - subtotal_excl).quantize(
            MONEY_Q, rounding=ROUND_HALF_UP
        )
        vat = {
            "subtotal_excl_vat": float(subtotal_excl),
            "vat_rate": float(vat_rate),
            "vat_amount": float(vat_amount),
            "total_incl_vat": float(override_total),
        }
    else:
        vat = _calc_vat(pdf_pricing)

    pricing_ready = not needs_review_flag
    is_provisional = needs_review_flag
    show_prices = not needs_review_flag

    tmpl = _jinja_env().get_template("estimate_pdf.html")
    html = tmpl.render(
        pricing_ready=pricing_ready,
        pricing=pdf_pricing,
        vat=vat,
        pricing_labor=pricing_labor,
        pricing_materials=pricing_materials,
        copy=PAINTLY_ESTIMATE_COPY,
        needs_review=PAINTLY_NEEDS_REVIEW_COPY,
        scope_bullets=scope_bullets,
        exclusions=exclusions,
        project=project,
        company=company,
        branding_company_name=branding_company_name,
        branding_logo_data_url=branding_logo_data_url,
        branding_logo_url=branding_logo_url,
        lead=lead or {},
        customer=customer or {},
        token=token,
        needs_review_flag=needs_review_flag,
        review_reasons=review_reasons_display,
        decision_vars=decision_vars or {},
        assumptions_ctx=assumptions_ctx,
        show_prices=show_prices,
        is_provisional=is_provisional,
    )

    if "{{" in html or "{%" in html:
        raise RuntimeError("Estimate PDF HTML still contains Jinja tags.")
    return html
