"""
app/verticals/painting/quote_service.py

Painting quote orchestration service.

Public surface
--------------
compute_and_persist_quote(db, lead, *, vertical_id)
    Called by PaintlyAdapter.compute_quote() after HTTP-layer validation.
    Orchestrates engine → normalization → review decision → persist → ML capture.

Internal helpers (private, same module)
----------------------------------------
_run_engine               — engine facade call + debug diagnostics
_extract_quote_payload    — result validation + estimate normalisation
_resolve_review_decision  — engine flag + demo_force_review override
_fire_ml_capture          — best-effort ML training capture side-effect
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models import Lead, LeadFile, Tenant
from app.models.upload_record import UploadRecord, UploadStatus
from app.models.user import User
from app.billing.entitlements import Action, check_entitlement
from app.services.branding import is_custom_branding_allowed, log_branding_state, normalize_plan
from app.services.lead_training_service import capture_ml_data
from inversiq.engine.facade import VerticalDefinition, compute_quote_for_lead_v15
from inversiq.engine.steps import register_all as _register_paintly_steps

logger = logging.getLogger(__name__)


def _looks_like_image(key: str) -> bool:
    return (key or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic"))


def prepare_painting_assets(db: Session, lead: Any) -> Dict[str, Any]:
    """
    Painting-specific asset preparation for the engine facade.

    Precomputes the three painting-vertical assets that steps consume:
      tenant_pricing   — Tenant.pricing_json dict; consumed by step_pricing_v1
      image_refs       — List[str] of S3 keys; consumed by step_photo_quality_v1
      branding_context — resolved branding/contractor dict; consumed by step_output_v1

    Passed as `prepare_assets_fn` to compute_quote_for_lead_v15.
    """
    # tenant_pricing
    _tenant_pricing: Dict[str, Any] = {}
    try:
        _t = db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()
        _raw = getattr(_t, "pricing_json", None) if _t is not None else None
        if isinstance(_raw, dict):
            _tenant_pricing = _raw
    except Exception:
        _tenant_pricing = {}

    # image_refs: UploadRecord primary, LeadFile fallback
    _image_refs: List[str] = []
    try:
        _seen: set = set()
        _ur_rows = (
            db.query(UploadRecord)
            .filter(UploadRecord.tenant_id == str(lead.tenant_id))
            .filter(UploadRecord.lead_id == str(lead.id))
            .filter(UploadRecord.status.in_([UploadStatus.uploaded, "uploaded"]))
            .all()
        )
        for _r in _ur_rows:
            _ok_mime = isinstance(_r.mime, str) and _r.mime.startswith("image/")
            _ok_ext = _looks_like_image(getattr(_r, "object_key", "") or "")
            if _ok_mime or _ok_ext:
                if isinstance(_r.object_key, str) and _r.object_key:
                    if _r.object_key not in _seen:
                        _seen.add(_r.object_key)
                        _image_refs.append(_r.object_key)
        if not _image_refs:
            _lf_rows = db.query(LeadFile).filter(LeadFile.lead_id == str(lead.id)).all()
            for _lf in _lf_rows:
                _key = getattr(_lf, "s3_key", None)
                if isinstance(_key, str) and _key and _looks_like_image(_key):
                    if _key not in _seen:
                        _seen.add(_key)
                        _image_refs.append(_key)
    except Exception:
        _image_refs = []

    # branding_context: Tenant + User resolution
    _branding_ctx: Dict[str, Any] = {}
    try:
        _bu = (
            db.query(User)
            .filter(
                User.tenant_id == str(lead.tenant_id),
                User.is_active == True,  # noqa: E712
            )
            .order_by(User.created_at.desc(), User.id.desc())
            .first()
        )
        _bt = db.query(Tenant).filter(Tenant.id == str(lead.tenant_id)).first()

        _plan_raw = getattr(_bt, "plan_code", None) if _bt is not None else None
        _plan_normalized = normalize_plan(_plan_raw)
        _branding_allowed = is_custom_branding_allowed(_plan_raw)
        _wl = check_entitlement(_bt, Action.USE_WHITELABEL.value)
        _whitelabel_enabled = bool(_wl.allowed)

        _user_company_name = (
            (getattr(_bu, "company_name", None) or "").strip() if _bu is not None else ""
        )
        _tenant_company_name = (
            (getattr(_bt, "company_name", None) or "").strip() if _bt is not None else ""
        )
        _user_logo_url = (
            (getattr(_bu, "logo_url", None) or "").strip() if _bu is not None else ""
        )
        _tenant_logo_url = (
            (getattr(_bt, "logo_url", None) or "").strip() if _bt is not None else ""
        )
        _chosen_custom_name = _user_company_name or _tenant_company_name
        _chosen_custom_logo = _user_logo_url or _tenant_logo_url

        _bc_source = "default"
        _bc_fallback_reason = None
        if _branding_allowed and _chosen_custom_name:
            _bc_company_name = _chosen_custom_name
            _bc_logo_url = _chosen_custom_logo or None
            _bc_source = "user" if _user_company_name else "tenant"
            if not _bc_logo_url:
                _bc_fallback_reason = "logo_missing"
        else:
            _bc_company_name = "Inversiq"
            _bc_logo_url = None
            _bc_fallback_reason = (
                "tier_not_allowed" if not _branding_allowed else "company_name_missing"
            )

        _user_email = (getattr(_bu, "email", None) or "").strip() if _bu is not None else ""
        _tenant_email = (getattr(_bt, "email", None) or "").strip() if _bt is not None else ""

        _branding_ctx = {
            "company_name": _bc_company_name,
            "logo_url": _bc_logo_url,
            "branding_allowed": _branding_allowed,
            "whitelabel_enabled": _whitelabel_enabled,
            "branding_source": _bc_source,
            "fallback_reason": _bc_fallback_reason,
            "contractor_email": _user_email or _tenant_email,
            "contractor_phone": (
                (getattr(_bt, "phone", None) or "").strip() if _bt is not None else ""
            ),
            "user_company_name": _user_company_name,
            "tenant_company_name": _tenant_company_name,
            "user_logo_url": _user_logo_url,
            "tenant_logo_url": _tenant_logo_url,
            "user_email": _user_email,
            "tenant_email": _tenant_email,
            "user_id": str(getattr(_bu, "id", "")) if _bu is not None else None,
            "plan_raw": _plan_raw,
            "plan_normalized": _plan_normalized,
        }
    except Exception as _bexc:
        _branding_ctx = {
            "company_name": "Inversiq",
            "logo_url": None,
            "branding_allowed": False,
            "whitelabel_enabled": False,
            "branding_source": "default",
            "fallback_reason": "branding_resolve_exception",
            "contractor_email": "",
            "contractor_phone": "",
            "user_company_name": "",
            "tenant_company_name": "",
            "user_logo_url": "",
            "tenant_logo_url": "",
            "user_email": "",
            "tenant_email": "",
            "user_id": None,
            "plan_raw": None,
            "plan_normalized": "unknown",
        }
        log_branding_state(
            logger,
            "branding_resolve_failed",
            {
                "lead_id": str(getattr(lead, "id", "")),
                "tenant_id": str(lead.tenant_id),
                "error": repr(_bexc),
                "branding_allowed": False,
                "branding_company_name": "Inversiq",
                "branding_logo_url": None,
            },
        )

    return {
        "tenant_pricing": _tenant_pricing,
        "image_refs": _image_refs,
        "branding_context": _branding_ctx,
    }


# Module-level vertical definition — passed to compute_quote_for_lead_v15.
_PAINTLY_VERTICAL = VerticalDefinition(
    vertical_id="paintly",
    register_steps_fn=_register_paintly_steps,
    prepare_assets_fn=prepare_painting_assets,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_engine(
    db: Session,
    lead: Lead,
    vertical_id: str,
) -> Dict[str, Any]:
    """
    Invoke the engine facade and emit debug diagnostics.

    The debug block is intentionally non-blocking — any failure inside it is
    swallowed so it can never affect the pricing outcome.

    Returns the raw engine result dict.
    """
    result = compute_quote_for_lead_v15(db, lead, _PAINTLY_VERTICAL)

    # DEBUG (safe, non-blocking)
    try:
        dbg_logger = logging.getLogger("aether")
        dbg_logger.warning(
            "DEBUG facade estimate_html_key=%s",
            result.get("estimate_html_key"),
        )
        est_dbg = result.get("estimate_json")
        if isinstance(est_dbg, str):
            try:
                est_dbg_obj = json.loads(est_dbg)
            except Exception:
                est_dbg_obj = {"_raw": est_dbg}
        elif isinstance(est_dbg, dict):
            est_dbg_obj = est_dbg
        else:
            est_dbg_obj = {"_type": str(type(est_dbg))}
        digest = hashlib.md5(
            json.dumps(est_dbg_obj, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        dbg_logger.warning("DEBUG facade estimate_json_md5=%s", digest)
    except Exception:
        pass

    return result


def _extract_quote_payload(
    result: Dict[str, Any],
) -> Tuple[str, Any, str]:
    """
    Validate the engine result and serialise the estimate to a JSON string.

    Returns:
        (html_key, estimate_obj, estimate_json_str)
        - html_key          : S3 path to the rendered HTML estimate
        - estimate_obj      : the estimate as dict | None (normalized by the facade)
        - estimate_json_str : the estimate serialised to a UTF-8 JSON string,
                              ready to write to Lead.estimate_json

    Raises:
        RuntimeError if html_key is absent (engine wiring bug).
    """
    html_key = result.get("estimate_html_key")
    if not html_key:
        raise RuntimeError("engine_missing_estimate_html_key")

    # estimate_json is guaranteed dict | None by the engine facade.
    estimate_obj = result.get("estimate_json")
    estimate_json_str = json.dumps(
        jsonable_encoder(estimate_obj),
        ensure_ascii=False,
        default=str,
    )

    return html_key, estimate_obj, estimate_json_str


def _resolve_review_decision(
    engine_result: Dict[str, Any],
    intake_payload_raw: str | None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Determine the final needs_review value and return the parsed intake payload.

    Starts from the engine's own flag, then applies the demo_force_review
    override from the lead's intake_payload.  The parsed payload dict is
    returned so that the ML capture step can reuse it without re-parsing.

    Returns:
        (needs_review, payload)
    """
    needs_review = bool(engine_result.get("needs_review", False))

    payload: Dict[str, Any] = {}
    try:
        try:
            payload = json.loads(intake_payload_raw or "{}")
        except Exception:
            payload = {}
        # DEMO-SIMPLIFICATIE: forceer NEEDS_REVIEW wanneer demo_force_review is
        # gezet in het intake_payload.  Standaard flow gebruikt de engine-uitkomst.
        flag = payload.get("demo_force_review") or payload.get("demo_review")
        if bool(flag):
            needs_review = True
    except Exception:
        # Failsafe: keep engine decision on payload parsing issues.
        pass

    return needs_review, payload


