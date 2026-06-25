from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

from app.core.settings import settings
from app.domain.vision_models import (
    DetectedDamage,
    DetectedSurface,
    VisionExecutionResult,
    VisionPhotoPrediction,
    VisionStepInput,
)
from app.services.vision.fallback_provider import run_existing_fallback_predictor

logger = logging.getLogger(__name__)

VISION_PROMPT_VERSION = "vision_v1_1_practical_intake"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

VISION_DEVELOPER_PROMPT = """
You are Paintly's visual inspection assistant for renovation leads.

Rules:
- Return ONLY valid JSON matching the schema.
- Focus only on visual observations from the photo.
- Do NOT estimate pricing, m2, labor, or costs.
- Do NOT invent details that are not visible.
- Use uncertainty conservatively; increase uncertainty when unclear.
- Evaluate photos for practical quote intake usability, not perfect composition.
- Accept imperfect framing, partial room visibility, and normal household objects
  when a paintable wall/surface is still clearly visible enough for first-pass quoting.
- Reserve hard review signals for truly unusable cases (very blurry, too dark,
  no paintable surface visible, or corrupted/unreadable image).
- Do NOT mark a photo unusable only because doors, mirrors, chairs, furniture,
  partial room framing, or imperfect composition are present.
- Use concise Dutch or English notes where useful.
""".strip()

VISION_RAW_SCHEMA: dict[str, Any] = {
    "name": "construction_vision_raw_output",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "photo_is_usable": {"type": "boolean"},
            "photo_usability_score": {"type": "number", "minimum": 0, "maximum": 1},
            "photo_usability_reasons": {
                "type": "array",
                "items": {"type": "string"},
            },
            "environment": {"type": "string"},
            "environment_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "surfaces": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "approximate_coverage": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["label", "confidence", "approximate_coverage", "notes"],
                },
            },
            "damages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "severity": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["label", "confidence", "severity", "notes"],
                },
            },
            "complexity": {"type": "string"},
            "complexity_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "quote_relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
            "uncertainty_score": {"type": "number", "minimum": 0, "maximum": 1},
            "review_flags": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": [
            "photo_is_usable",
            "photo_usability_score",
            "photo_usability_reasons",
            "environment",
            "environment_confidence",
            "surfaces",
            "damages",
            "complexity",
            "complexity_confidence",
            "quote_relevance_score",
            "uncertainty_score",
            "review_flags",
            "summary",
        ],
    },
    "strict": True,
}

SURFACE_NORMALIZE_MAP: dict[str, str] = {
    "muur": "wall",
    "wall": "wall",
    "wand": "wall",
    "plafond": "ceiling",
    "ceiling": "ceiling",
    "hout": "wood",
    "wood": "wood",
    "kozijn": "window_frame",
    "kozijnwerk": "window_frame",
    "window frame": "window_frame",
    "window_frame": "window_frame",
    "deur": "door",
    "door": "door",
    "trap": "stairs",
    "trappen": "stairs",
    "stairs": "stairs",
    "gevel": "facade",
    "facade": "facade",
    "lijstwerk": "trim",
    "trim": "trim",
    "metal": "metal",
    "metaal": "metal",
    "unknown": "unknown",
}

DAMAGE_NORMALIZE_MAP: dict[str, str] = {
    "scheur": "crack",
    "scheuren": "crack",
    "crack": "crack",
    "bladderende verf": "peeling_paint",
    "afbladderende verf": "peeling_paint",
    "peeling paint": "peeling_paint",
    "peeling_paint": "peeling_paint",
    "vocht": "moisture_stain",
    "vochtplek": "moisture_stain",
    "vochtvlek": "moisture_stain",
    "moisture stain": "moisture_stain",
    "moisture_stain": "moisture_stain",
    "schimmel": "mold",
    "mold": "mold",
    "houtrot": "wood_rot_possible",
    "wood rot": "wood_rot_possible",
    "wood_rot_possible": "wood_rot_possible",
    "vlek": "stain",
    "stain": "stain",
    "none": "none",
    "geen": "none",
    "unknown": "unknown",
    # English-ish synonyms for the keyword-based normalization as well.
    "dirty spot": "stain",
    "dirty spots": "stain",
    "scuff mark": "stain",
    "scuff marks": "stain",
    "smudge": "stain",
    "smudges": "stain",
}


