from __future__ import annotations

import datetime as dt
import json
import logging
import re
import uuid
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from aether.engine.config import StepConfig
from aether.engine.context import PipelineState, StepResult

from decimal import Decimal, InvalidOperation

from app.models import Lead, LeadFile, Tenant
from app.models.user import User
from app.models.upload_record import UploadRecord, UploadStatus
from app.services.branding import (
    branding_html_debug_summary,
    is_custom_branding_allowed,
    log_branding_state,
    normalize_plan,
)
from app.services.photo_quality.inference import predict_photo_quality
from app.services.tenant_pricing import apply_paintly_tenant_pricing_overrides
from app.services.storage import get_storage
from app.tasks.vision_task import run_vision_for_lead
from app.verticals.paintly.render_estimate import render_estimate_html
from app.verticals.paintly.pricing_engine_us import (
    run_pricing_engine,
    load_rules_default,
)
from app.verticals.paintly.pricing_output_builder import build_pricing_output
from app.verticals.paintly.vision_aggregate_us import (
    aggregate_images_to_surfaces as aggregate_vision,
)

logger = logging.getLogger(__name__)

# Review reason codes that may appear in merged output but must not alone force
# NEEDS_REVIEW when pricing/totals are otherwise valid (priced output path).
NON_BLOCKING_REVIEW_REASONS = frozenset(
    {
        "surface_preparation_required",
        "few_images_low_confidence",
        "low_overall_confidence",
        "wall_repair_or_wallpaper_likely",
    }
)


def _reason_is_non_blocking(r: object) -> bool:
    s = str(r or "").strip()
    if s in NON_BLOCKING_REVIEW_REASONS:
        return True
    if s.startswith("vision:") and s[7:].strip() in NON_BLOCKING_REVIEW_REASONS:
        return True
    return False


def _ensure_obj(x: Any) -> Any:
    """
    If a stage accidentally returns JSON as a string, parse it back to dict/list.
    Keeps non-JSON strings untouched.
    """
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return x
    return x


# -------------------------
# Defaults for template context (1.5.5)
# -------------------------
def _default_company() -> Dict[str, Any]:
    return {"name": "Paintly", "phone": "", "email": ""}


def _default_copy() -> Dict[str, Any]:
    return {
        "doc_title": "Concept offerte – schilderwerk",
        "scope_label": "Werkzaamheden",
        "exclusions_label": "Niet inbegrepen",
        "labor_label": "Arbeid",
        "materials_label": "Materialen",
    }


def _default_scope_bullets() -> List[str]:
    return [
        "Bescherming van vloeren en omliggende oppervlakken",
        "Standaard voorbereiding (licht schuren waar nodig)",
        "Twee verflagen waar nodig",
        "Opruimen en afvoeren van licht afval",
    ]


def _default_exclusions() -> List[str]:
    return [
        "Groot herstelwerk aan muren of hout",
        "Schimmelbehandeling",
        "Verplaatsen van zware meubels",
    ]


def _looks_like_image(object_key: str) -> bool:
    key = (object_key or "").lower()
    return key.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic"))


def _is_nonzero_money(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, Decimal):
        return x > Decimal("0.00")
    if isinstance(x, (int, float)):
        return float(x) > 0
    if isinstance(x, str):
        s = x.strip().replace("$", "").replace(",", "")
        try:
            return float(s) > 0
        except Exception:
            return False
    return False


