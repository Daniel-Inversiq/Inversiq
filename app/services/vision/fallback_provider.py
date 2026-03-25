from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.domain.vision_models import VisionExecutionResult, VisionPhotoPrediction, VisionStepInput
from app.tasks.vision import predict_images

logger = logging.getLogger(__name__)


def _to_prediction_from_legacy(
    *,
    inp: VisionStepInput,
    legacy: dict[str, Any],
) -> VisionPhotoPrediction:
    substrate_conf = float(legacy.get("substrate_confidence", 0.4) or 0.4)
    issues = legacy.get("issues") if isinstance(legacy.get("issues"), list) else []
    uncertainty = 1.0 - max(0.0, min(1.0, substrate_conf))
    review_flags = []
    if inp.photo_quality.usability_score < 0.5:
        review_flags.append("low_photo_usability")
    if uncertainty >= 0.7:
        review_flags.append("high_uncertainty")

    return VisionPhotoPrediction(
        lead_id=inp.lead_id,
        photo_id=inp.photo_id,
        photo_is_usable=bool(inp.photo_quality.usability_score >= 0.4),
        photo_usability_score=float(inp.photo_quality.usability_score),
        photo_usability_reasons=[],
        environment="unknown",
        environment_confidence=0.0,
        surfaces=[],
        damages=[],
        complexity="unknown",
        complexity_confidence=0.0,
        quote_relevance_score=0.0,
        uncertainty_score=max(0.0, min(1.0, uncertainty)),
        review_flags=review_flags,
        summary=f"Legacy fallback predictor used ({legacy.get('method', 'unknown')}).",
        model_name="legacy_predict_images_fallback",
        model_latency_ms=0,
        prompt_version="vision_v1",
    )


def run_existing_fallback_predictor(inp: VisionStepInput) -> VisionExecutionResult:
    """
    Project-correct fallback wired to existing app.tasks.vision.predict_images.
    Requires metadata.local_path from vision task wiring.
    """
    local_path = str(inp.metadata.get("local_path", "") or "").strip()
    if not local_path:
        raise RuntimeError("fallback_requires_metadata_local_path")
    if not Path(local_path).exists():
        raise RuntimeError("fallback_local_path_not_found")

    predictions = predict_images([local_path])
    if not predictions:
        raise RuntimeError("fallback_predict_images_empty")
    legacy = predictions[0] if isinstance(predictions[0], dict) else {}

    prediction = _to_prediction_from_legacy(inp=inp, legacy=legacy)
    logger.info(
        "Vision fallback predictor used lead_id=%s photo_id=%s method=%s",
        inp.lead_id,
        inp.photo_id,
        legacy.get("method"),
    )
    return VisionExecutionResult(
        source="fallback",
        prediction=prediction,
        raw_response={"legacy_fallback": legacy},
        error=None,
    )