def build_vision_user_prompt(inp: VisionStepInput) -> str:
    tasks = ", ".join(inp.requested_tasks) if inp.requested_tasks else "general_observation"
    metadata_json = json.dumps(inp.metadata, ensure_ascii=True, separators=(",", ":"))
    return (
        "Analyze this Paintly project photo and return structured JSON.\n"
        f"lead_id={inp.lead_id}\n"
        f"photo_id={inp.photo_id}\n"
        f"mime_type={inp.mime_type}\n"
        f"requested_tasks={tasks}\n"
        f"photo_quality={inp.photo_quality.model_dump_json()}\n"
        f"metadata={metadata_json}\n"
        "Focus on visible surfaces, visible damage signals, scene environment, complexity, and uncertainty."
    )


def _is_remote_image_access_error(exc: Exception) -> bool:
    msg = str(exc or "").lower()
    return (
        ("403" in msg)
        or ("forbidden" in msg)
        or ("access denied" in msg)
        or ("cannot access" in msg)
        or ("failed to download" in msg)
        or ("image_url" in msg and "invalid" in msg)
    )


def _env_truthy(name: str, default: str = "false") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


def call_openai_vision(
    image_url: str,
    user_prompt: str,
    client_request_id: str,
    metadata: dict[str, str],
) -> tuple[dict[str, Any], int, str]:
    started = time.perf_counter()
    model_name = DEFAULT_OPENAI_MODEL
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("invalid_external_image_url")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("OpenAI SDK is not installed/configured") from exc

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    image_input = build_image_input(image_url=image_url, metadata=metadata)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = client.responses.create(
            model=model_name,
            input=[
                {"role": "developer", "content": [{"type": "input_text", "text": VISION_DEVELOPER_PROMPT}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        image_input,
                    ],
                },
            ],
            text={"format": {"type": "json_schema", "name": VISION_RAW_SCHEMA["name"], "schema": VISION_RAW_SCHEMA["schema"], "strict": True}},
            extra_headers={"X-Client-Request-Id": client_request_id},
        )
    except Exception as exc:
        if _is_remote_image_access_error(exc):
            try:
                fallback_image_input = build_image_input(
                    image_url=image_url, metadata=metadata, force_data_url=True
                )
                logger.warning(
                    "Vision remote_url rejected; retrying with data_url request_id=%s image_url=%r err=%s",
                    client_request_id,
                    image_url,
                    exc,
                )
                response = client.responses.create(
                    model=model_name,
                    input=[
                        {"role": "developer", "content": [{"type": "input_text", "text": VISION_DEVELOPER_PROMPT}]},
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": user_prompt},
                                fallback_image_input,
                            ],
                        },
                    ],
                    text={"format": {"type": "json_schema", "name": VISION_RAW_SCHEMA["name"], "schema": VISION_RAW_SCHEMA["schema"], "strict": True}},
                    extra_headers={"X-Client-Request-Id": client_request_id},
                )
            except Exception:
                raise exc
        else:
            raise

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    output_text = getattr(response, "output_text", "") or ""
    if not output_text:
        # Compatibility fallback for SDK variants where output_text is absent.
        output = getattr(response, "output", None)
        if isinstance(output, list):
            for item in output:
                content = getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for chunk in content:
                    if getattr(chunk, "type", None) == "output_text":
                        text_part = getattr(chunk, "text", None)
                        if isinstance(text_part, str) and text_part.strip():
                            output_text = text_part
                            break
                if output_text:
                    break
    if not output_text:
        raise RuntimeError("OpenAI response did not include output_text")

    try:
        raw = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI response was not valid JSON") from exc

    return raw, elapsed_ms, model_name