# -------------------------
# Step: photo quality (guardrail)
# -------------------------
def step_photo_quality_v1(
    state: PipelineState, step: StepConfig, assets: dict
) -> StepResult:
    """
    Photo quality guardrail.
    IMPORTANT: For MVP we do NOT hard-stop the pipeline here.
    We mark bad photos via step data + meta reasons, and let step_needs_review_v1
    combine reasons into the final outcome.
    """
    lead: Lead = assets["lead"]
    db: Session = assets["db"]

    rows = (
        db.query(UploadRecord)
        .filter(UploadRecord.tenant_id == lead.tenant_id)
        .filter(UploadRecord.lead_id == lead.id)
        .filter(UploadRecord.status.in_([UploadStatus.uploaded, "uploaded"]))
        .all()
    )

    logger.info(
        "PHOTO_QUALITY rows=%s lead_id=%s tenant_id=%s",
        len(rows),
        getattr(lead, "id", None),
        getattr(lead, "tenant_id", None),
    )
    if rows:
        r0 = rows[0]
        logger.info(
            "PHOTO_QUALITY sample mime=%s status=%s key=%s",
            getattr(r0, "mime", None),
            getattr(r0, "status", None),
            getattr(r0, "object_key", None),
        )

    image_refs: List[str] = []
    seen_refs: set[str] = set()
    for r in rows:
        ok_mime = isinstance(r.mime, str) and r.mime.startswith("image/")
        ok_ext = _looks_like_image(getattr(r, "object_key", "") or "")
        if ok_mime or ok_ext:
            if isinstance(r.object_key, str) and r.object_key:
                if r.object_key not in seen_refs:
                    seen_refs.add(r.object_key)
                    image_refs.append(r.object_key)

    # Real intake flow can have LeadFile rows without UploadRecord linkage yet.
    # Fall back to LeadFile.s3_key so photo-quality analyzes the same images
    # that the vision step already uses successfully.
    if not image_refs:
        lf_rows = db.query(LeadFile).filter(LeadFile.lead_id == lead.id).all()
        for lf in lf_rows:
            key = getattr(lf, "s3_key", None)
            if isinstance(key, str) and key and _looks_like_image(key):
                if key not in seen_refs:
                    seen_refs.add(key)
                    image_refs.append(key)

    logger.info("PHOTO_QUALITY image_refs=%s", len(image_refs))

    if not image_refs:
        reasons = ["no_photos"]
        return StepResult(
            status="OK",
            data={
                "photo_quality": {
                    "quality": "bad",
                    "score_bad": 1.0,
                    "reasons": reasons,
                    "bad": True,
                    "n_images": 0,
                }
            },
            meta={"reasons": reasons},
        )

    storage = get_storage()
    tenant_id = str(getattr(lead, "tenant_id", ""))

    min_confidence = 0.70
    min_quality_score = 0.60
    # Confidence threshold for triggering manual review.
    # Below this threshold => hard review trigger.
    # Between this threshold and `min_confidence` => soft diagnostic only.
    PHOTO_REVIEW_CONFIDENCE_THRESHOLD = 0.60
    # Quality threshold for hard review. Between this threshold and
    # `min_quality_score` stays a soft warning only.
    PHOTO_REVIEW_QUALITY_THRESHOLD = 0.45
    try:
        # Engine config stores step options in `with`; parsed StepConfig exposes
        # that as `with_`. Keep optional `params` fallback for compatibility.
        step_opts = getattr(step, "with_", None) or getattr(step, "params", None) or {}
        if isinstance(step_opts, dict):
            if step_opts.get("min_confidence") is not None:
                min_confidence = float(step_opts["min_confidence"])
            if step_opts.get("min_quality_score") is not None:
                min_quality_score = float(step_opts["min_quality_score"])
    except Exception:
        pass

    res = predict_photo_quality(
        image_refs=image_refs,
        storage=storage,
        tenant_id=tenant_id,
    )

    validation = {
        "relevant": bool(res.relevant),
        "quality_score": float(res.quality_score or 0.0),
        "confidence": float(res.confidence or 0.0),
        "issues": list(res.issues or []),
    }
    review_reasons: List[str] = []
    hard_review_required = False
    if not validation["relevant"]:
        review_reasons.append("photo_not_relevant")
        hard_review_required = True

    photo_confidence = float(validation["confidence"] or 0.0)
    if photo_confidence < min_confidence:
        if photo_confidence < PHOTO_REVIEW_CONFIDENCE_THRESHOLD:
            review_reasons.append("photo_validation_low_confidence")
            hard_review_required = True
        else:
            # Soft diagnostic only: keep in reasons/logs but do not
            # auto-escalate to NEEDS_REVIEW.
            review_reasons.append("photo_validation_low_confidence_soft")

    photo_quality_score = float(validation["quality_score"] or 0.0)
    if photo_quality_score < min_quality_score:
        if photo_quality_score < PHOTO_REVIEW_QUALITY_THRESHOLD:
            review_reasons.append("photo_quality_score_low")
            hard_review_required = True
        else:
            review_reasons.append("photo_quality_score_low_soft")

    # Keep existing behavior for actual photo-quality issues.
    issues = list(validation.get("issues") or [])
    if issues:
        hard_review_required = True
    review_reasons.extend(issues)
    review_required = bool(hard_review_required)

    return StepResult(
        status="OK",
        data={
            "photo_quality": {
                # New validation response shape
                "validation": validation,
                # Backward-compatible aliases for existing callers
                "quality": "good" if validation["quality_score"] >= 0.6 else "bad",
                "score_bad": float(max(0.0, min(1.0, 1.0 - validation["quality_score"]))),
                "reasons": review_reasons,
                "bad": bool(review_required),
                # Explicit routing signal for downstream review logic
                "review_required": review_required,
                "review_reasons": review_reasons,
                "n_images": len(image_refs),
            }
        },
        meta={"reasons": review_reasons},
    )


# -------------------------
# Step: vision
# -------------------------
def step_vision_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    db: Session = assets["db"]
    lead: Lead = assets["lead"]

    vision_raw = run_vision_for_lead(db, lead.id)
    vision_raw = _ensure_obj(vision_raw)

    return StepResult(status="OK", data={"vision_raw": vision_raw})


# -------------------------
# Step: aggregate
# -------------------------
def step_aggregate_v1(
    state: PipelineState, step: StepConfig, assets: dict
) -> StepResult:
    db: Session = assets["db"]
    lead: Lead = assets["lead"]

    vision_raw = (state.data.get("steps") or {}).get("vision", {}).get("vision_raw")
    vision_raw = _ensure_obj(vision_raw)

    # `run_vision_for_lead` (new OpenAI provider) returns a wrapper dict:
    # - image_predictions: legacy compat shape (issues/substrate_confidence)
    # - lead_aggregate: source-of-truth for needs_review + review_reasons (incl. surface_preparation_required)
    # Paintly aggregate heuristics operate on `image_predictions`, so we unwrap
    # for pricing variables, but we keep `lead_aggregate.review_reasons` to
    # drive the final review routing.
    raw_aggregate_needs_review = None
    raw_aggregate_review_reasons = None
    raw_file_skip_reasons = None
    if isinstance(vision_raw, dict):
        lead_aggregate = (
            vision_raw.get("lead_aggregate")
            if isinstance(vision_raw.get("lead_aggregate"), dict)
            else None
        )

        # Prefer wrapper keys, fallback to lead_aggregate keys.
        raw_aggregate_needs_review = vision_raw.get("needs_review", None)
        if raw_aggregate_needs_review is None and isinstance(lead_aggregate, dict):
            raw_aggregate_needs_review = lead_aggregate.get("needs_review", None)

        raw_aggregate_review_reasons = vision_raw.get("review_reasons", None)
        if raw_aggregate_review_reasons is None and isinstance(lead_aggregate, dict):
            raw_aggregate_review_reasons = lead_aggregate.get("review_reasons", None)
        raw_file_skip_reasons = vision_raw.get("file_skip_reasons", None)

        logger.info(
            "RAW_VISION_AGGREGATE lead_id=%s needs_review=%r review_reasons=%r file_skip_reasons=%r",
            getattr(lead, "id", None),
            raw_aggregate_needs_review,
            raw_aggregate_review_reasons,
            raw_file_skip_reasons,
        )

        # Unwrap to the list expected by paintly aggregate_vision.
        image_predictions = vision_raw.get("image_predictions")
        if image_predictions is not None:
            vision_raw = _ensure_obj(image_predictions)

    # --- area ophalen uit intake_payload of lead.square_meters ---
    estimated_area_m2 = None
    try:
        raw = getattr(lead, "intake_payload", None)
        payload = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
        if isinstance(payload, dict):
            v = (
                payload.get("square_meters")
                or payload.get("area_m2")
                or payload.get("sqm")
            )
            if v is not None:
                estimated_area_m2 = float(v)
    except Exception:
        pass

    if estimated_area_m2 is None:
        try:
            v = getattr(lead, "square_meters", None)
            if v is not None:
                estimated_area_m2 = float(v)
        except Exception:
            pass

    # scope (MVP default)
    scope = {
        "interior": True,
        "paint_walls": True,
        "paint_ceiling": False,
        "paint_trim": False,
    }

    # ✅ nu wél correct
    vision = aggregate_vision(
        vision_raw,
        estimated_area_m2=estimated_area_m2,
        scope=scope,
    )
    vision = _ensure_obj(vision)

    # Merge vision provider review flags from `lead_aggregate` back into the
    # paintly aggregate output (so needs_review routing matches validate/debug).
    if isinstance(vision, dict):
        if raw_aggregate_needs_review is not None:
            vision["needs_review"] = bool(
                vision.get("needs_review", False) or raw_aggregate_needs_review
            )

        if raw_aggregate_review_reasons is not None:
            rr = raw_aggregate_review_reasons
            if not isinstance(rr, list):
                rr = [rr]
            rr = [str(x) for x in rr if x is not None and str(x).strip()]

            existing = vision.get("review_reasons") or []
            if not isinstance(existing, list):
                existing = [existing]
            existing = [str(x) for x in existing if x is not None]

            vision["review_reasons"] = list(dict.fromkeys(existing + rr))

        # Ingest hard-signal bridge:
        # if upload/source resolution shows MIME/content-type uncertainty,
        # surface one explicit reason for final review decisioning.
        skip_reasons = raw_file_skip_reasons
        if not isinstance(skip_reasons, list):
            skip_reasons = [skip_reasons] if skip_reasons is not None else []
        skip_reasons_txt = [str(x).lower() for x in skip_reasons if x is not None]
        upload_mime_unverified = any(
            ("non_image_mime" in txt)
            or ("bad_content_type" in txt)
            for txt in skip_reasons_txt
        )
        if upload_mime_unverified:
            existing = vision.get("review_reasons") or []
            if not isinstance(existing, list):
                existing = [existing]
            existing = [str(x) for x in existing if x is not None]
            vision["review_reasons"] = list(
                dict.fromkeys(existing + ["upload_mime_unverified"])
            )
            vision["needs_review"] = True

    return StepResult(status="OK", data={"vision": vision})


