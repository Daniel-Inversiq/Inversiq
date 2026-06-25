from __future__ import annotations

from typing import Any


REVIEW_LABELS_NL = {
    # Specifieke labels uit vision/review output.
    "repair work required": "Herstelwerk nodig",
    "substrate visible": "Ondergrond zichtbaar",
    "surface damage detected": "Schade aan oppervlak",
    "surface preparation required": "Voorbereiding nodig",
    # Interne reason codes (snake_case en varianten).
    "repair_work_required": "Herstelwerk nodig",
    "substrate_visible": "Ondergrond zichtbaar",
    "surface_damage_detected": "Schade aan oppervlak",
    "surface_preparation_required": "Voorbereiding nodig",
    "vision:surface_preparation_required": "Voorbereiding nodig",
    "photo_validation_low_confidence": "Foto is onduidelijk of moeilijk te beoordelen",
    "photo_validation_low_confidence_soft": "Foto is onduidelijk of moeilijk te beoordelen",
    "photo_quality_score_low": "Fotokwaliteit onvoldoende",
    "photo_quality_score_low_soft": "Fotokwaliteit onvoldoende",
    "photo_not_relevant": "Foto lijkt niet relevant voor de offerte",
    "photo_quality_bad": "Fotokwaliteit onvoldoende",
    "no_images": "Geen bruikbare foto's gevonden",
    "no_photos": "Geen bruikbare foto's gevonden",
    "low_overall_confidence": "Onvoldoende zekerheid uit beeldanalyse",
    "low_vision_signal_confidence": "Onvoldoende visuele informatie in de foto",
    "few_images_low_confidence": "Te weinig duidelijke foto's voor betrouwbare beoordeling",
}


def _normalize_reason(reason: Any) -> str:
    value = str(reason or "").strip().lower()
    if not value:
        return ""
    value = " ".join(value.replace("-", " ").replace("_", " ").split())
    if value.startswith("vision:"):
        value = value[7:].strip()
    return value


def review_label_nl(reason: Any) -> str:
    raw = str(reason or "").strip()
    if not raw:
        return "Controle vereist"

    direct = REVIEW_LABELS_NL.get(raw)
    if direct:
        return direct

    normalized = _normalize_reason(raw)
    normalized_direct = REVIEW_LABELS_NL.get(normalized)
    if normalized_direct:
        return normalized_direct

    snake = raw.lower().replace("-", "_")
    snake_direct = REVIEW_LABELS_NL.get(snake)
    if snake_direct:
        return snake_direct

    readable = " ".join(raw.replace("_", " ").replace("-", " ").split())
    return readable[:1].upper() + readable[1:] if readable else "Controle vereist"