def build_image_input(
    image_url: str, metadata: dict[str, str], force_data_url: bool = False
) -> dict[str, Any]:
    """
    OpenAI vision transport helper.

    For localhost/dev images, remote URLs may be blocked/unreachable from the OpenAI side.
    In that case, use metadata["local_path"] to send the image as a data URL.
    """
    normalized_url = (image_url or "").strip()
    parsed = urlparse(normalized_url)

    host = (parsed.hostname or "").lower() if parsed.hostname else ""
    url_lc = normalized_url.lower()
    is_local_dev = host in {"localhost", "127.0.0.1"} or "localhost" in url_lc or "127.0.0.1" in url_lc
    force_data_url_requested = bool(force_data_url or _env_truthy("VISION_FORCE_DATA_URL", "false"))
    allow_remote_url = _env_truthy("VISION_ALLOW_REMOTE_URL", "0")

    if (not is_local_dev) and (not force_data_url_requested):
        logger.info("Vision image transport via remote_url=%r", normalized_url)
        return {"type": "input_image", "image_url": normalized_url, "detail": "high"}

    local_path = metadata.get("local_path", "") or ""
    if not local_path:
        if force_data_url_requested and allow_remote_url:
            logger.warning(
                "Vision data_url forced but local_path missing; remote_url explicitly allowed. image_url=%r",
                normalized_url,
            )
            return {"type": "input_image", "image_url": normalized_url, "detail": "high"}
        logger.error(
            "Vision data_url transport requested but metadata['local_path'] is missing/empty. image_url=%r metadata_keys=%s force_data_url=%s",
            normalized_url,
            sorted(metadata.keys()),
            force_data_url_requested,
        )
        raise RuntimeError("local_path_missing_for_data_url_transport")

    try:
        with open(local_path, "rb") as f:
            raw_bytes = f.read()
    except FileNotFoundError as exc:
        logger.error(
            "Vision local dev image transport failed: local_path not found. local_path=%r image_url=%r",
            local_path,
            normalized_url,
        )
        raise RuntimeError("local_path_not_found_for_dev_image_transport") from exc
    except Exception as exc:
        logger.error(
            "Vision local dev image transport failed: cannot read local_path. local_path=%r image_url=%r err=%s",
            local_path,
            normalized_url,
            exc,
        )
        raise RuntimeError("local_path_unreadable_for_dev_image_transport") from exc

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"
    logger.info(
        "Vision image transport via data_url (local_path_used=%r) image_url=%r",
        local_path,
        normalized_url,
    )
    return {"type": "input_image", "image_url": data_url, "detail": "high"}


def normalize_surface(label: str) -> str:
    normalized = label.strip().lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    # Examples (real model outputs we’ve seen):
    # - "painted wall" -> wall
    # - "wall surface" -> wall
    # - "ceiling surface" -> ceiling
    # - "baseboard / skirting" -> trim
    # - "window frame" -> window_frame
    # - "door frame" -> door
    # - "wooden floor / floor" -> unknown (skip/ignore; not relevant for renovation scope)

    # Optioneel/veilig negeren van irrelevante oppervlakken.
    # We hebben geen quote-context hier, dus we map het altijd naar "unknown"
    # zodat het niet onbedoeld de dominant/coverage score beïnvloedt.
    if "floor" in normalized:
        logger.debug("normalize_surface skip floor label=%r normalized=%r", label, normalized)
        return "unknown"

    # Fuzzy keyword-based mapping first (handles phrases instead of exact keys).
    if "ceiling" in normalized or "plafond" in normalized:
        logger.debug("normalize_surface map ceiling label=%r normalized=%r", label, normalized)
        return "ceiling"
    if ("facade" in normalized or "exterior" in normalized) and "wall" in normalized:
        logger.debug("normalize_surface map facade label=%r normalized=%r", label, normalized)
        return "facade"
    if "baseboard" in normalized or "skirting" in normalized:
        logger.debug("normalize_surface map trim(baseboard/skirting) label=%r normalized=%r", label, normalized)
        return "trim"
    if "trim" in normalized and "window" not in normalized and "door" not in normalized:
        logger.debug("normalize_surface map trim label=%r normalized=%r", label, normalized)
        return "trim"
    if ("window" in normalized and "frame" in normalized) or "window frame" in normalized:
        logger.debug("normalize_surface map window_frame label=%r normalized=%r", label, normalized)
        return "window_frame"
    if ("door" in normalized and "frame" in normalized) or "door frame" in normalized:
        # Door_frame bestaat niet in onze SurfaceType; map naar de dichtstbijzijnde type.
        logger.debug("normalize_surface map door(label=%r) normalized=%r", label, normalized)
        return "door"
    if "wall" in normalized or "painted wall" in normalized or "wall surface" in normalized:
        logger.debug("normalize_surface map wall label=%r normalized=%r", label, normalized)
        return "wall"

    if normalized in SURFACE_NORMALIZE_MAP:
        return SURFACE_NORMALIZE_MAP[normalized]
    return "unknown"