# -------------------------
# Step: pricing (rules injected)
# -------------------------
def step_pricing_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    lead: Lead = assets["lead"]
    db: Session = assets["db"]
    rules = assets.get("rules") if isinstance(assets, dict) else None

    vision = (state.data.get("steps") or {}).get("aggregate", {}).get("vision")
    vision = _ensure_obj(vision)

    # Always make sure rules is a dict
    base_rules = _ensure_obj(rules) if rules is not None else load_rules_default()
    if not isinstance(base_rules, dict):
        base_rules = load_rules_default()

    # Load tenant explicitly from DB (do not rely on lead.tenant relationship)
    tenant = None
    try:
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == getattr(lead, "tenant_id", None))
            .first()
        )
    except Exception:
        tenant = None

    effective_rules = apply_paintly_tenant_pricing_overrides(base_rules, tenant)

    try:
        logger.info(
            "PAINTLY_PRICING tenant_id=%s tenant_pricing=%s default_walls_rate=%s effective_walls_rate=%s",
            getattr(lead, "tenant_id", None),
            getattr(tenant, "pricing_json", None) if tenant else None,
            ((base_rules or {}).get("base_rates") or {})
            .get("walls", {})
            .get("rate_eur"),
            ((effective_rules or {}).get("base_rates") or {})
            .get("walls", {})
            .get("rate_eur"),
        )
    except Exception:
        pass

    pricing = run_pricing_engine(lead, vision, rules=effective_rules)
    pricing = _ensure_obj(pricing)

    return StepResult(status="OK", data={"pricing": pricing})


