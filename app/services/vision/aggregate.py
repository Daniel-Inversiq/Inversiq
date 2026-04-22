from __future__ import annotations

from collections import defaultdict
import logging

from app.domain.vision_models import (
    DetectedDamage,
    DetectedSurface,
    LeadVisionAggregate,
    VisionPhotoPrediction,
)

logger = logging.getLogger(__name__)

HARD_REVIEW_FLAGS = {
    "photo_unreadable",
    "too_dark",
    "too_blurry",
    "no_clear_surface_detected",
    "not_paintable_surface",
}

# Flags that should never hard-route to manual review on their own for
# painter quote intake; they can still appear as warnings.
NON_BLOCKING_REVIEW_REASONS = {
    "surface_preparation_required",
    "contains_furniture",
    "contains_door_or_window",
    "contains_mirror",
    "partial_room_view",
    "imperfect_framing",
    "angle_not_ideal",
    "composition_not_clean",
}


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _clamp_01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _complexity_to_score(level: str) -> float:
    if level == "high":
        return 1.0
    if level == "medium":
        return 0.5
    if level == "low":
        return 0.0
    return 0.5


def _score_to_complexity(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def aggregate_predictions(preds: list[VisionPhotoPrediction]) -> LeadVisionAggregate:
    if not preds:
        return LeadVisionAggregate(
            lead_id="unknown",
            environment="unknown",
            environment_confidence=0.0,
            dominant_surfaces=[],
            damages=[],
            overall_complexity="unknown",
            overall_complexity_confidence=0.0,
            coverage_score=0.0,
            evidence_score=0.0,
            uncertainty_score=1.0,
            needs_review=True,
            review_reasons=["no_predictions"],
            decision="NEEDS_REVIEW",
            decision_reasons=["no_predictions"],
            warning_reasons=[],
            decision_confidence=1.0,
            quality_metrics={
                "usable_ratio": 0.0,
                "coverage_score": 0.0,
                "uncertainty_score": 1.0,
                "avg_quote_relevance": 0.0,
            },
        )

    lead_id = preds[0].lead_id
    usable_preds = [p for p in preds if p.photo_is_usable]
    usable_count = len(usable_preds)
    total_count = len(preds)

    env_scores: dict[str, float] = defaultdict(float)
    for p in preds:
        env_scores[p.environment] += _clamp_01(p.environment_confidence)
    dominant_environment = max(env_scores.items(), key=lambda it: it[1])[0] if env_scores else "unknown"
    total_env_score = sum(env_scores.values())
    environment_confidence = _clamp_01(_safe_div(env_scores.get(dominant_environment, 0.0), total_env_score))

    surface_weight_sum: dict[str, float] = defaultdict(float)
    surface_conf_sum: dict[str, float] = defaultdict(float)
    surface_coverage_sum: dict[str, float] = defaultdict(float)
    for p in preds:
        # Paintly quote-context: avoid letting non-paint surfaces (floors etc.)
        # that normalize to "unknown" pollute dominant_surfaces.
        quote_context = float(getattr(p, "quote_relevance_score", 0.0) or 0.0) >= 0.5
        for s in p.surfaces:
            if quote_context and s.type == "unknown":
                continue
            weight = _clamp_01(s.confidence) * _clamp_01(s.approximate_coverage)
            surface_weight_sum[s.type] += weight
            surface_conf_sum[s.type] += _clamp_01(s.confidence)
            surface_coverage_sum[s.type] += _clamp_01(s.approximate_coverage)

    dominant_surfaces: list[DetectedSurface] = []
    for surface_type, total_weight in sorted(
        surface_weight_sum.items(),
        key=lambda it: it[1],
        reverse=True,
    )[:3]:
        avg_conf = _safe_div(surface_conf_sum[surface_type], max(1, total_count))
        avg_cov = _safe_div(surface_coverage_sum[surface_type], max(1, total_count))
        dominant_surfaces.append(
            DetectedSurface(
                type=surface_type,
                confidence=_clamp_01(avg_conf),
                approximate_coverage=_clamp_01(avg_cov),
                notes=None,
            )
        )

    damage_conf_sum: dict[str, float] = defaultdict(float)
    damage_count: dict[str, int] = defaultdict(int)
    severity_high_flags: dict[str, bool] = defaultdict(bool)
    for p in preds:
        for d in p.damages:
            if d.type == "none":
                continue
            damage_conf_sum[d.type] += _clamp_01(d.confidence)
            damage_count[d.type] += 1
            if d.severity == "high":
                severity_high_flags[d.type] = True

    combined_damages: list[DetectedDamage] = []
    for damage_type, count in sorted(damage_count.items(), key=lambda it: damage_conf_sum[it[0]], reverse=True):
        avg_conf = _safe_div(damage_conf_sum[damage_type], count)
        severity = "high" if severity_high_flags[damage_type] else None
        combined_damages.append(
            DetectedDamage(
                type=damage_type,
                confidence=_clamp_01(avg_conf),
                severity=severity,
                notes=None,
            )
        )

    coverage_score = _clamp_01(
        _safe_div(sum(s.approximate_coverage for p in preds for s in p.surfaces), max(1.0, float(total_count)))
    )

    usable_ratio = _safe_div(float(usable_count), float(total_count))
    avg_quote_relevance = _safe_div(sum(_clamp_01(p.quote_relevance_score) for p in preds), float(total_count))
    evidence_score = _clamp_01((0.4 * usable_ratio) + (0.3 * coverage_score) + (0.3 * avg_quote_relevance))

    uncertainty_score = _clamp_01(
        _safe_div(sum(_clamp_01(p.uncertainty_score) for p in preds), float(total_count))
    )

    complexity_weighted_sum = 0.0
    complexity_conf_sum = 0.0
    for p in preds:
        conf = _clamp_01(p.complexity_confidence)
        complexity_weighted_sum += _complexity_to_score(p.complexity) * conf
        complexity_conf_sum += conf
    if complexity_conf_sum > 0:
        complexity_score = _safe_div(complexity_weighted_sum, complexity_conf_sum)
        overall_complexity = _score_to_complexity(complexity_score)
        overall_complexity_confidence = _clamp_01(
            _safe_div(complexity_conf_sum, float(total_count))
        )
    else:
        overall_complexity = "unknown"
        overall_complexity_confidence = 0.0

    review_reasons: set[str] = set()
    for p in preds:
        review_reasons.update(p.review_flags)

    logger.debug(
        "VISION_AGG_DEBUG review_reasons_before_extra=%r review_reasons_sorted=%r",
        list(review_reasons),
        sorted(review_reasons),
    )

    if usable_count == 0:
        review_reasons.add("no_usable_photos")
    if coverage_score < 0.2:
        review_reasons.add("low_coverage_score")
    if uncertainty_score > 0.7:
        review_reasons.add("high_uncertainty")

    surface_prep_present = "surface_preparation_required" in review_reasons
    blocking_review_reasons = {
        r for r in review_reasons if r not in NON_BLOCKING_REVIEW_REASONS
    }
    hard_flags_present = sorted(
        {
            flag
            for p in preds
            for flag in p.review_flags
            if flag in HARD_REVIEW_FLAGS
        }
    )
    wall_visibility_score = _clamp_01(
        _safe_div(
            sum(
                max(
                    (
                        _clamp_01(s.confidence) * _clamp_01(s.approximate_coverage)
                        for s in p.surfaces
                        if s.type in {"wall", "ceiling", "trim", "door", "window_frame", "facade", "wood"}
                    ),
                    default=0.0,
                )
                for p in preds
            ),
            float(total_count),
        )
    )
    blurry_ratio = _safe_div(
        float(sum(1 for p in preds if "too_blurry" in p.review_flags)),
        float(total_count),
    )
    dark_ratio = _safe_div(
        float(sum(1 for p in preds if "too_dark" in p.review_flags)),
        float(total_count),
    )
    bright_ratio = _safe_div(
        float(sum(1 for p in preds if "too_bright" in p.review_flags)),
        float(total_count),
    )
    obstructed_ratio = _safe_div(
        float(sum(1 for p in preds if "obstructed" in p.review_flags)),
        float(total_count),
    )
    blur_score = _clamp_01(1.0 - blurry_ratio)
    brightness_score = _clamp_01(1.0 - max(dark_ratio, bright_ratio))
    obstruction_score = _clamp_01(obstructed_ratio)

    hard_reason_set = set(hard_flags_present)
    if "no_clear_surface_detected" in hard_reason_set and (
        wall_visibility_score >= 0.16 or avg_quote_relevance >= 0.45
    ):
        hard_reason_set.discard("no_clear_surface_detected")
        warning_reason_set_note = "no_clear_surface_detected_softened"
    else:
        warning_reason_set_note = ""

    if usable_count == 0:
        hard_reason_set.add("no_usable_photos")
    if coverage_score < 0.08 and wall_visibility_score < 0.14:
        hard_reason_set.add("very_low_coverage_score")
    if uncertainty_score > 0.95:
        hard_reason_set.add("very_high_uncertainty")
    if blur_score < 0.3:
        hard_reason_set.add("extreme_blur")
    if brightness_score < 0.25:
        hard_reason_set.add("extreme_lighting")
    if wall_visibility_score < 0.1 and avg_quote_relevance < 0.25:
        hard_reason_set.add("no_paintable_surface_visible")

    warning_reason_set = set()
    if 0 < usable_count < total_count:
        warning_reason_set.add("some_photos_not_usable")
    if coverage_score < 0.25:
        warning_reason_set.add("limited_surface_coverage")
    if uncertainty_score > 0.7:
        warning_reason_set.add("elevated_uncertainty")
    if blur_score < 0.6:
        warning_reason_set.add("reduced_sharpness")
    if brightness_score < 0.55:
        warning_reason_set.add("challenging_lighting")
    if wall_visibility_score < 0.25:
        warning_reason_set.add("limited_wall_visibility")
    if obstruction_score > 0.6:
        warning_reason_set.add("high_obstruction")
    for r in blocking_review_reasons:
        if r not in hard_reason_set:
            warning_reason_set.add(r)
    if warning_reason_set_note:
        warning_reason_set.add(warning_reason_set_note)
    if surface_prep_present:
        warning_reason_set.add("surface_preparation_required")

    if hard_reason_set:
        decision = "NEEDS_REVIEW"
        decision_reasons = sorted(hard_reason_set)
    elif warning_reason_set:
        decision = "ACCEPTED_WITH_WARNING"
        decision_reasons = sorted(warning_reason_set)
    else:
        decision = "ACCEPTED"
        decision_reasons = []

    needs_review = decision == "NEEDS_REVIEW"
    decision_confidence = _clamp_01(
        (0.45 * usable_ratio) + (0.30 * (1.0 - uncertainty_score)) + (0.25 * avg_quote_relevance)
    )

    logger.debug(
        "VISION_AGG_DEBUG review_reasons_after_extra=%r surface_prep_present=%s needs_review=%s",
        sorted(review_reasons),
        surface_prep_present,
        needs_review,
    )

    return LeadVisionAggregate(
        lead_id=lead_id,
        environment=dominant_environment,
        environment_confidence=environment_confidence,
        dominant_surfaces=dominant_surfaces,
        damages=combined_damages,
        overall_complexity=overall_complexity,
        overall_complexity_confidence=overall_complexity_confidence,
        coverage_score=coverage_score,
        evidence_score=evidence_score,
        uncertainty_score=uncertainty_score,
        needs_review=needs_review,
        review_reasons=sorted(review_reasons),
        decision=decision,
        decision_reasons=decision_reasons,
        warning_reasons=sorted(warning_reason_set),
        decision_confidence=decision_confidence,
        quality_metrics={
            "usable_ratio": _clamp_01(usable_ratio),
            "coverage_score": coverage_score,
            "uncertainty_score": uncertainty_score,
            "avg_quote_relevance": _clamp_01(avg_quote_relevance),
            "blur_score": blur_score,
            "brightness_score": brightness_score,
            "wall_visibility_score": wall_visibility_score,
            "obstruction_score": obstruction_score,
        },
    )