def normalize_damage(label: str) -> str:
    normalized = label.strip().lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    # Examples we want to map from real model outputs:
    # - "wall stains" / "stain" / "dirty spots" -> stain
    # - "scuff marks" / "scuffs" / "smudges" -> (no dedicated type) => stain
    # - "peeling paint" -> peeling_paint
    # - "moisture stain" -> moisture_stain
    # - "mold" -> mold
    # - "hairline crack" / "crack" -> crack

    # Keyword-based rules first (handles phrases).
    # door-focused imperfections often show up as minor surface scuffs/smudges/marks;
    # our schema has no dedicated "scuff" type, so map to the closest "stain".
    if "door" in normalized and (
        "imperfection" in normalized
        or "imperfections" in normalized
        or "marks" in normalized
        or "mark" in normalized
    ):
        logger.debug("normalize_damage map door imperfections/marks to stain label=%r normalized=%r", label, normalized)
        return "stain"
    if "surface" in normalized and (
        "imperfection" in normalized
        or "imperfections" in normalized
        or "marks" in normalized
        or "mark" in normalized
    ):
        logger.debug("normalize_damage map surface imperfections/marks to stain label=%r normalized=%r", label, normalized)
        return "stain"

    # Additional real-world examples:
    # - "wall mark(s)" / "mark on wall" -> stain
    # - "surface mark" -> stain
    # - "smudge mark(s)" -> stain (smudge itself already maps to stain)
    if (
        ("wall" in normalized or "surface" in normalized)
        and ("mark" in normalized or "marks" in normalized)
    ):
        logger.debug("normalize_damage map wall/surface mark(s) to stain label=%r normalized=%r", label, normalized)
        return "stain"
    if "mark on" in normalized or "mark on wall" in normalized:
        logger.debug("normalize_damage map mark-on label=%r normalized=%r", label, normalized)
        return "stain"
    if "smudge mark" in normalized or "smudge marks" in normalized:
        logger.debug("normalize_damage map smudge mark(s) to stain label=%r normalized=%r", label, normalized)
        return "stain"

    if "wood rot" in normalized or ("wood" in normalized and "rot" in normalized):
        logger.debug("normalize_damage map wood_rot_possible label=%r normalized=%r", label, normalized)
        return "wood_rot_possible"
    if "peeling" in normalized and "paint" in normalized:
        logger.debug("normalize_damage map peeling_paint label=%r normalized=%r", label, normalized)
        return "peeling_paint"
    if "moisture" in normalized and "stain" in normalized:
        logger.debug("normalize_damage map moisture_stain label=%r normalized=%r", label, normalized)
        return "moisture_stain"
    if "mold" in normalized or "mould" in normalized:
        logger.debug("normalize_damage map mold label=%r normalized=%r", label, normalized)
        return "mold"
    if "crack" in normalized:
        logger.debug("normalize_damage map crack label=%r normalized=%r", label, normalized)
        return "crack"
    if "scuff" in normalized or "smudge" in normalized or "smudges" in normalized:
        # Geen "scuff" DamageType in onze schema/output; map naar dichtstbijzijnde categorie.
        logger.debug("normalize_damage map scuff/smudge to stain label=%r normalized=%r", label, normalized)
        return "stain"
    if "stain" in normalized or "dirty" in normalized or ("spot" in normalized and "stain" not in normalized):
        logger.debug("normalize_damage map stain label=%r normalized=%r", label, normalized)
        return "stain"

    if normalized in DAMAGE_NORMALIZE_MAP:
        return DAMAGE_NORMALIZE_MAP[normalized]
    return "unknown"