# -------------------------
# Step: output (canonical PricingOutput dict)
# -------------------------
def step_output_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    lead: Lead = assets["lead"]
    db: Session = assets["db"]

    vision = (state.data.get("steps") or {}).get("aggregate", {}).get("vision")
    pricing = (state.data.get("steps") or {}).get("pricing", {}).get("pricing")
    vision = _ensure_obj(vision)
    pricing = _ensure_obj(pricing)

    try:
        logger.info(
            "PRICING_RAW_FOR_OUTPUT lead_id=%s pricing=%s",
            getattr(lead, "id", None),
            pricing,
        )
    except Exception:
        pass

    estimate = build_pricing_output(lead, vision, pricing)
    estimate = _ensure_obj(estimate)
    if not isinstance(estimate, dict):
        estimate = {}

    try:
        tenant_row = (
            db.query(Tenant).filter(Tenant.id == getattr(lead, "tenant_id", None)).first()
        )
        tenant_user = (
            db.query(User)
            .filter(
                User.tenant_id == str(getattr(lead, "tenant_id", "")),
                User.is_active == True,  # noqa: E712
            )
            .order_by(User.created_at.desc(), User.id.desc())
            .first()
        )

        plan_raw = getattr(tenant_row, "plan_code", None) if tenant_row is not None else None
        plan_normalized = normalize_plan(plan_raw)
        branding_allowed = is_custom_branding_allowed(plan_raw)

        user_company_name = (
            (getattr(tenant_user, "company_name", None) or "").strip()
            if tenant_user is not None
            else ""
        )
        tenant_company_name = (
            (getattr(tenant_row, "company_name", None) or "").strip()
            if tenant_row is not None
            else ""
        )
        user_logo_url = (
            (getattr(tenant_user, "logo_url", None) or "").strip()
            if tenant_user is not None
            else ""
        )
        tenant_logo_url = (
            (getattr(tenant_row, "logo_url", None) or "").strip()
            if tenant_row is not None
            else ""
        )

        chosen_custom_name = user_company_name or tenant_company_name
        chosen_custom_logo = user_logo_url or tenant_logo_url
        branding_source = "default"
        fallback_reason = None
        if branding_allowed and chosen_custom_name:
            branding_company_name = chosen_custom_name
            branding_logo_url = chosen_custom_logo or None
            branding_source = "user" if user_company_name else "tenant"
            if not branding_logo_url:
                fallback_reason = "logo_missing"
        else:
            branding_company_name = "Paintly"
            branding_logo_url = None
            fallback_reason = "tier_not_allowed" if not branding_allowed else "company_name_missing"
    except Exception as exc:
        tenant_row = None
        tenant_user = None
        plan_raw = None
        plan_normalized = "unknown"
        branding_allowed = False
        user_company_name = ""
        tenant_company_name = ""
        user_logo_url = ""
        tenant_logo_url = ""
        branding_company_name = "Paintly"
        branding_logo_url = None
        branding_source = "default"
        fallback_reason = "branding_resolve_exception"
        log_branding_state(
            logger,
            "branding_resolve_failed",
            {
                "lead_id": str(getattr(lead, "id", "")),
                "tenant_id": str(getattr(lead, "tenant_id", "")),
                "error": repr(exc),
                "branding_allowed": False,
                "branding_company_name": "Paintly",
                "branding_logo_url": None,
            },
        )

    intake_payload = {}
    try:
        raw_payload = getattr(lead, "intake_payload", None)
        if isinstance(raw_payload, str) and raw_payload.strip():
            parsed_payload = json.loads(raw_payload)
            if isinstance(parsed_payload, dict):
                intake_payload = parsed_payload
    except Exception:
        intake_payload = {}

    customer_name = (getattr(lead, "name", None) or "").strip()
    customer_email = (getattr(lead, "email", None) or "").strip()
    customer_phone = (getattr(lead, "phone", None) or "").strip()
    customer_location = (
        (intake_payload.get("address") if isinstance(intake_payload, dict) else None)
        or (intake_payload.get("street") if isinstance(intake_payload, dict) else None)
        or ""
    )

    contractor_email = (
        (getattr(tenant_user, "email", None) or "").strip()
        if tenant_user is not None
        else ""
    ) or (
        (getattr(tenant_row, "email", None) or "").strip()
        if tenant_row is not None
        else ""
    )
    contractor_phone = (
        (getattr(tenant_row, "phone", None) or "").strip()
        if tenant_row is not None
        else ""
    )
    contractor_company_name = (branding_company_name or "").strip()

    logger.info(
        "[DATA_DEBUG] snapshot input lead_id=%s lead_name=%r lead_email=%r lead_phone=%r tenant_company_name=%r user_company_name=%r tenant_email=%r user_email=%r tenant_phone=%r",
        str(getattr(lead, "id", "")),
        getattr(lead, "name", None),
        getattr(lead, "email", None),
        getattr(lead, "phone", None),
        getattr(tenant_row, "company_name", None) if tenant_row is not None else None,
        getattr(tenant_user, "company_name", None) if tenant_user is not None else None,
        getattr(tenant_row, "email", None) if tenant_row is not None else None,
        getattr(tenant_user, "email", None) if tenant_user is not None else None,
        getattr(tenant_row, "phone", None) if tenant_row is not None else None,
    )

    company = estimate.get("company") if isinstance(estimate.get("company"), dict) else {}
    company = dict(company)
    company["company_name"] = branding_company_name
    company["name"] = branding_company_name
    company["logo_url"] = branding_logo_url
    company["email"] = contractor_email or company.get("email") or ""
    company["phone"] = contractor_phone or company.get("phone") or ""
    estimate["company"] = company
    estimate["customer"] = {
        "name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
        "location": customer_location,
    }
    estimate["contractor"] = {
        "company_name": contractor_company_name,
        "email": contractor_email,
        "phone": contractor_phone,
    }
    estimate["lead"] = {
        "name": customer_name,
        "email": customer_email,
        "phone": customer_phone,
    }
    estimate["branding_company_name"] = branding_company_name
    estimate["branding_logo_url"] = branding_logo_url
    estimate["branding_allowed"] = branding_allowed
    estimate["branding_source"] = branding_source
    logger.info(
        "[DATA_DEBUG] snapshot output lead_id=%s customer_name=%r customer_email=%r customer_phone=%r contractor_company_name=%r contractor_email=%r contractor_phone=%r",
        str(getattr(lead, "id", "")),
        estimate.get("customer", {}).get("name"),
        estimate.get("customer", {}).get("email"),
        estimate.get("customer", {}).get("phone"),
        estimate.get("contractor", {}).get("company_name"),
        estimate.get("contractor", {}).get("email"),
        estimate.get("contractor", {}).get("phone"),
    )

    log_branding_state(
        logger,
        "settings_loaded",
        {
            "lead_id": str(getattr(lead, "id", "")),
            "user_id": str(getattr(tenant_user, "id", "")) if tenant_user is not None else None,
            "tenant_id": str(getattr(lead, "tenant_id", "")),
            "user_company_name": user_company_name or None,
            "tenant_company_name": tenant_company_name or None,
            "user_logo_url": user_logo_url or None,
            "tenant_logo_url": tenant_logo_url or None,
            "plan_raw": plan_raw,
            "plan_normalized": plan_normalized,
            "branding_allowed": branding_allowed,
        },
    )
    log_branding_state(
        logger,
        "tier_gating",
        {
            "tier_source": "tenant.plan_code",
            "plan_raw": plan_raw,
            "plan_normalized": plan_normalized,
            "branding_allowed": branding_allowed,
        },
    )
    log_branding_state(
        logger,
        "estimate_snapshot",
        {
            "estimate_id": ((estimate.get("meta") or {}).get("estimate_id") if isinstance(estimate.get("meta"), dict) else None),
            "lead_id": str(getattr(lead, "id", "")),
            "branding_company_name": branding_company_name,
            "branding_logo_url": branding_logo_url,
            "branding_allowed": branding_allowed,
            "branding_source": branding_source,
            "fallback_reason": fallback_reason,
        },
    )

    try:
        for li in estimate.get("line_items") or []:
            if isinstance(li, dict) and not li.get("label"):
                st = li.get("code") or li.get("surface_type") or "Item"
                li["label"] = str(st).replace("_", " ").title()
    except Exception:
        pass

    return StepResult(status="OK", data={"estimate_json": estimate})


