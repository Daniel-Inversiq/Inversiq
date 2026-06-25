from __future__ import annotations

import json
import uuid
import secrets
import datetime as dt
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.models import Lead, Tenant
from app.models.user import User
from app.tasks.vision_task import run_vision_for_lead

from app.verticals.construction.vision_aggregate_us import (
    aggregate_images_to_quote_inputs as aggregate_vision,
)

from app.verticals.construction.pricing_engine_us import run_pricing_engine
from app.verticals.construction.pricing_output_builder import build_pricing_output
from app.verticals.construction.needs_review import needs_review_from_output

from app.services.storage import get_storage
from app.services.branding import (
    is_custom_branding_allowed,
    log_branding_state,
    normalize_plan,
)

logger = logging.getLogger(__name__)


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


def _demo_vision() -> dict:
    """
    Fallback quote_inputs for leads without uploaded files.
    Keeps pricing predictable.
    """
    return {
        "area": {
            "value_m2": 75,
            "source": "demo",
            "confidence": 0.75,
            "sanity": {"status": "OK", "reason": None},
        },
        "scope": {
            "interior": True,
            "paint_walls": True,
            "paint_ceiling": False,
            "paint_trim": False,
        },
        "modifiers": {
            # NOTE: rules expect light/medium/heavy; "standard" will map to multiplier 1.0
            "prep_level": "light",
            "complexity": 1.1,
            "risk": {"cracks": False, "moisture": False},
        },
        "vision_signal_confidence": 0.8,
        "pricing_ready": True,
        "needs_review": False,
        "review_reasons": ["demo_mode"],
    }


def _extract_estimated_area(lead: Lead) -> float | None:
    """
    Extract estimated m² from intake.
    Supports:
      - lead.estimated_area_m2
      - lead.square_meters
      - lead.intake_payload (JSON string) with square_meters/area_sqm
      - dict-ish fields lead.data/lead.payload/lead.intake
    """
    # 1) direct columns
    for attr in ("estimated_area_m2", "square_meters"):
        if hasattr(lead, attr):
            v = getattr(lead, attr, None)
            if v:
                try:
                    f = float(v)
                    if f > 0:
                        return f
                except Exception:
                    pass

    # 2) intake_payload JSON string
    raw = getattr(lead, "intake_payload", None)
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                v = (
                    payload.get("square_meters")
                    or payload.get("area_sqm")
                    or payload.get("estimated_area_m2")
                )
                if v is not None:
                    f = float(v)
                    if f > 0:
                        return f
        except Exception:
            pass

    # 3) dict fields
    for attr in ("data", "payload", "intake"):
        val = getattr(lead, attr, None)
        if isinstance(val, dict):
            v = (
                val.get("square_meters")
                or val.get("area_sqm")
                or val.get("estimated_area_m2")
                or val.get("area_m2")
            )
            if v is not None:
                try:
                    f = float(v)
                    if f > 0:
                        return f
                except Exception:
                    pass

    return None