def _as_float_01(value: Any, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _as_int_non_negative(value: Any, default: int = 0) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, v)


def _as_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _normalize_environment(value: Any) -> str:
    env = str(value or "").strip().lower()
    # Handle both single tokens ("indoor") and longer phrases
    # ("interior residential space" -> indoor).
    if any(tok in env for tok in ["interior", "indoor", "inside", "binnen"]):
        logger.debug("normalize_environment map indoor label=%r env=%r", value, env)
        return "indoor"
    if any(tok in env for tok in ["outdoor", "outside", "buiten", "exterior"]):
        logger.debug("normalize_environment map outdoor label=%r env=%r", value, env)
        return "outdoor"
    return "unknown"


def _normalize_complexity(value: Any) -> str:
    c = str(value or "").strip().lower()
    if c in {"low", "laag"}:
        return "low"
    if c in {"medium", "gemiddeld", "middel"}:
        return "medium"
    if c in {"high", "hoog"}:
        return "high"
    return "unknown"


def _normalize_severity(value: Any) -> str | None:
    s = str(value or "").strip().lower()
    if s in {"low", "laag"}:
        return "low"
    if s in {"minor", "small", "mild"}:
        return "low"
    if s in {"medium", "gemiddeld", "middel"}:
        return "medium"
    if s in {"moderate"}:
        return "medium"
    if s in {"high", "hoog"}:
        return "high"
    if s in {"severe"}:
        return "high"
    return None