# -------------------------
# Step: render (1.5.5 template per branch)
# -------------------------
def step_render_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    env = assets["jinja_env"]
    template_path = assets["template_path"]
    template = env.get_template(template_path)

    def fmt_eur(v: Any) -> str:
        if v is None:
            return "€0"
        try:
            d = Decimal(str(v).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return "€0"

        s = f"{d:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        if s.endswith(",00"):
            s = s[:-3]
        return f"€{s}"

    # register helper in Jinja
    env.filters.setdefault("fmt_eur", fmt_eur)
    env.globals.setdefault("fmt_eur", fmt_eur)

    lead: Lead = assets.get("lead")

    def _safe_json_dict(s: Any) -> Dict[str, Any]:
        if not isinstance(s, str) or not s.strip():
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _clean_text(s: Any, max_len: int = 240) -> str:
        if not isinstance(s, str):
            s = "" if s is None else str(s)

        s = s.strip()
        if not s:
            return ""

        s = re.sub(r"\s+", " ", s).strip()
        lower = s.lower()

        cut_markers = [
            "vision_json",
            "vision json",
            "vision=",
            "debug",
            "trace_id=",
            "engine_status=",
            "image_predictions",
            "image_path",
            "model:",
            "reason:",
        ]
        for m in cut_markers:
            idx = lower.find(m)
            if idx != -1:
                s = s[:idx].strip()
                lower = s.lower()

        if "{" in s and not s.lstrip().startswith("{"):
            s = s.split("{", 1)[0].strip()

        s = s.rstrip(" -:;|,").strip()
        s = re.sub(r"\s+", " ", s).strip()

        if len(s) > max_len:
            s = s[: max_len - 1].rstrip() + "…"

        return s

    # --- pricing output (canonical) ---
    pricing = (state.data.get("steps") or {}).get("output", {}).get("estimate_json") or {}
    pricing = _ensure_obj(pricing)
    if not isinstance(pricing, dict):
        pricing = {}

    # --- raw pricing (engine internal) ---
    pricing_raw = (state.data.get("steps") or {}).get("pricing", {}).get(
        "pricing"
    ) or {}
    pricing_raw = _ensure_obj(pricing_raw)
    if not isinstance(pricing_raw, dict):
        pricing_raw = {}

    # meta / reasons
    meta = pricing.get("meta") if isinstance(pricing.get("meta"), dict) else {}
    reasons = meta.get("needs_review_reasons") or meta.get("review_reasons") or []
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(x) for x in reasons if x is not None]

    needs_review_step = (state.data.get("steps") or {}).get("needs_review", {}) or {}
    needs_review_flag = bool(
        needs_review_step.get("needs_review", False) or len(reasons) > 0
    )

    is_provisional = "provisional_total" in reasons

    grand_total = None
    try:
        grand_total = (pricing.get("totals") or {}).get("grand_total")
    except Exception:
        grand_total = None

    pricing_ready = _is_nonzero_money(grand_total) and (not is_provisional) and (not needs_review_flag)

    # -------------------------
    # Intake payload → context
    # -------------------------
    lead_payload = (
        _safe_json_dict(getattr(lead, "intake_payload", None)) if lead else {}
    )

    def _to_float(x: Any) -> float | None:
        try:
            if x is None:
                return None
            if isinstance(x, str) and not x.strip():
                return None
            return float(x)
        except Exception:
            return None

    def _to_int(x: Any) -> int | None:
        try:
            if x is None:
                return None
            if isinstance(x, str) and not x.strip():
                return None
            return int(float(x))
        except Exception:
            return None

    # -------------------------
    # Customer fields
    # -------------------------
    customer_name = (
        getattr(lead, "name", None) or lead_payload.get("name") or ""
    ).strip()
    customer_email = (
        getattr(lead, "email", None) or lead_payload.get("email") or ""
    ).strip()
    customer_phone = (
        getattr(lead, "phone", None) or lead_payload.get("phone") or ""
    ).strip()

    project_desc_raw = lead_payload.get("project_description") or ""
    address_raw = lead_payload.get("address") or ""

    project_desc = _clean_text(project_desc_raw)
    address = _clean_text(address_raw)

    # 1) Dedicated address veld (intake "address") heeft voorrang.
    # 2) Zo niet: bouw adres uit losse velden (street/zip/city).
    # 3) Zo niet: probeer "Adres: ..." uit de projectbeschrijving te parsen (demo fallback).
    if not address:
        street = _clean_text(lead_payload.get("street") or "")
        zip_code = _clean_text(lead_payload.get("zip") or "")
        city = _clean_text(lead_payload.get("city") or "")
        parts = [p for p in (street, zip_code, city) if p]
        fallback_address = ", ".join(parts)
        if fallback_address:
            address = fallback_address

    # DEMO: laatste redmiddel – haal adres uit beschrijving met een "Adres: ..." prefix.
    if not address and project_desc_raw:
        try:
            m = re.search(r"Adres[:\-\s]+(.+)", project_desc_raw, flags=re.IGNORECASE)
            if m:
                address = _clean_text(m.group(1))
        except Exception:
            pass

    if address and project_desc.lower().startswith("address:"):
        tmp = project_desc[len("address:") :].strip()
        if address.lower() in tmp.lower():
            tmp = re.sub(re.escape(address), "", tmp, flags=re.IGNORECASE).strip()
        project_desc = tmp.strip(" -:;|,").strip()

    location = (
        address or (project_desc[:80] + ("…" if len(project_desc) > 80 else "")) or None
    )

    # -------------------------
    # Area (sqft) selection (kept as-is)
    # -------------------------
    sqft: int | None = None
    source = None

    payload_sqft = _to_int(lead_payload.get("square_feet"))
    if payload_sqft is not None and payload_sqft > 0:
        sqft = payload_sqft
        source = "payload.square_feet"

    if sqft is None:
        sqm = _to_float(lead_payload.get("square_meters"))
        if sqm is not None and sqm > 0:
            sqft = int(round(sqm * 10.7639))
            source = "payload.square_meters"

    if sqft is None:
        lead_sqm = _to_float(getattr(lead, "square_meters", None)) if lead else None
        if lead_sqm is not None and lead_sqm > 0:
            sqft = int(round(lead_sqm * 10.7639))
            source = "lead.square_meters"

    try:
        logger.warning(
            "RENDER lead_id=%s sqft=%s source=%s payload_sqft=%s payload_sqm=%s lead_sqm=%s",
            getattr(lead, "id", None),
            sqft,
            source,
            lead_payload.get("square_feet"),
            lead_payload.get("square_meters"),
            getattr(lead, "square_meters", None),
        )
    except Exception:
        pass

    customer = {
        "name": customer_name or None,
        "email": customer_email or None,
        "phone": customer_phone or None,
    }

    project = {
        "lead_id": getattr(lead, "id", None) if lead else None,
        "estimate_id": meta.get("estimate_id")
        or (f"lead_{getattr(lead, 'id', '')}" if lead else ""),
        "date": str(meta.get("date") or dt.date.today().isoformat()),
        "valid_until": meta.get("valid_until"),
        "location": location,
        "square_feet": sqft,
        "description": project_desc or None,
        "address": address or None,
    }

    # -------------------------
    # ✅ VAT + totals (FIXED)
    # -------------------------
    def _to_float_safe(x: Any) -> float | None:
        try:
            if x is None:
                return None
            if isinstance(x, str) and not x.strip():
                return None
            return float(x)
        except Exception:
            return None

    def _sum_line_items_total(pr: Dict[str, Any]) -> Decimal:
        s = Decimal("0.00")
        for li in pr.get("line_items") or []:
            if not isinstance(li, dict):
                continue
            try:
                s += Decimal(str(li.get("total") or 0))
            except Exception:
                pass
        return s

    vat_rate = _to_float_safe(lead_payload.get("vat_rate"))

    if vat_rate is None:
        if lead_payload.get("home_older_than_2_years") is False:
            vat_rate = 0.21
    else:
        vat_rate = 0.09

    subtotal_excl = None
    try:
        subtotal_excl = (pricing.get("totals") or {}).get("pre_tax")
    except Exception:
        subtotal_excl = None

    if subtotal_excl is None:
        subtotal_excl = _sum_line_items_total(pricing)

    subtotal_excl_dec = Decimal(str(subtotal_excl or 0)).quantize(Decimal("0.01"))
    vat_rate_dec = Decimal(str(vat_rate)).quantize(Decimal("0.0001"))

    vat_amount_dec = (subtotal_excl_dec * vat_rate_dec).quantize(Decimal("0.01"))
    total_incl_dec = (subtotal_excl_dec + vat_amount_dec).quantize(Decimal("0.01"))

    vat = {
        "subtotal_excl_vat": float(subtotal_excl_dec),
        "vat_rate": float(vat_rate_dec),
        "vat_amount": float(vat_amount_dec),
        "total_incl_vat": float(total_incl_dec),
        # aliases for templates
        "rate": float(vat_rate_dec),
        "percent": int(round(float(vat_rate_dec) * 100)),
        "percentage": int(round(float(vat_rate_dec) * 100)),
        "amount": float(vat_amount_dec),
        "included": True,
    }

    branding_company_name = (
        pricing.get("branding_company_name") if isinstance(pricing.get("branding_company_name"), str) else "Paintly"
    )
    branding_logo_url = (
        pricing.get("branding_logo_url") if isinstance(pricing.get("branding_logo_url"), str) else None
    )
    log_branding_state(
        logger,
        "pre_render",
        {
            "lead_id": str(getattr(lead, "id", "")),
            "template": str(template_path),
            "branding_company_name": branding_company_name,
            "branding_logo_url": branding_logo_url,
            "branding_is_paintly": branding_company_name == "Paintly",
            "branding_logo_empty": not bool((branding_logo_url or "").strip()),
        },
    )

    if str(template_path).endswith("estimate.html"):
        html = render_estimate_html(pricing)
        html_summary = branding_html_debug_summary(
            html,
            branding_name=branding_company_name,
        )
        log_branding_state(
            logger,
            "post_render",
            {
                "lead_id": str(getattr(lead, "id", "")),
                **html_summary,
            },
        )
        logger.info(
            "RENDER_HTML_STEP_SOURCE lead_id=%s source=render_estimate_html canonical=True",
            getattr(lead, "id", None),
        )
    else:
        return StepResult(
            status="FAILED",
            error=f"unsupported_render_template:{template_path}",
        )
    return StepResult(status="OK", data={"estimate_html": html})


