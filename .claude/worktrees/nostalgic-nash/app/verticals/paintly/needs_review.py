# app/verticals/paintly/needs_review.py
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


US_PAINTERS_NEEDS_REVIEW_COPY = {
    "headline": "Thanks — we’ll review this and get back to you shortly.",
    "body": (
        "Your project needs a quick manual check to make sure the estimate is accurate. "
        "You don’t need to do anything right now."
    ),
}

PAINTLY_NEEDS_REVIEW_COPY = {
    "intro": "We hebben nog een korte handmatige check nodig om de prijs 100% zeker te maken.",
    "range_explanation": "We bevestigen oppervlakken, voorbereiding en bereikbaarheid. Daarna ontvang je de definitieve prijs.",
}


def _get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def needs_review_from_output(estimate: Any) -> List[str]:
    """
    Returns a list of reasons. Empty list => OK to auto-deliver.

    "Preset B" (recommended):
    - Block only on truly broken output (missing/invalid total).
    - Otherwise: only flag NEEDS_REVIEW when 2+ soft signals stack up.
    """
    if not isinstance(estimate, dict):
        logger.debug("PAINTLY_NEEDS_REVIEW_DEBUG estimate_not_dict")
        return ["estimate_not_dict"]

    reasons: List[str] = []
    soft: List[str] = []

    # ------------------------------------------------------------------
    # HARD requirement: we must have a non-zero total
    # NOTE: PricingOutput uses totals.grand_total (and totals.pre_tax).
    # ------------------------------------------------------------------
    total = (
        _get(estimate, "totals.grand_total", None)
        or _get(estimate, "totals.pre_tax", None)
        or _get(estimate, "total_eur", None)
        or _get(estimate, "total", None)
    )

    if total is None:
        reasons.append("missing_total")
    else:
        try:
            total_val = float(total)
            if total_val <= 0:
                reasons.append("non_positive_total")
        except Exception:
            reasons.append("total_not_numeric")

    # If we already have blockers, stop here
    if reasons:
        logger.debug("PAINTLY_NEEDS_REVIEW_DEBUG early_return_reasons=%r", reasons)
        return reasons

    # ------------------------------------------------------------------
    # SOFT signals (only escalate if multiple)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Vision aggregate hard coupling (fix for missed propagation)
    # ------------------------------------------------------------------
    agg_needs_review = _get(estimate, "meta.vision_aggregate_needs_review", False)
    agg_review_reasons_raw = _get(
        estimate, "meta.vision_aggregate_review_reasons", None
    )
    logger.debug(
        "PAINTLY_NEEDS_REVIEW_DEBUG aggregate_coupling agg_needs_review=%r agg_review_reasons_raw=%r",
        agg_needs_review,
        agg_review_reasons_raw,
    )
    if agg_needs_review is True:
        if isinstance(agg_review_reasons_raw, list) and any(
            r == "surface_preparation_required"
            for r in agg_review_reasons_raw
            if isinstance(r, str)
        ):
            final = ["vision:surface_preparation_required"]
            logger.debug(
                "PAINTLY_NEEDS_REVIEW_DEBUG aggregate_hard_trigger final_reasons=%r",
                final,
            )
            return final

        final = ["vision:aggregate_needs_review"]
        logger.debug(
            "PAINTLY_NEEDS_REVIEW_DEBUG aggregate_hard_trigger final_reasons=%r",
            final,
        )
        return final

    # Vision wants manual review (MVP safety rail)
    vision_needs_review = _get(estimate, "meta.vision_needs_review", None)
    vr = _get(estimate, "meta.vision_review_reasons", None)
    agg_vr = _get(estimate, "meta.vision_aggregate_review_reasons", None)
    logger.debug(
        "PAINTLY_NEEDS_REVIEW_DEBUG vision_needs_review=%r vision_review_reasons=%r vision_aggregate_review_reasons=%r",
        vision_needs_review,
        vr,
        agg_vr,
    )
    if vision_needs_review is True:
        # treat as a soft signal; it will trigger review if another soft signal is present
        soft.append("vision_needs_review")

        # add the specific reasons (also soft)
        if isinstance(vr, list):
            for r in vr:
                if isinstance(r, str) and r:
                    soft.append(f"vision:{r}")

            # Strong paintly trigger: when preparation is likely needed, always review.
            if any(
                r == "surface_preparation_required" for r in vr if isinstance(r, str)
            ) or (isinstance(agg_vr, list) and any(r == "surface_preparation_required" for r in agg_vr if isinstance(r, str))):
                final = ["vision:surface_preparation_required"]
                logger.debug("PAINTLY_NEEDS_REVIEW_DEBUG final_reasons=%r", final)
                return final

    # Line items presence
    items = _get(estimate, "line_items", None) or _get(estimate, "items", None)
    if not items or (isinstance(items, list) and len(items) == 0):
        soft.append("no_line_items")

    # Vision confidence if present (optional field)
    conf = _get(estimate, "meta.confidence", None) or _get(estimate, "confidence", None)
    if conf is not None:
        try:
            c = float(conf)
            if c < 0.45:
                # very low confidence -> treat as blocker-ish (but still "soft" bucket)
                # if you want this to be a hard blocker, move to `reasons.append(...)`
                soft.append("confidence_low")
            elif c < 0.65:
                soft.append("confidence_medium")
        except Exception:
            soft.append("confidence_not_numeric")

    # Suspiciously low/high totals (tune as you like)
    try:
        tv = float(total)
        if tv < 200:
            soft.append("total_very_low")
        if tv > 25000:
            soft.append("total_very_high")
    except Exception:
        pass

    # Area checks (optional; only if you actually store it in output)
    # Keep this non-blocking.
    area_m2 = _get(estimate, "meta.area_m2", None) or _get(
        estimate, "inputs.area_m2", None
    )
    if area_m2 is not None:
        try:
            a = float(area_m2)
            if a < 8:
                soft.append("area_m2_too_small")
            if a > 250:
                soft.append("area_m2_too_large")
        except Exception:
            soft.append("area_m2_not_numeric")

    # ------------------------------------------------------------------
    # Vision risk score (new, simple and explainable)
    # ------------------------------------------------------------------
    # We keep this additive and transparent, then gate with a threshold.
    # Existing soft signals stay in place for backwards compatibility.
    risk_score = 0.0
    risk_reasons: List[str] = []

    # uncertainty_score (0..1)
    uncertainty = _get(estimate, "meta.vision_uncertainty_score", None)
    if uncertainty is not None:
        try:
            u = float(uncertainty)
            if u >= 0.8:
                risk_score += 0.40
                risk_reasons.append("risk:uncertainty_high")
            elif u >= 0.6:
                risk_score += 0.25
                risk_reasons.append("risk:uncertainty_medium")
        except Exception:
            risk_score += 0.10
            risk_reasons.append("risk:uncertainty_not_numeric")

    # coverage_score (0..1)
    coverage = _get(estimate, "meta.vision_coverage_score", None)
    if coverage is not None:
        try:
            c = float(coverage)
            if c < 0.2:
                risk_score += 0.35
                risk_reasons.append("risk:coverage_low")
            elif c < 0.4:
                risk_score += 0.20
                risk_reasons.append("risk:coverage_medium")
        except Exception:
            risk_score += 0.10
            risk_reasons.append("risk:coverage_not_numeric")

    # fallback usage (provider/legacy)
    if _get(estimate, "meta.vision_fallback_used", False) is True:
        risk_score += 0.25
        risk_reasons.append("risk:fallback_used")

    # low photo usability (aggregate and per-photo counts if present)
    low_usability_count = _get(estimate, "meta.vision_low_usability_photo_count", None)
    photo_count = _get(estimate, "meta.vision_photo_count", None)
    if low_usability_count is not None and photo_count is not None:
        try:
            lu = int(low_usability_count)
            pc = max(1, int(photo_count))
            ratio = lu / pc
            if ratio >= 0.5:
                risk_score += 0.25
                risk_reasons.append("risk:photo_usability_low")
        except Exception:
            pass

    # high-impact damages / review flags from aggregate
    agg_reasons = _get(estimate, "meta.vision_aggregate_review_reasons", None)
    if isinstance(agg_reasons, list):
        rset = {str(r) for r in agg_reasons}
        if "no_usable_photos" in rset:
            risk_score += 0.35
            risk_reasons.append("risk:no_usable_photos")
        if "high_uncertainty" in rset:
            risk_score += 0.20
            risk_reasons.append("risk:high_uncertainty")
        if "low_coverage_score" in rset:
            risk_score += 0.20
            risk_reasons.append("risk:low_coverage_score")

    agg = _get(estimate, "meta.vision_lead_aggregate", None)
    if isinstance(agg, dict):
        damages = agg.get("damages")
        if isinstance(damages, list):
            severe_damage_found = False
            for d in damages:
                if not isinstance(d, dict):
                    continue
                t = str(d.get("type", "")).strip().lower()
                sev = str(d.get("severity", "")).strip().lower()
                try:
                    conf = float(d.get("confidence", 0.0))
                except Exception:
                    conf = 0.0
                if t in {"wood_rot_possible", "moisture_stain", "mold"} and (
                    sev == "high" or conf >= 0.7
                ):
                    severe_damage_found = True
                    break
            if severe_damage_found:
                risk_score += 0.30
                risk_reasons.append("risk:high_impact_damage")

    # contradictions / low confidence conflicts
    vis_conf = _get(estimate, "meta.vision_signal_confidence", None)
    if vis_conf is not None and uncertainty is not None:
        try:
            vc = float(vis_conf)
            u = float(uncertainty)
            if vc < 0.45 and u >= 0.7:
                risk_score += 0.20
                risk_reasons.append("risk:low_confidence_conflict")
        except Exception:
            pass

    risk_score = max(0.0, min(1.0, risk_score))
    if risk_score >= 0.50:
        soft.extend(risk_reasons)
        soft.append(f"risk:score={risk_score:.2f}")

    # Escalate only if multiple soft signals (legacy behavior)
    if len(soft) >= 2:
        # dedupe while preserving order
        final = list(dict.fromkeys(soft))
        logger.debug("PAINTLY_NEEDS_REVIEW_DEBUG final_reasons=%r", final)
        return final

    logger.debug("PAINTLY_NEEDS_REVIEW_DEBUG final_reasons=%r", [])
    return []
