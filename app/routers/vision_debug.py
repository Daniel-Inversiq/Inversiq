# app/routers/vision_debug.py
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db import get_db
from app.models import Lead
from app.verticals.registry import get as get_vertical
from app.verticals.painting import compute_quote_for_lead, needs_review_from_output

router = APIRouter(prefix="/vision", tags=["vision"])
logger = logging.getLogger(__name__)


@router.post("/run/{lead_id}")
def run_vision(lead_id: str, db: Session = Depends(get_db)):
    try:
        # Single-vertical for now, but registry-based
        v = get_vertical("paintly")
        vision_output = v.run_vision(db, lead_id)

        return {
            "lead_id": lead_id,
            "vertical": v.vertical_id,
            "vision_output": vision_output,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inspect/{lead_id}")
def inspect_vision_flow(lead_id: str, db: Session = Depends(get_db)):
    """
    Lightweight debug entry for validating the new Paintly vision flow on a single lead.
    Runs the same vision stage and returns a compact inspection payload.
    """
    if not settings.ENABLE_DEV_ROUTES:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        v = get_vertical("paintly")
        vision_output = v.run_vision(db, lead_id)
        if not isinstance(vision_output, dict):
            return {
                "lead_id": lead_id,
                "vertical": v.vertical_id,
                "mode": "unknown",
                "vision_output_type": type(vision_output).__name__,
                "vision_output": vision_output,
            }

        photo_predictions = vision_output.get("photo_predictions")
        photo_inputs = vision_output.get("photo_inputs")
        lead_aggregate = vision_output.get("lead_aggregate")
        review_reasons = vision_output.get("review_reasons") or []
        vision_results = vision_output.get("vision_results")

        per_photo_preview = []
        photo_inputs_by_id = {}
        if isinstance(photo_inputs, list):
            for pi in photo_inputs:
                if not isinstance(pi, dict):
                    continue
                pid = pi.get("photo_id")
                if pid is not None:
                    photo_inputs_by_id[str(pid)] = pi
        if isinstance(photo_predictions, list):
            for p in photo_predictions:
                if not isinstance(p, dict):
                    continue
                photo_id = str(p.get("photo_id"))
                pi = photo_inputs_by_id.get(photo_id, {})
                per_photo_preview.append(
                    {
                        "photo_id": p.get("photo_id"),
                        "photo_is_usable": p.get("photo_is_usable"),
                        "photo_usability_score": p.get("photo_usability_score"),
                        "quote_relevance_score": p.get("quote_relevance_score"),
                        "uncertainty_score": p.get("uncertainty_score"),
                        "review_flags": p.get("review_flags", []),
                        "photo_quality": (pi.get("photo_quality") if isinstance(pi, dict) else None) or {},
                        "top_surfaces": [
                            {
                                "type": s.get("type"),
                                "confidence": s.get("confidence"),
                                "approximate_coverage": s.get("approximate_coverage"),
                            }
                            for s in (p.get("surfaces") or [])[:3]
                            if isinstance(s, dict)
                        ],
                        "damages": [
                            {
                                "type": d.get("type"),
                                "confidence": d.get("confidence"),
                                "severity": d.get("severity"),
                            }
                            for d in (p.get("damages") or [])
                            if isinstance(d, dict)
                        ],
                    }
                )

        provider_summary = []
        if isinstance(vision_results, list):
            for r in vision_results:
                if not isinstance(r, dict):
                    continue
                provider_summary.append(
                    {
                        "photo_id": r.get("photo_id"),
                        "provider": r.get("provider"),
                        "model_name": r.get("model_name"),
                        "prompt_version": r.get("prompt_version"),
                        "latency_ms": r.get("latency_ms"),
                        "error": r.get("error"),
                        "request_id": r.get("request_id"),
                    }
                )

        quality_metrics = {}
        if isinstance(lead_aggregate, dict):
            quality_metrics = lead_aggregate.get("quality_metrics") or {}

        return {
            "lead_id": lead_id,
            "vertical": v.vertical_id,
            "mode": vision_output.get("mode"),
            "reason": vision_output.get("reason"),
            "photo_prediction_count": len(photo_predictions)
            if isinstance(photo_predictions, list)
            else 0,
            "photo_predictions": per_photo_preview,
            "lead_aggregate": lead_aggregate,
            "decision_diagnostics": {
                "decision": (lead_aggregate or {}).get("decision")
                if isinstance(lead_aggregate, dict)
                else None,
                "reasons": (lead_aggregate or {}).get("decision_reasons", [])
                if isinstance(lead_aggregate, dict)
                else [],
                "confidence": (lead_aggregate or {}).get("decision_confidence")
                if isinstance(lead_aggregate, dict)
                else None,
                "blur_score": quality_metrics.get("blur_score"),
                "brightness_score": quality_metrics.get("brightness_score"),
                "wall_visibility_score": quality_metrics.get("wall_visibility_score"),
                "obstruction_score": quality_metrics.get("obstruction_score"),
                "coverage_score": quality_metrics.get("coverage_score"),
                "uncertainty_score": quality_metrics.get("uncertainty_score"),
                "avg_quote_relevance": quality_metrics.get("avg_quote_relevance"),
            },
            "needs_review": bool(vision_output.get("needs_review", False)),
            "review_reasons": review_reasons,
            "provider_runs": provider_summary,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validate/{lead_id}")
def validate_vision_flow(lead_id: str, db: Session = Depends(get_db)):
    """
    Practical validation endpoint for one lead:
    - vision stage details per photo
    - aggregate
    - legacy image_predictions bridge
    - needs_review impact in quote output
    """
    if not settings.ENABLE_DEV_ROUTES:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        v = get_vertical("paintly")
        vision_output = v.run_vision(db, lead_id)
        if not isinstance(vision_output, dict):
            raise RuntimeError("vision_output_not_dict")

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead is None:
            raise RuntimeError("lead_not_found")

        quote_result = compute_quote_for_lead(db=db, lead=lead, render_html=False)
        estimate = quote_result.get("estimate_json")
        if not isinstance(estimate, dict):
            raise RuntimeError("estimate_json_not_dict")

        current_reasons = needs_review_from_output(estimate)
        current_needs_review = bool(current_reasons)

        # Persist the debug validation outcome so the actual UI review queue updates.
        # UI uses Lead.status == "NEEDS_REVIEW".
        prev_status = getattr(lead, "status", None)
        lead.estimate_json = json.dumps(estimate, ensure_ascii=False, default=str)
        if current_needs_review:
            lead.status = "NEEDS_REVIEW"
        lead.updated_at = datetime.utcnow()
        db.add(lead)
        db.commit()
        db.refresh(lead)

        # Post-commit readback to ensure nothing overwrote the status after commit.
        lead_reloaded = db.query(Lead).filter(Lead.id == lead_id).first()
        persisted_status = getattr(lead_reloaded, "status", None) if lead_reloaded else None
        persisted_needs_review_reasons = []
        try:
            if isinstance(getattr(lead_reloaded, "estimate_json", None), str) and lead_reloaded.estimate_json:
                persisted_est = json.loads(lead_reloaded.estimate_json)
                persisted_needs_review_reasons = (persisted_est.get("meta") or {}).get(
                    "needs_review_reasons", []
                ) or []
        except Exception:
            persisted_needs_review_reasons = []

        logger.info(
            "VISION_VALIDATE_PERSIST lead_id=%s prev_status=%r final_needs_review=%s persisted_status=%r reasons=%r",
            lead_id,
            prev_status,
            current_needs_review,
            persisted_status,
            current_reasons,
        )

        logger.info(
            "VISION_VALIDATE_PERSIST_POSTREAD lead_id=%s tenant_id=%r final_needs_review=%s persisted_status=%r persisted_needs_review_reasons=%r",
            lead_id,
            getattr(lead_reloaded, "tenant_id", None) if lead_reloaded else None,
            current_needs_review,
            persisted_status,
            persisted_needs_review_reasons,
        )

        # Quick comparison: remove new vision meta signals to inspect impact.
        estimate_without_new_vision = dict(estimate)
        meta = dict(estimate.get("meta") or {})
        for key in (
            "vision_lead_aggregate",
            "vision_uncertainty_score",
            "vision_coverage_score",
            "vision_evidence_score",
            "vision_aggregate_needs_review",
            "vision_aggregate_review_reasons",
            "vision_photo_count",
            "vision_usable_photo_count",
            "vision_low_usability_photo_count",
            "vision_fallback_used",
        ):
            meta.pop(key, None)
        estimate_without_new_vision["meta"] = meta

        legacy_reasons = needs_review_from_output(estimate_without_new_vision)
        legacy_needs_review = bool(legacy_reasons)

        return {
            "lead_id": lead_id,
            "vertical": v.vertical_id,
            "vision_mode": vision_output.get("mode"),
            "vision_reason": vision_output.get("reason"),
            "photo_count": len(vision_output.get("photo_predictions") or []),
            "photo_inputs": vision_output.get("photo_inputs") or [],
            "photo_predictions": vision_output.get("photo_predictions") or [],
            "provider_runs": vision_output.get("vision_results") or [],
            "lead_aggregate": vision_output.get("lead_aggregate"),
            "legacy_image_predictions": vision_output.get("image_predictions") or [],
            "needs_review_inspection": {
                "with_new_vision_data": {
                    "needs_review": current_needs_review,
                    "reasons": current_reasons,
                },
                "without_new_vision_meta": {
                    "needs_review": legacy_needs_review,
                    "reasons": legacy_reasons,
                },
                "changed": current_needs_review != legacy_needs_review
                or current_reasons != legacy_reasons,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