# -------------------------
# Step: store html (writes estimate_html_key)
# -------------------------
def step_store_html_v1(
    state: PipelineState, step: StepConfig, assets: dict
) -> StepResult:
    lead: Lead = assets.get("lead")
    if not lead:
        return StepResult(status="FAILED", error="missing_lead_in_assets")

    # config step id is "render_html"
    render_data = (state.data.get("steps") or {}).get("render_html") or {}
    html = render_data.get("estimate_html")
    if not html:
        return StepResult(
            status="FAILED", error="missing_estimate_html_from_render_step"
        )

    storage = get_storage()

    today = dt.date.today().isoformat()
    filename = f"estimate_{lead.id}_{uuid.uuid4().hex}.html"
    html_key = f"leads/{lead.id}/estimates/{today}/{filename}"
    print("STORE_HTML_V1:", html_key)
    logger.info(
        "STORE_HTML_CONTEXT lead_id=%s html_length=%s",
        getattr(lead, "id", None),
        len(html),
    )
    log_branding_state(
        logger,
        "store_html",
        {
            "lead_id": str(getattr(lead, "id", "")),
            "estimate_html_key": html_key,
            **branding_html_debug_summary(html),
        },
    )

    storage.save_bytes(
        tenant_id=str(getattr(lead, "tenant_id", "")),
        key=html_key,
        data=html.encode("utf-8"),
    )

    return StepResult(status="OK", data={"estimate_html_key": html_key})