def normalize_vision_output(
    *,
    inp: VisionStepInput,
    raw_output: dict[str, Any],
    model_name: str,
    model_latency_ms: int,
    prompt_version: str = VISION_PROMPT_VERSION,
) -> VisionPhotoPrediction:
    surfaces_raw = raw_output.get("surfaces")
    damages_raw = raw_output.get("damages")

    surfaces: list[DetectedSurface] = []
    if isinstance(surfaces_raw, list):
        for item in surfaces_raw:
            if not isinstance(item, dict):
                continue
            surfaces.append(
                DetectedSurface(
                    type=normalize_surface(str(item.get("label", ""))),
                    confidence=_as_float_01(item.get("confidence"), 0.0),
                    approximate_coverage=_as_float_01(
                        item.get("approximate_coverage"),
                        0.0,
                    ),
                    notes=str(item.get("notes")).strip() if item.get("notes") is not None else None,
                )
            )

    damages: list[DetectedDamage] = []
    if isinstance(damages_raw, list):
        for item in damages_raw:
            if not isinstance(item, dict):
                continue
            damages.append(
                DetectedDamage(
                    type=normalize_damage(str(item.get("label", ""))),
                    confidence=_as_float_01(item.get("confidence"), 0.0),
                    severity=_normalize_severity(item.get("severity")),
                    notes=str(item.get("notes")).strip() if item.get("notes") is not None else None,
                )
            )

    review_flags = set(_as_list_of_str(raw_output.get("review_flags")))
    photo_usability_score = _as_float_01(raw_output.get("photo_usability_score"), 0.0)
    uncertainty_score = _as_float_01(raw_output.get("uncertainty_score"), 0.5)
    uncertainty_before = uncertainty_score
    complexity_level = _normalize_complexity(raw_output.get("complexity"))
    complexity_before = complexity_level
    complexity_confidence = _as_float_01(raw_output.get("complexity_confidence"), 0.0)
    has_clear_surface = any(s.type != "unknown" and s.confidence >= 0.4 for s in surfaces)
    has_paintable_surface_hint = any(
        s.type in {"wall", "ceiling", "trim", "door", "window_frame", "facade", "wood"}
        and s.confidence >= 0.25
        and s.approximate_coverage >= 0.12
        for s in surfaces
    )

    # Paintly (schilderwerk) review trigger: surface preparation likely required.
    # We base detection on raw_output labels/notes + summary, since the model
    # often uses "clean labels" like wall/stains/marks/smudges.
    preparation_required = False
    preparation_matched_keywords: list[str] = []
    preparation_trigger_source: set[str] = set()

    summary_text = str(raw_output.get("summary", "") or "").strip()
    summary_used = bool(summary_text)
    summary_lc = summary_text.lower()

    raw_environment = raw_output.get("environment")
    raw_summary = summary_text
    raw_surfaces_labels_notes: list[dict[str, Any]] = []
    if isinstance(surfaces_raw, list):
        for item in surfaces_raw:
            if not isinstance(item, dict):
                continue
            raw_surfaces_labels_notes.append(
                {
                    "label": item.get("label"),
                    "notes": item.get("notes"),
                }
            )

    raw_damages_labels_notes: list[dict[str, Any]] = []
    if isinstance(damages_raw, list):
        for item in damages_raw:
            if not isinstance(item, dict):
                continue
            raw_damages_labels_notes.append(
                {
                    "label": item.get("label"),
                    "notes": item.get("notes"),
                }
            )

    # Broad prep-needed signals (derived from real model text + renovation vocabulary).
    prep_keywords = [
        "exposed",
        "exposed wall",
        "exposed plaster",
        "exposed substrate",
        "underlayer",
        "bare wall",
        "partially removed",
        "partially stripped",
        "torn covering",
        "hanging material",
        "loose material",
        "lifted edge",
        "unfinished surface",
        "incomplete wall finish",
        "irregular removed area",
        "patchy removal",
        "scraped wall",
        "skim coat visible",
        "filler visible",
        "repair area",
        "stripped section",
        "peeled section",
        "peeled",
        "peeeling",
        "removed paint",
        "patchy surface",
        "patchy",
        "adhesive residue",
        "wallpaper removal",
        "wallpaper",
        "adhesive",
        "stripped",
        "stripping",
        "partially peeled",
        "removed",
        "loose",
        "lifted",
        "incomplete",
        "unfinished",
    ]

    # Coverage / pattern heuristics.
    max_surface_cov = 0.0
    wall_dominant_cov = 0.0
    stain_count = 0
    marks_like_count = 0
    marks_or_stains_count = 0
    uneven_found = False
    has_unfinished_exposed_hint = False

    surface_items_processed = 0
    damage_items_processed = 0

    if isinstance(surfaces_raw, list):
        for item in surfaces_raw:
            if not isinstance(item, dict):
                continue
            surface_items_processed += 1
            label_txt = str(item.get("label", "") or "").strip().lower()
            notes_txt = str(item.get("notes", "") or "").strip().lower()
            text = f"{label_txt} {notes_txt}".strip()
            cov = _as_float_01(item.get("approximate_coverage"), 0.0)
            max_surface_cov = max(max_surface_cov, cov)

            # Dominant wall coverage gate.
            if normalize_surface(label_txt) == "wall":
                wall_dominant_cov = max(wall_dominant_cov, cov)

            if "uneven" in text:
                uneven_found = True

            for kw in prep_keywords:
                if kw in text:
                    preparation_required = True
                    preparation_matched_keywords.append(kw)
                    has_unfinished_exposed_hint = True
                    preparation_trigger_source.add("surface_keyword_match")
                    break

    if isinstance(damages_raw, list):
        for item in damages_raw:
            if not isinstance(item, dict):
                continue
            damage_items_processed += 1
            label_txt = str(item.get("label", "") or "").strip().lower()
            notes_txt = str(item.get("notes", "") or "").strip().lower()
            text = f"{label_txt} {notes_txt}".strip()

            if "stain" in text:
                stain_count += 1

            if any(k in text for k in ["mark", "marks", "smudge", "smudges"]):
                marks_like_count += 1

            if any(
                k in text
                for k in ["mark", "marks", "smudge", "smudges", "stain", "stains"]
            ):
                marks_or_stains_count += 1

            # If damage notes mention exposed/removed states, it's prep-worthy even if
            # the damage label itself is "stain/marks/smudges".
            for kw in prep_keywords:
                if kw in text:
                    preparation_required = True
                    preparation_matched_keywords.append(kw)
                    has_unfinished_exposed_hint = True
                    preparation_trigger_source.add("damage_keyword_match")
                    break

    # Summary-based hint.
    if summary_used:
        for kw in prep_keywords:
            if kw in summary_lc:
                has_unfinished_exposed_hint = True
                preparation_matched_keywords.append(kw)
                preparation_trigger_source.add("summary_keyword_match")
                break

    # Heuristic 2: dominant wall (>0.4 coverage) + unfinished/exposed hint.
    if wall_dominant_cov > 0.4 and has_unfinished_exposed_hint:
        preparation_required = True
        preparation_trigger_source.add("wall_dominant_with_unfinished_hint")
        preparation_matched_keywords.append("wall_dominant_prep_heuristic")

    # Stains alone are usually still quote-usable for painter intake. Keep
    # prep escalation for stronger structural surface evidence only.
    if uneven_found:
        preparation_required = True
        preparation_trigger_source.add("uneven_surface")
        preparation_matched_keywords.append("uneven_surface")

    if preparation_required:
        review_flags.add("surface_preparation_required")
        uncertainty_score = _as_float_01(
            uncertainty_score + 0.2, uncertainty_score
        )
        if complexity_level in {"unknown", "low"}:
            complexity_level = "medium"
            complexity_confidence = max(complexity_confidence, 0.5)
        logger.debug(
            "surface_preparation_required trigger_source=%r matched_keywords=%r summary_used=%s wall_dominant_cov=%s lead_id=%s photo_id=%s",
            sorted(preparation_trigger_source),
            sorted(set(preparation_matched_keywords)),
            summary_used,
            wall_dominant_cov,
            inp.lead_id,
            inp.photo_id,
        )

    # Escalate explicit peeling/wall-damage signals to hard review flags.
    # This keeps the existing prep signal, but ensures clear structural paint
    # damage cannot be treated as non-blocking-only.
    peeling_damage_detected = any(
        d.type == "peeling_paint" and float(d.confidence or 0.0) >= 0.55
        for d in damages
    )
    summary_wallpaper_damage = False
    summary_repair_damage = False
    summary_substrate_exposed = False
    if summary_used:
        summary_wallpaper_damage = any(
            kw in summary_lc
            for kw in (
                "peeling wallpaper",
                "torn wallpaper",
                "loose wallpaper",
                "peeling wallcovering",
                "wallpaper removal",
            )
        )
        summary_substrate_exposed = any(
            kw in summary_lc
            for kw in (
                "exposed underlying surface",
                "exposed substrate",
                "underlying surface",
                "bare wall",
                "exposed plaster",
            )
        )
        summary_repair_damage = ("repair" in summary_lc) and any(
            ctx in summary_lc for ctx in ("wall", "wallpaper", "surface", "substrate")
        )

    if peeling_damage_detected or summary_wallpaper_damage or summary_repair_damage:
        review_flags.add("surface_damage_detected")
        review_flags.add("repair_work_required")
        if has_unfinished_exposed_hint or summary_substrate_exposed:
            review_flags.add("substrate_visible")

    if photo_usability_score < 0.5:
        review_flags.add("low_photo_usability")
    if uncertainty_score >= 0.7:
        review_flags.add("high_uncertainty")
    if inp.photo_quality.blur_detected:
        review_flags.add("too_blurry")
    if inp.photo_quality.too_dark:
        review_flags.add("too_dark")
    if inp.photo_quality.too_bright:
        review_flags.add("too_bright")
    if inp.photo_quality.obstructed:
        review_flags.add("obstructed")
    if not has_clear_surface and not has_paintable_surface_hint:
        review_flags.add("no_clear_surface_detected")

    logger.debug(
        "VISION_PREP_DEBUG raw_environment=%r raw_summary=%r summary_used=%s raw_surfaces_labels_notes=%r raw_damages_labels_notes=%r matched_preparation_keywords=%r preparation_trigger_source=%r preparation_required=%s complexity_before=%r complexity_after=%r uncertainty_before=%s uncertainty_after=%s review_flags_final=%r",
        raw_environment,
        raw_summary,
        summary_used,
        raw_surfaces_labels_notes,
        raw_damages_labels_notes,
        preparation_matched_keywords,
        sorted(set(preparation_trigger_source)),
        preparation_required,
        complexity_before,
        complexity_level,
        uncertainty_before,
        uncertainty_score,
        sorted(review_flags),
    )

    return VisionPhotoPrediction(
        lead_id=inp.lead_id,
        photo_id=inp.photo_id,
        photo_is_usable=bool(raw_output.get("photo_is_usable", photo_usability_score >= 0.5)),
        photo_usability_score=photo_usability_score,
        photo_usability_reasons=_as_list_of_str(raw_output.get("photo_usability_reasons")),
        environment=_normalize_environment(raw_output.get("environment")),
        environment_confidence=_as_float_01(raw_output.get("environment_confidence"), 0.0),
        surfaces=surfaces,
        damages=damages,
        complexity=complexity_level,
        complexity_confidence=complexity_confidence,
        quote_relevance_score=_as_float_01(raw_output.get("quote_relevance_score"), 0.0),
        uncertainty_score=uncertainty_score,
        review_flags=sorted(review_flags),
        summary=str(raw_output.get("summary") or "").strip() or "No summary provided.",
        model_name=model_name,
        model_latency_ms=_as_int_non_negative(model_latency_ms, default=0),
        prompt_version=prompt_version,
    )