def _fire_ml_capture(
    db: Session,
    lead: Lead,
    files: List[LeadFile],
    estimate_obj: Any,
    payload: Dict[str, Any],
    engine_result: Dict[str, Any],
    *,
    needs_review: bool,
) -> None:
    """
    Best-effort ML training data capture.

    Any failure inside this function is logged but never propagates to the
    caller — dataset capture must never break the pricing flow.
    """
    intake_snapshot: Dict[str, Any] = {}
    try:
        if isinstance(payload, dict) and payload:
            intake_snapshot = payload
        else:
            raw_intake = getattr(lead, "intake_payload", None)
            if isinstance(raw_intake, str) and raw_intake.strip():
                intake_snapshot = json.loads(raw_intake)
    except Exception:
        intake_snapshot = {}

    photo_refs: List[str] = [
        lf.s3_key for lf in files if getattr(lf, "s3_key", None)
    ]

    structured_estimate_output: Any = estimate_obj  # dict | None, normalized by facade

    metadata_json: Dict[str, Any] = {
        "source": "paintly_adapter.compute_quote",
        "engine_status": engine_result.get("engine_status"),
        "needs_review": needs_review,
        "trace_id": engine_result.get("trace_id"),
    }

    pricing_result = engine_result.get("debug_pricing_raw")
    try:
        capture_ml_data(
            db,
            tenant_id=str(lead.tenant_id),
            lead_id=str(lead.id),
            intake_snapshot=intake_snapshot,
            photo_refs=photo_refs,
            estimate_input=None,
            estimate_output=structured_estimate_output,
            pricing_result=pricing_result,
            metadata_json=metadata_json,
        )
    except Exception:
        # Never break the pricing flow on dataset capture failures.
        logger.exception(
            "LEAD_TRAINING_CAPTURE_FAILED "
            "lead_id=%s tenant_id=%s "
            "intake_snapshot=%r photo_refs=%r "
            "pricing_result_present=%s pricing_result_type=%s "
            "estimate_output_present=%s estimate_output_type=%s",
            getattr(lead, "id", None),
            getattr(lead, "tenant_id", None),
            intake_snapshot,
            photo_refs,
            pricing_result is not None,
            type(pricing_result).__name__ if pricing_result is not None else "NoneType",
            structured_estimate_output is not None,
            type(structured_estimate_output).__name__
            if structured_estimate_output is not None
            else "NoneType",
        )


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