def _decide_paintly_needs_review(
    pq_bad,
    prior_reasons,
    aggregate_needs_review,
    aggregate_reasons,
    pricing_reasons,
    photo_confidence=None,
    lead_id=None,
):
    """
    Central helper for Paintly NEEDS_REVIEW logic.

    Only "hard blockers" are allowed to flip needs_review to True.
    Soft signals (low confidence, furniture, framing, generic photo_quality
    noise) are kept in reasons/meta but do NOT force NEEDS_REVIEW on their own.
    """
    prior_reasons = prior_reasons or []
    aggregate_reasons = aggregate_reasons or []
    pricing_reasons = pricing_reasons or []

    merged_reasons = list(
        dict.fromkeys(prior_reasons + aggregate_reasons + pricing_reasons)
    )

    blocking_review_reasons = [
        r for r in merged_reasons if not _reason_is_non_blocking(r)
    ]

    # Hard blockers coming from pricing/engine-level validation
    PRICING_BLOCKERS = {
        "no_pricing_match",
        "missing_required_field",
        "too_few_images",
    }

    pricing_blocked = any(r in PRICING_BLOCKERS for r in pricing_reasons)

    # Hard blockers coming from estimate/output interpretation
    HARD_ESTIMATE_REASONS = {
        # Broken totals / missing required numeric output
        "estimate_not_dict",
        "missing_total",
        "non_positive_total",
        "total_not_numeric",
        # Explicit "missing analysis" style flags
        "missing_required_analysis",
        "missing_vision_output",
        "missing_pricing_output",
        "area_m2_non_positive",
    }

    # Hard blockers coming from vision aggregation / structural analysis
    HARD_AGGREGATE_REASONS = {
        # No usable walls/surfaces detected
        "no_walls_detected",
        "no_wall_detected",
        "no_wall_surfaces",
        "no_surfaces",
        # Upload/content-type uncertainty in image ingest pipeline
        "upload_mime_unverified",
    }

    # Hard blockers coming from structural wall condition / heavy prep signals
    # surfaced by vision aggregation (e.g. loslatend behang, blootliggende
    # ondergrond, zware herstelwerken).
    HARD_STRUCTURAL_REASONS = {
        # Alleen expliciete, zware schadecodes tellen hier als hard blockers.
        "substrate_visible",
        "peeling_wallcovering_detected",
        "repair_work_required",
        "surface_damage_detected",
    }

    # Hard blockers coming from photo quality (true absence of photos)
    HARD_PHOTO_REASONS = {
        "no_photos",
        "no_readable_photos",
        "photo_not_relevant",
        "photo_validation_low_confidence",
        "photo_quality_score_low",
    }

    # Extra diagnostic gate (kept for logging); explicit hard codes above still
    # force review on their own.
    surface_prep_present = (
        ("surface_preparation_required" in merged_reasons)
        or ("vision:surface_preparation_required" in merged_reasons)
    )
    low_photo_confidence_present = (
        photo_confidence is not None and float(photo_confidence) < 0.55
    )

    # Minimal decision-layer expansion:
    # Some providers/aggregators surface structural damage/prep as free-text or
    # variant reason labels. Treat those as hard blockers too so content-heavy
    # wall issues (not just photo-quality issues) can force review.
    structural_keywords = (
        "damaged wall",
        "wall damage",
        "peeling paint",
        "flaking paint",
        "exposed substrate",
        "substrate exposed",
        "repair required",
    )
    structural_text_reasons = []
    for r in blocking_review_reasons:
        txt = str(r or "").strip().lower()
        if txt and any(k in txt for k in structural_keywords):
            structural_text_reasons.append(str(r))
    structural_text_hard_blocker = bool(structural_text_reasons)

    base_hard_reason_present = any(
        (r in HARD_ESTIMATE_REASONS)
        or (r in HARD_AGGREGATE_REASONS)
        or (r in HARD_PHOTO_REASONS)
        or (r in HARD_STRUCTURAL_REASONS)
        for r in blocking_review_reasons
    ) or structural_text_hard_blocker

    heavy_prep_present = any(
        r in {
            "substrate_visible",
            "peeling_wallcovering_detected",
            "repair_work_required",
            "surface_damage_detected",
        }
        for r in blocking_review_reasons
    )
    severe_photo_quality_present = bool(
        pq_bad
        or any(
            r in {"no_usable_photos", "no_readable_photos", "no_photos", "photo_not_relevant"}
            for r in blocking_review_reasons
        )
    )
    # surface_preparation_required / vision:… are NON_BLOCKING; do not escalate
    # via the old prep+confidence gate for priced-output policy.
    surface_prep_hard_blocker = False
    hard_reason_present = bool(base_hard_reason_present or surface_prep_hard_blocker)

    triggered_rules: list[str] = []
    if pricing_blocked:
        triggered_rules.append("pricing_blocked")

    # Exact hard reason codes that triggered the decision (blocking only).
    for r in blocking_review_reasons:
        if (
            (r in HARD_ESTIMATE_REASONS)
            or (r in HARD_AGGREGATE_REASONS)
            or (r in HARD_PHOTO_REASONS)
            or (r in HARD_STRUCTURAL_REASONS)
        ):
            triggered_rules.append(r)
    if surface_prep_hard_blocker:
        triggered_rules.append("surface_preparation_required_gated")
    if structural_text_hard_blocker:
        triggered_rules.append("structural_text_reason_detected")
        triggered_rules.extend(structural_text_reasons)

    # Keep aggregate_needs_review coupled to explicit prep blockers so the
    # final decision cannot silently fall back to SUCCEEDED for this case.
    aggregate_surface_prep_blocker = bool(
        aggregate_needs_review and surface_prep_present and surface_prep_hard_blocker
    )
    if aggregate_surface_prep_blocker and "surface_preparation_required_gated" not in triggered_rules:
        triggered_rules.append("surface_preparation_required_gated")

    # Explicit allowlisted exception:
    # allow SUCCEEDED only when aggregate asks for review but every collected
    # reason is explicitly non-blocking (e.g. surface prep note only).
    allowlisted_aggregate_only = bool(
        aggregate_needs_review
        and not blocking_review_reasons
        and bool(merged_reasons)
        and all(_reason_is_non_blocking(r) for r in merged_reasons)
    )

    # Final decision:
    # - aggregate_needs_review OR any blocking reason now escalates to review
    # - except for the explicit allowlisted aggregate-only case above
    needs_review = bool(
        (
            pricing_blocked
            or hard_reason_present
            or aggregate_surface_prep_blocker
            or aggregate_needs_review
            or bool(blocking_review_reasons)
        )
        and (not allowlisted_aggregate_only)
    )

    logger.info(
        "REVIEW_BLOCKING_FILTER lead_id=%s merged_reasons=%s "
        "blocking_review_reasons=%s final_needs_review=%s",
        lead_id,
        merged_reasons,
        blocking_review_reasons,
        needs_review,
    )

    return needs_review, merged_reasons, pricing_blocked, triggered_rules