def compute_quote_for_lead(db: Session, lead: Lead, render_html: bool = True) -> dict:
    # --------------------------------------------------
    # 1) Vision stage
    # --------------------------------------------------
    vision_raw: Any = None
    try:
        vision_raw = run_vision_for_lead(db, lead.id, lead=lead)
        vision_raw = _ensure_obj(vision_raw)

        estimated_area_m2 = _extract_estimated_area(lead)

        scope = {
            "interior": True,
            "paint_walls": True,
            "paint_ceiling": False,
            "paint_trim": False,
        }

        # Unwrap: run_vision_for_lead returns a dict with "image_predictions"
        image_predictions = (
            vision_raw.get("image_predictions")
            if isinstance(vision_raw, dict)
            else vision_raw
        )
        image_predictions = _ensure_obj(image_predictions)

        vision = aggregate_vision(
            image_predictions=image_predictions,
            estimated_area_m2=estimated_area_m2,
            scope=scope,
        )
        vision = _ensure_obj(vision)

    except ValueError as e:
        if "No files found for this lead" in str(e):
            vision = _demo_vision()
        else:
            raise

    # --------------------------------------------------
    # 2) Pricing stage (tenant pricing aware)
    # --------------------------------------------------
    tenant_row: Tenant | None = (
        db.query(Tenant).filter(Tenant.id == lead.tenant_id).first()
    )
    tenant_pricing = (
        dict(getattr(tenant_row, "pricing_json", {}) or {}) if tenant_row is not None else {}
    )
    pricing = run_pricing_engine(lead, vision, tenant_pricing=tenant_pricing)
    pricing = _ensure_obj(pricing)

    # --------------------------------------------------
    # 3) Output builder
    # --------------------------------------------------
    estimate = build_pricing_output(lead, vision, pricing)
    estimate = _ensure_obj(estimate)

    # Attach vision info to meta (once)
    if isinstance(estimate, dict):
        meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
        if isinstance(vision, dict):
            meta["vision_needs_review"] = bool(vision.get("needs_review", False))
            meta["vision_review_reasons"] = vision.get("review_reasons", [])
            meta["vision_signal_confidence"] = vision.get(
                "vision_signal_confidence", None
            )

            area = (
                (vision.get("area") or {})
                if isinstance(vision.get("area"), dict)
                else {}
            )
            meta["area_m2"] = area.get("value_m2", None)

        # New vision provider signals (optional, backwards-compatible)
        if isinstance(vision_raw, dict):
            lead_aggregate = (
                vision_raw.get("lead_aggregate")
                if isinstance(vision_raw.get("lead_aggregate"), dict)
                else None
            )
            if lead_aggregate is not None:
                meta["vision_lead_aggregate"] = lead_aggregate
                meta["vision_uncertainty_score"] = lead_aggregate.get(
                    "uncertainty_score"
                )
                meta["vision_coverage_score"] = lead_aggregate.get("coverage_score")
                meta["vision_evidence_score"] = lead_aggregate.get("evidence_score")
                meta["vision_aggregate_needs_review"] = bool(
                    lead_aggregate.get("needs_review", False)
                )
                meta["vision_aggregate_review_reasons"] = lead_aggregate.get(
                    "review_reasons", []
                )

            photo_predictions = vision_raw.get("photo_predictions")
            if isinstance(photo_predictions, list):
                usable_count = 0
                low_usability_count = 0
                for p in photo_predictions:
                    if not isinstance(p, dict):
                        continue
                    if bool(p.get("photo_is_usable")):
                        usable_count += 1
                    try:
                        if float(p.get("photo_usability_score", 0.0)) < 0.5:
                            low_usability_count += 1
                    except Exception:
                        pass
                meta["vision_photo_count"] = len(photo_predictions)
                meta["vision_usable_photo_count"] = usable_count
                meta["vision_low_usability_photo_count"] = low_usability_count

            vision_results = vision_raw.get("vision_results")
            if isinstance(vision_results, list):
                fallback_used = any(
                    isinstance(vr, dict) and str(vr.get("provider")) == "fallback"
                    for vr in vision_results
                )
                meta["vision_fallback_used"] = fallback_used

            if str(vision_raw.get("reason", "")) == "provider_fallback_to_legacy":
                meta["vision_fallback_used"] = True

        estimate["meta"] = meta

    # --------------------------------------------------
    # 4) Needs review logic
    # --------------------------------------------------
    reasons = needs_review_from_output(estimate)
    needs_review = bool(reasons)

    if isinstance(estimate, dict):
        meta = estimate.get("meta") if isinstance(estimate.get("meta"), dict) else {}
        meta["needs_review_reasons"] = reasons
        estimate["meta"] = meta

    # --------------------------------------------------
    # 5b) Company context for HTML template render
    # --------------------------------------------------
    if isinstance(estimate, dict):
        tenant_user = (
            db.query(User)
            .filter(User.tenant_id == str(lead.tenant_id), User.is_active == True)  # noqa: E712
            .order_by(User.created_at.desc(), User.id.desc())
            .first()
        )
        tenant_fallback = (
            db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()
        )
        company = estimate.get("company") or estimate.get("tenant") or {}
        if not isinstance(company, dict):
            company = {}
        company = dict(company)

        user_company_name = (
            (getattr(tenant_user, "company_name", None) or "").strip()
            if tenant_user is not None
            else ""
        )
        tenant_company_name = (
            (getattr(tenant_fallback, "company_name", None) or "").strip()
            if tenant_fallback is not None
            else ""
        )
        plan_raw = getattr(tenant_fallback, "plan_code", None) if tenant_fallback is not None else None
        plan_normalized = normalize_plan(plan_raw)
        branding_allowed = is_custom_branding_allowed(plan_raw)
        chosen_custom_name = user_company_name or tenant_company_name
        user_logo_url = (
            (getattr(tenant_user, "logo_url", None) or "").strip()
            if tenant_user is not None
            else ""
        )
        tenant_logo_url = (
            (getattr(tenant_fallback, "logo_url", None) or "").strip()
            if tenant_fallback is not None
            else ""
        )
        chosen_custom_logo = user_logo_url or tenant_logo_url
        if branding_allowed and chosen_custom_name:
            company_name = chosen_custom_name
            branding_logo_url = chosen_custom_logo or None
            branding_source = "user" if user_company_name else "tenant"
            fallback_reason = None if branding_logo_url else "logo_missing"
        else:
            company_name = "Inversiq"
            branding_logo_url = None
            branding_source = "default"
            fallback_reason = "tier_not_allowed" if not branding_allowed else "company_name_missing"

        company["company_name"] = company_name
        company["name"] = company_name
        company["logo_url"] = branding_logo_url
        estimate["company"] = company
        estimate["branding_company_name"] = company_name
        estimate["branding_logo_url"] = branding_logo_url

        logger.info(
            "ESTIMATE_BRANDING_CONTEXT lead_id=%s tenant_id=%s user_id=%s user_company_name=%r user_logo_url=%r tenant_company_name=%r tenant_logo_url=%r branding_company_name=%r branding_logo_url=%r",
            str(getattr(lead, "id", "")),
            str(getattr(lead, "tenant_id", "")),
            str(getattr(tenant_user, "id", "")) if tenant_user is not None else None,
            user_company_name or None,
            user_logo_url or None,
            tenant_company_name or None,
            tenant_logo_url or None,
            company_name,
            branding_logo_url,
        )
        log_branding_state(
            logger,
            "legacy_estimate_snapshot",
            {
                "lead_id": str(getattr(lead, "id", "")),
                "plan_raw": plan_raw,
                "plan_normalized": plan_normalized,
                "branding_allowed": branding_allowed,
                "branding_company_name": company_name,
                "branding_logo_url": branding_logo_url,
                "branding_source": branding_source,
                "fallback_reason": fallback_reason,
            },
        )

    # --------------------------------------------------
    # 6) Optional HTML render + store
    # --------------------------------------------------
    html_key = None

    if render_html:
        # Import lazily to avoid boot failure when render dependencies/constants mismatch
        from app.verticals.construction.render_estimate import render_estimate_html

        html = render_estimate_html(estimate)

        storage = get_storage()
        today = dt.date.today().isoformat()
        filename = f"estimate_{lead.id}_{uuid.uuid4().hex}.html"
        html_key = f"leads/{lead.id}/estimates/{today}/{filename}"

        storage.save_bytes(
            tenant_id=str(lead.tenant_id),
            key=html_key,
            data=html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )

        if not getattr(lead, "public_token", None):
            lead.public_token = secrets.token_hex(16)
            logger.info(
                "GENERATED_MISSING_PUBLIC_TOKEN lead_id=%s tenant_id=%s public_token=%s",
                str(getattr(lead, "id", "")),
                str(getattr(lead, "tenant_id", "")),
                lead.public_token,
            )

    return {
        "estimate_json": estimate,
        "estimate_html_key": html_key,
        "needs_review": needs_review,
    }
