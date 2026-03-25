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
    needs_review = (
        usable_count == 0
        or coverage_score < 0.2
        or uncertainty_score > 0.7
        or "surface_preparation_required" in review_reasons
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
    )