def run_vision_step(inp: VisionStepInput) -> VisionExecutionResult:
    client_request_id = f"vision-{inp.lead_id}-{inp.photo_id}"
    user_prompt = build_vision_user_prompt(inp)

    try:
        logger.info(
            "Running OpenAI vision step lead_id=%s photo_id=%s request_id=%s",
            inp.lead_id,
            inp.photo_id,
            client_request_id,
        )
        raw_output, latency_ms, model_name = call_openai_vision(
            image_url=inp.image_url,
            user_prompt=user_prompt,
            client_request_id=client_request_id,
            metadata=inp.metadata,
        )
        prediction = normalize_vision_output(
            inp=inp,
            raw_output=raw_output,
            model_name=model_name,
            model_latency_ms=latency_ms,
            prompt_version=VISION_PROMPT_VERSION,
        )
        return VisionExecutionResult(
            source="openai",
            prediction=prediction,
            raw_response=raw_output,
            error=None,
        )
    except Exception as exc:
        logger.exception(
            "OpenAI vision step failed, using fallback lead_id=%s photo_id=%s err=%s",
            inp.lead_id,
            inp.photo_id,
            exc,
        )
        try:
            fallback_result = run_existing_fallback_predictor(inp)
            fallback_result.error = fallback_result.error or str(exc)
            if fallback_result.source != "fallback":
                fallback_result.source = "fallback"
            return fallback_result
        except Exception:
            # Last-resort safe fallback result that still respects the domain contract.
            minimal_prediction = VisionPhotoPrediction(
                lead_id=inp.lead_id,
                photo_id=inp.photo_id,
                photo_is_usable=False,
                photo_usability_score=0.0,
                photo_usability_reasons=["vision_step_failed"],
                environment="unknown",
                environment_confidence=0.0,
                surfaces=[],
                damages=[],
                complexity="unknown",
                complexity_confidence=0.0,
                quote_relevance_score=0.0,
                uncertainty_score=1.0,
                review_flags=["high_uncertainty", "no_clear_surface_detected"],
                summary="Vision step failed; fallback unavailable.",
                model_name="fallback_unavailable",
                model_latency_ms=0,
                prompt_version=VISION_PROMPT_VERSION,
            )
            return VisionExecutionResult(
                source="fallback",
                prediction=minimal_prediction,
                raw_response=None,
                error=str(exc),
            )