# -------------------------
# Step: needs review
# -------------------------
def step_needs_review_v1(
    state: PipelineState, step: StepConfig, assets: dict
) -> StepResult:
    # Local import avoids package-level circular import during engine step module load:
    # aether.engine.steps -> app.verticals -> adapter -> aether.engine.facade -> aether.engine.steps
    from app.verticals.paintly.needs_review import needs_review_from_output

    lead = (assets or {}).get("lead")
    lead_id = getattr(lead, "id", None)

    # -----------------------------
    # Manual override: skip review
    # -----------------------------
    try:
        # Prefer lead from assets if available
        lead = (assets or {}).get("lead")
        raw = getattr(lead, "intake_payload", None) if lead is not None else None

        # Fallbacks: sometimes pipeline stores payload in state.data
        if not raw:
            raw = (state.data or {}).get("lead_intake_payload") or (
                state.data or {}
            ).get("intake_payload")

        if isinstance(raw, str) and raw.strip():
            payload = json.loads(raw)
            if payload.get("manual_override") is True:
                return StepResult(
                    status="OK",
                    data={
                        "needs_review": False,
                        "needs_review_reasons": [],
                        "needs_review_hard": {"manual_override": True},
                    },
                    meta={"reasons": []},
                )
        elif isinstance(raw, dict):
            # If it's already a dict
            if raw.get("manual_override") is True:
                return StepResult(
                    status="OK",
                    data={
                        "needs_review": False,
                        "needs_review_reasons": [],
                        "needs_review_hard": {"manual_override": True},
                    },
                    meta={"reasons": []},
                )
    except Exception:
        # Never block pipeline because of override parsing
        pass

    # -----------------------------
    # Existing logic
    # -----------------------------
    estimate = (state.data.get("steps") or {}).get("output", {}).get(
        "estimate_json"
    ) or {}
    estimate = _ensure_obj(estimate)

    # also inspect aggregate output directly
    aggregate_data = (state.data.get("steps") or {}).get("aggregate", {}).get(
        "vision"
    ) or {}
    aggregate_data = _ensure_obj(aggregate_data)

    reasons = needs_review_from_output(estimate) or []

    aggregate_needs_review = False
    aggregate_reasons = []

    if isinstance(aggregate_data, dict):
        aggregate_needs_review = bool(aggregate_data.get("needs_review", False))
        aggregate_reasons = aggregate_data.get("review_reasons") or []
        if not isinstance(aggregate_reasons, list):
            aggregate_reasons = [str(aggregate_reasons)]

        # Hard blocker: clearly invalid or non-positive area estimate
        try:
            area_val = (
                (aggregate_data.get("area") or {}).get("value_m2", None)
                if isinstance(aggregate_data.get("area"), dict)
                else None
            )
            if area_val is not None:
                a = float(area_val)
                if a <= 0:
                    reasons.append("area_m2_non_positive")
        except Exception:
            # Keep failures as soft diagnostics only
            pass

    pq = (
        (state.data.get("steps") or {})
        .get("photo_quality", {})
        .get("photo_quality", {})
    )

    prior_reasons = []
    pq_bad = False
    photo_confidence = None
    if isinstance(pq, dict):
        prior_reasons = (pq.get("review_reasons") or pq.get("reasons") or [])
        pq_bad = bool(pq.get("review_required", pq.get("bad")))
        try:
            v = pq.get("validation") if isinstance(pq.get("validation"), dict) else {}
            if v:
                photo_confidence = float(v.get("confidence", None))
        except Exception:
            photo_confidence = None
        if pq_bad and not prior_reasons:
            prior_reasons = ["photo_quality_bad"]

    (
        needs_review,
        merged_reasons,
        pricing_blocked,
        triggered_rules,
    ) = _decide_paintly_needs_review(
        pq_bad=pq_bad,
        prior_reasons=prior_reasons,
        aggregate_needs_review=aggregate_needs_review,
        aggregate_reasons=aggregate_reasons,
        pricing_reasons=reasons,
        photo_confidence=photo_confidence,
        lead_id=lead_id,
    )

    if isinstance(estimate, dict):
        meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
        meta["needs_review_reasons"] = merged_reasons
        meta["review_reasons"] = merged_reasons
        meta["needs_review_hard"] = {
            "pq_bad": pq_bad,
            "pricing_blocked": pricing_blocked,
        }
        # Canonical top-level aliases used by estimate renderers/templates.
        estimate["needs_review"] = needs_review
        estimate["review_reasons"] = merged_reasons
        estimate["meta"] = meta

        # Targeted logging for review routing debugging:
        logger.info(
            "ESTIMATE_META_NEEDS_REVIEW_REASONS lead_id=%s needs_review_reasons=%r",
            lead_id,
            meta.get("needs_review_reasons"),
        )
        logger.info(
            "FINAL_MERGED_REASONS lead_id=%s merged_reasons=%r",
            lead_id,
            merged_reasons,
        )

    print(
        "NEEDS_REVIEW DEBUG:",
        {
            "pq_bad": pq_bad,
            "pricing_blocked": pricing_blocked,
            "aggregate_needs_review": aggregate_needs_review,
            "merged_reasons": merged_reasons,
        },
    )

    final_status = "NEEDS_REVIEW" if needs_review else "SUCCEEDED"
    logger.info(
        "REVIEW_DECISION lead_id=%s pq_bad=%r aggregate_needs_review=%r photo_confidence=%r merged_reasons=%r triggered_rules=%r final_status=%s",
        lead_id,
        pq_bad,
        aggregate_needs_review,
        photo_confidence,
        merged_reasons,
        triggered_rules,
        final_status,
    )

    return StepResult(
        status="NEEDS_REVIEW" if needs_review else "OK",
        data={
            "needs_review": needs_review,
            "needs_review_reasons": merged_reasons,
            "needs_review_hard": {
                "pq_bad": pq_bad,
                "pricing_blocked": pricing_blocked,
            },
        },
        meta={"reasons": merged_reasons},
    )
