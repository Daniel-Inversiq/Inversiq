from __future__ import annotations

from app.domain.vision_models import DetectedSurface, VisionPhotoPrediction
from app.services.vision.aggregate import aggregate_predictions


def _pred(
    *,
    photo_id: str,
    photo_is_usable: bool,
    photo_usability_score: float,
    quote_relevance_score: float,
    uncertainty_score: float,
    review_flags: list[str] | None = None,
    wall_coverage: float = 0.75,
    surface_confidence: float = 0.9,
) -> VisionPhotoPrediction:
    return VisionPhotoPrediction(
        lead_id="lead-test",
        photo_id=photo_id,
        photo_is_usable=photo_is_usable,
        photo_usability_score=photo_usability_score,
        photo_usability_reasons=[],
        environment="indoor",
        environment_confidence=0.9,
        surfaces=(
            [
                DetectedSurface(
                    type="wall",
                    confidence=surface_confidence,
                    approximate_coverage=wall_coverage,
                    notes=None,
                )
            ]
            if wall_coverage > 0
            else []
        ),
        damages=[],
        complexity="low",
        complexity_confidence=0.8,
        quote_relevance_score=quote_relevance_score,
        uncertainty_score=uncertainty_score,
        review_flags=review_flags or [],
        summary="test",
        model_name="test-model",
        model_latency_ms=1,
        prompt_version="test",
    )


def test_clearly_usable_photo_is_accepted() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="1",
                photo_is_usable=True,
                photo_usability_score=0.95,
                quote_relevance_score=0.9,
                uncertainty_score=0.1,
            )
        ]
    )
    assert agg.decision == "ACCEPTED"
    assert agg.needs_review is False
    assert agg.decision_reasons == []
    assert "usable_ratio" in agg.quality_metrics


def test_usable_but_imperfect_photo_gets_warning_not_review() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="1",
                photo_is_usable=True,
                photo_usability_score=0.7,
                quote_relevance_score=0.65,
                uncertainty_score=0.78,
                review_flags=["surface_preparation_required"],
            )
        ]
    )
    assert agg.decision == "ACCEPTED_WITH_WARNING"
    assert agg.needs_review is False
    assert "surface_preparation_required" in agg.warning_reasons


def test_blurry_or_no_surface_photo_is_needs_review() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="1",
                photo_is_usable=False,
                photo_usability_score=0.2,
                quote_relevance_score=0.05,
                uncertainty_score=0.95,
                review_flags=["too_blurry", "no_clear_surface_detected"],
                wall_coverage=0.0,
            )
        ]
    )
    assert agg.decision == "NEEDS_REVIEW"
    assert agg.needs_review is True
    assert "too_blurry" in agg.decision_reasons or "no_usable_photos" in agg.decision_reasons


def test_usable_wall_with_surrounding_objects_is_not_hard_reviewed() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="wall-objects",
                photo_is_usable=True,
                photo_usability_score=0.76,
                quote_relevance_score=0.71,
                uncertainty_score=0.58,
                review_flags=[
                    "contains_furniture",
                    "contains_door_or_window",
                    "imperfect_framing",
                    "no_clear_surface_detected",
                ],
                wall_coverage=0.22,
                surface_confidence=0.31,
            )
        ]
    )
    assert agg.decision in {"ACCEPTED", "ACCEPTED_WITH_WARNING"}
    assert agg.decision != "NEEDS_REVIEW"
    assert agg.needs_review is False


def test_usable_but_imperfect_wall_photo_prefers_warning() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="wall-imperfect",
                photo_is_usable=True,
                photo_usability_score=0.66,
                quote_relevance_score=0.62,
                uncertainty_score=0.74,
                review_flags=["contains_mirror", "angle_not_ideal"],
                wall_coverage=0.18,
                surface_confidence=0.37,
            )
        ]
    )
    assert agg.decision == "ACCEPTED_WITH_WARNING"
    assert agg.needs_review is False


def test_too_dark_photo_is_needs_review() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="too-dark",
                photo_is_usable=False,
                photo_usability_score=0.18,
                quote_relevance_score=0.18,
                uncertainty_score=0.91,
                review_flags=["too_dark", "no_clear_surface_detected"],
                wall_coverage=0.0,
            )
        ]
    )
    assert agg.decision == "NEEDS_REVIEW"
    assert agg.needs_review is True
    assert "too_dark" in agg.decision_reasons or "extreme_lighting" in agg.decision_reasons


def test_wrong_subject_photo_is_needs_review() -> None:
    agg = aggregate_predictions(
        [
            _pred(
                photo_id="wrong-subject",
                photo_is_usable=False,
                photo_usability_score=0.24,
                quote_relevance_score=0.1,
                uncertainty_score=0.86,
                review_flags=["not_paintable_surface", "no_clear_surface_detected"],
                wall_coverage=0.0,
            )
        ]
    )
    assert agg.decision == "NEEDS_REVIEW"
    assert agg.needs_review is True
    assert any(
        reason in agg.decision_reasons
        for reason in ("not_paintable_surface", "no_paintable_surface_visible")
    )