def compute_and_persist_quote(
    db: Session,
    lead: Lead,
    *,
    vertical_id: str,
) -> Dict[str, Any]:
    """
    Run the engine facade for a painting lead, persist the result, and return
    a summary dict.

    Pre-conditions (caller's responsibility):
      - lead exists in DB and has been refreshed
      - lead.vertical == vertical_id
      - lead has at least one LeadFile row

    Returns:
        {"estimate_json": str, "estimate_html_key": str, "needs_review": bool}

    Raises:
        RuntimeError  — engine returned a malformed result (no html_key)
        Any exception raised by the engine pipeline

    Note: HTTPException is intentionally NOT raised here.  The adapter wrapper
    catches all non-HTTP exceptions and converts them to HTTP 500.
    """
    # Re-query files: cheap (indexed), keeps this function self-contained.
    files: List[LeadFile] = (
        db.query(LeadFile).filter(LeadFile.lead_id == lead.id).all()
    )

    # 1. Run engine
    engine_result = _run_engine(db, lead, vertical_id)

    # 2. Validate + normalise engine output
    html_key, estimate_obj, estimate_json_str = _extract_quote_payload(engine_result)

    # 3. Resolve review decision (engine flag + demo_force_review override)
    needs_review, payload = _resolve_review_decision(engine_result, lead.intake_payload)

    # 4. Write estimate fields and status to lead
    lead.estimate_json = estimate_json_str
    lead.estimate_html_key = html_key
    lead.status = "NEEDS_REVIEW" if needs_review else "SUCCEEDED"
    lead.error_message = None

    # 5. Operational logging
    total_price = None
    price_mode = "tbd"
    pricing_status = "computed"
    try:
        est_for_log = estimate_obj if isinstance(estimate_obj, dict) else {}
        totals = (
            est_for_log.get("totals")
            if isinstance(est_for_log.get("totals"), dict)
            else {}
        )
        total_price = totals.get("grand_total", totals.get("pre_tax"))
        if total_price is not None:
            price_mode = "priced"
    except Exception:
        total_price = None
        price_mode = "tbd"

    # Outward-facing labeling polish: review cases should not be logged
    # as normal priced auto-quotes, even if an internal price exists.
    if needs_review:
        price_mode = "tbd"
        pricing_status = "computed_review"

    logger.info(
        "QUOTE_OUTPUT_DECISION lead_id=%s needs_review=%s lead_status=%s "
        "pricing_status=%s total_price=%r price_mode=%s template=%s review_page=%s",
        getattr(lead, "id", None),
        needs_review,
        getattr(lead, "status", None),
        pricing_status,
        total_price,
        price_mode,
        "estimate.html",
        bool(needs_review),
    )

    # 6. ML capture (best-effort side-effect, never breaks the flow)
    _fire_ml_capture(
        db, lead, files, estimate_obj, payload, engine_result,
        needs_review=needs_review,
    )

    # 7. Commit
    db.add(lead)
    db.commit()
    db.refresh(lead)

    return {
        "estimate_json": lead.estimate_json,
        "estimate_html_key": lead.estimate_html_key,
        "needs_review": needs_review,
    }
