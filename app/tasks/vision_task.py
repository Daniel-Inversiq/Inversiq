# app/tasks/vision_task.py
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.domain.vision_models import (
    PhotoQualityInput,
    VisionPhotoPrediction,
    VisionStepInput,
)
from app.models import Lead, LeadFile
from app.models.upload_record import UploadRecord
from app.services.photo_quality.inference import predict_photo_quality
from app.services.storage import get_storage
from app.services.vision.aggregate import aggregate_predictions
from app.services.vision.openai_provider import run_vision_step
from app.services.vision.persistence import persist_vision_artifacts

logger = logging.getLogger(__name__)


def _tmp_dir_for_lead(lead_id: str) -> Path:
    """
    Cloud Run only guarantees /tmp as writable.
    We keep a per-lead folder for repeatability during one run.
    """
    # Be robust across environments:
    # - Cloud Run: usually /tmp is writable
    # - Windows dev: "/tmp" is not a reliable location
    # - allow override via UPLOAD_DIR
    env_base = os.getenv("UPLOAD_DIR")
    base = Path(env_base) if env_base else (Path(tempfile.gettempdir()) / "uploads")
    d = base / "vision" / str(lead_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _collect_image_paths(files: List[Any], lead: Lead) -> List[str]:
    paths: List[str] = []
    lead_id = str(getattr(lead, "id", "") or "")
    tenant_id = str(getattr(lead, "tenant_id", "") or "").strip()
    logger.debug(
        "VISION_COLLECT_IMAGE_PATHS_START lead_id=%s tenant_id=%s source_count=%s",
        lead_id,
        tenant_id,
        len(files),
    )

    # 1) local_path if present and exists
    for idx, f in enumerate(files):
        lp = getattr(f, "local_path", None)
        raw_s3_key = getattr(f, "raw_s3_key", None)
        raw_object_key = getattr(f, "raw_object_key", None)
        source = getattr(f, "source", "?")
        s3_key = getattr(f, "s3_key", None)
        filename = Path(str(s3_key or "")).name if s3_key else None

        if lp:
            try:
                p = Path(str(lp))
                ok = p.exists() and p.is_file() and p.stat().st_size > 0
                logger.debug(
                    "VISION_PHOTO_RESOLVE local_path_attr idx=%s lead_id=%s source=%s file_source_id=%r raw_s3_key=%r raw_object_key=%r s3_key=%r filename=%r local_path=%r local_path_ok=%s",
                    idx,
                    lead_id,
                    source,
                    getattr(f, "id", None),
                    raw_s3_key,
                    raw_object_key,
                    s3_key,
                    filename,
                    str(lp),
                    ok,
                )
                if ok:
                    paths.append(str(p))
            except Exception:
                pass

    if paths:
        return paths

    # 2) fallback: download from Storage via s3_key
    storage = get_storage()
    if not tenant_id:
        raise RuntimeError(f"tenant_id_missing lead_id={lead_id}")

    logger.info(
        "VISION collect_image_paths: backend=%s tenant_id=%r lead_id=%s files=%s",
        storage.__class__.__name__,
        tenant_id,
        lead_id,
        len(files),
    )

    tmp_dir = _tmp_dir_for_lead(lead_id)

    import shutil
    from uuid import uuid4

    for idx, f in enumerate(files):
        key = getattr(f, "s3_key", None)
        raw_s3_key = getattr(f, "raw_s3_key", None)
        raw_object_key = getattr(f, "raw_object_key", None)
        source = getattr(f, "source", "?")
        filename = Path(str(key or "")).name if key else None

        # Best-effort: useful for debugging provider failures later.
        image_url: str | None = None
        try:
            if key:
                image_url = _build_image_url_for_vision(
                    storage, tenant_id=tenant_id, key=str(key).strip()
                )
        except Exception:
            image_url = None

        logger.info(
            "VISION file id=%s s3_key=%r local_path=%r",
            getattr(f, "id", None),
            key,
            getattr(f, "local_path", None),
        )

        if not key:
            continue

        key_str = str(key).strip().lstrip("/")
        tried_keys: list[str] = []
        key_candidates: list[str] = []
        key_candidates.append(key_str)

        tenant_prefix = f"{tenant_id}/"
        if key_str.startswith(tenant_prefix):
            # Backward compatibility: some rows may still store tenant-prefixed keys.
            key_candidates.append(key_str[len(tenant_prefix) :].lstrip("/"))

        # Deduplicate while keeping order
        seen_candidates: set[str] = set()
        deduped_candidates: list[str] = []
        for cand in key_candidates:
            if not cand:
                continue
            if cand in seen_candidates:
                continue
            seen_candidates.add(cand)
            deduped_candidates.append(cand)
        key_candidates = deduped_candidates

        if not key_candidates:
            continue

        resolved = False
        last_err: str | None = None

        for cand_key in key_candidates:
            tried_keys.append(cand_key)
            try:
                local_path = storage.download_to_temp_path(
                    tenant_id=tenant_id, key=cand_key
                )
                p = Path(local_path)
                if not (p.exists() and p.is_file() and p.stat().st_size > 0):
                    raise RuntimeError("download_returned_empty_file")

                # Always copy to stable name to avoid spaces/collisions
                suffix = p.suffix or (Path(cand_key).suffix or ".jpg")
                safe_name = f"{getattr(f, 'id', 'file')}_{uuid4().hex}{suffix}"
                dst = tmp_dir / safe_name
                if not dst.exists() or dst.stat().st_size == 0:
                    shutil.copyfile(p, dst)

                if not (dst.exists() and dst.is_file() and dst.stat().st_size > 0):
                    raise RuntimeError("stable_copy_failed_or_empty")

                paths.append(str(dst))
                resolved = True
                logger.debug(
                    "VISION_PHOTO_RESOLVE download_ok idx=%s lead_id=%s source=%s file_source_id=%r raw_s3_key=%r raw_object_key=%r s3_key=%r filename=%r image_url=%r tried_keys=%r resolved_key=%r local_path_for_debug=%r stable_dst=%r",
                    idx,
                    lead_id,
                    source,
                    getattr(f, "id", None),
                    raw_s3_key,
                    raw_object_key,
                    key,
                    filename,
                    image_url,
                    tried_keys,
                    cand_key,
                    local_path,
                    str(dst),
                )
                break

            except Exception as e:
                last_err = f"{type(e).__name__}:{e}"
                logger.debug(
                    "VISION_PHOTO_RESOLVE download_failed idx=%s lead_id=%s source=%s file_source_id=%r s3_key=%r tried_key=%r image_url=%r err=%s",
                    idx,
                    lead_id,
                    source,
                    getattr(f, "id", None),
                    key,
                    cand_key,
                    image_url,
                    last_err,
                )

        if not resolved and last_err:
            logger.debug(
                "VISION_PHOTO_RESOLVE no_valid_local_path idx=%s lead_id=%s source=%s file_source_id=%r s3_key=%r filename=%r image_url=%r tried_keys=%r last_err=%r",
                idx,
                lead_id,
                source,
                getattr(f, "id", None),
                key,
                filename,
                image_url,
                tried_keys,
                last_err,
            )

    logger.debug(
        "VISION_COLLECT_IMAGE_PATHS_DONE lead_id=%s tenant_id=%s resolved_local_image_paths=%s/%s",
        lead_id,
        tenant_id,
        len(paths),
        len(files),
    )
    return paths


def _normalize_storage_key(tenant_id: str, raw: str) -> str:
    key_raw = str(raw or "").strip().lstrip("/")
    if not key_raw:
        return ""
    tenant_prefix = f"{str(tenant_id or '').strip()}/"
    if tenant_prefix and tenant_prefix != "/":
        # Some historical/legacy records may contain the tenant prefix multiple times.
        # Strip it repeatedly to normalize to the storage key without tenant.
        while key_raw.startswith(tenant_prefix):
            key_raw = key_raw[len(tenant_prefix) :].lstrip("/")
    return key_raw


def _resolve_vision_file_sources(
    db: Session, lead: Lead
) -> tuple[List[Any], List[str]]:
    """
    Build one row per usable photo for vision.

    Primary: LeadFile (engine convention: tenant-less s3_key).
    Fallback: UploadRecord (intake may have upload_rows before LeadFile sync).

    Returns (file_like_sequence, skip_reasons).
    Each file_like supports: id, s3_key, content_type, local_path (optional), source.
    """
    tenant_id = str(getattr(lead, "tenant_id", "") or "").strip()
    reasons: List[str] = []
    seen: set[str] = set()
    out: List[Any] = []

    lead_files = db.query(LeadFile).filter(LeadFile.lead_id == lead.id).all()
    logger.info(
        "VISION_FILE_SOURCES lead_id=%s db_source=lead_files row_count=%s",
        lead.id,
        len(lead_files),
    )

    for lf in lead_files:
        raw_s3_key = str(getattr(lf, "s3_key", "") or "")
        key = _normalize_storage_key(tenant_id, raw_s3_key)
        if not key:
            reasons.append(
                f"lead_file:id={getattr(lf, 'id', None)}:missing_or_empty_s3_key"
            )
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(
            SimpleNamespace(
                id=getattr(lf, "id", None),
                s3_key=key,
                raw_s3_key=raw_s3_key,
                content_type=str(getattr(lf, "content_type", None) or "image/jpeg"),
                local_path=getattr(lf, "local_path", None),
                source="lead_file",
            )
        )

    # Supplement: upload_records (intake complete_upload) may exist before LeadFile sync
    # or may hold additional keys not yet reflected in lead_files.
    from app.models.upload_record import UploadStatus

    uq = db.query(UploadRecord).filter(UploadRecord.lead_id == str(lead.id))
    if tenant_id:
        uq = uq.filter(UploadRecord.tenant_id == tenant_id)
    upload_rows = uq.all()
    logger.info(
        "VISION_FILE_SOURCES_UPLOAD_SCAN lead_id=%s tenant_filter=%s upload_row_count=%s",
        lead.id,
        tenant_id or "(none)",
        len(upload_rows),
    )
    for rec in upload_rows:
        if rec.status != UploadStatus.uploaded:
            reasons.append(
                f"upload_record:id={rec.id}:status_not_uploaded:{rec.status}"
            )
            continue
        if not rec.is_image:
            reasons.append(
                f"upload_record:id={rec.id}:non_image_mime:{getattr(rec, 'mime', None)}"
            )
            continue
        raw_object_key = str(getattr(rec, "object_key", "") or "")
        key = _normalize_storage_key(tenant_id, raw_object_key)
        if not key:
            reasons.append(
                f"upload_record:id={rec.id}:empty_object_key_after_normalize"
            )
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(
            SimpleNamespace(
                id=f"ur_{rec.id}",
                s3_key=key,
                raw_object_key=raw_object_key,
                content_type=str(getattr(rec, "mime", None) or "image/jpeg"),
                local_path=None,
                source="upload_record",
            )
        )

    sources = [getattr(x, "source", "?") for x in out]
    logger.info(
        "VISION_FILE_SOURCES_RESULT lead_id=%s resolved_count=%s sources=%s first_skip_reasons=%s",
        lead.id,
        len(out),
        sources,
        reasons[:15],
    )
    return out, reasons


def _paintly_enabled() -> bool:
    """Paintly vision on by default; set ENABLE_PAINTLY=false to disable."""
    return bool(getattr(settings, "ENABLE_PAINTLY", True))


def _storage_kind() -> str:
    backend = str(getattr(settings, "STORAGE_BACKEND", "") or "").strip().lower()
    return "s3" if backend == "s3" else "local"


def _build_image_url_for_vision(storage, tenant_id: str, key: str) -> str:
    """
    Build an absolute URL usable by external vision providers.
    """
    raw_url = storage.public_url(tenant_id=tenant_id, key=key)
    parsed = urlparse(raw_url)
    if parsed.scheme and parsed.netloc:
        return raw_url

    base = str(getattr(settings, "APP_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if base:
        path = "/" + str(raw_url).lstrip("/")
        return f"{base}{path}"

    logger.error(
        "Vision image URL is not externally reachable tenant_id=%s key=%s raw_url=%s",
        tenant_id,
        key,
        raw_url,
    )
    raise RuntimeError(
        "external_image_url_unavailable: set APP_PUBLIC_BASE_URL or wire presigned/public URL resolver"
    )


def _build_photo_quality_input(
    issues: List[str], quality_score: float
) -> PhotoQualityInput:
    issues_lc = {str(i).strip().lower() for i in issues}
    blur_detected = "too_blurry" in issues_lc
    too_dark = "too_dark" in issues_lc
    too_bright = "too_bright" in issues_lc
    obstructed = "obstructed" in issues_lc
    resolution_score = 0.35 if "resolution_too_low" in issues_lc else 0.85
    exposure_score = 0.35 if (too_dark or too_bright) else 0.85
    sharpness_score = max(0.0, min(1.0, float(quality_score)))
    usability_score = max(0.0, min(1.0, float(quality_score)))
    return PhotoQualityInput(
        sharpness_score=sharpness_score,
        resolution_score=resolution_score,
        exposure_score=exposure_score,
        usability_score=usability_score,
        blur_detected=blur_detected,
        too_dark=too_dark,
        too_bright=too_bright,
        obstructed=obstructed,
    )


def _legacy_image_prediction_from_photo_pred(
    pred: VisionPhotoPrediction,
) -> Dict[str, Any]:
    if pred.surfaces:
        best_surface = max(
            pred.surfaces,
            key=lambda s: float(s.confidence) * float(s.approximate_coverage),
        )
        if best_surface.type in {
            "wall",
            "ceiling",
            "trim",
            "window_frame",
            "door",
            "wood",
        }:
            substrate = "gipsplaat"
        elif best_surface.type in {"facade", "stairs", "metal"}:
            substrate = "beton"
        else:
            substrate = "bestaand"
        substrate_conf = float(best_surface.confidence)
    else:
        substrate = "bestaand"
        substrate_conf = 0.4

    issues: List[str] = []
    issue_confidences: List[float] = []
    for d in pred.damages:
        if d.type in {"none", "unknown"}:
            continue
        if d.type == "crack":
            issues.append("scheuren")
        elif d.type in {"moisture_stain", "mold"}:
            issues.append("vocht")
        else:
            issues.append(d.type)
        issue_confidences.append(float(d.confidence))

    if not issues:
        issues = ["geen"]
        issue_confidences = [0.5]

    return {
        "substrate": substrate,
        "substrate_confidence": max(0.0, min(1.0, substrate_conf)),
        "issues": issues,
        "issue_confidences": issue_confidences,
        "method": "openai_vision_normalized",
    }


def run_vision_for_lead(db: Session, lead_id: str, *, lead=None) -> Dict[str, Any]:
    """
    Runs vision for a lead:
    - loads Lead + LeadFile
    - collects local image paths (local_path OR downloads via storage using s3_key)
    - runs predict_images(local_paths)
    - aggregates for paintly if enabled
    - stores on lead.vision_json or lead.vision_output

    If `lead` is provided (e.g. already loaded by the engine facade), the initial
    db.query(Lead) is skipped to avoid a redundant round-trip.
    """
    if lead is None:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError("Lead not found")

    file_sources, file_skip_reasons = _resolve_vision_file_sources(db, lead)
    if not file_sources:
        logger.error(
            "VISION_NO_RESOLVABLE_PHOTOS lead_id=%s tenant_id=%s skip_reasons=%s",
            lead.id,
            getattr(lead, "tenant_id", None),
            file_skip_reasons,
        )
        raise ValueError(
            "No usable photos for vision (no LeadFile.s3_key and no matching upload_records). "
            f"skip_reasons={file_skip_reasons[:25]}"
        )

    # Best-effort: collect local paths for debug/fallback predictors.
    # Never hard-fail the whole flow if storage/local resolution is flaky for a subset.
    image_paths = _collect_image_paths(file_sources, lead)
    if not image_paths:
        logger.warning(
            "VISION_IMAGE_PATHS_EMPTY lead_id=%s resolved_sources=%s. Continuing with best-effort OpenAI/fallback flow.",
            lead.id,
            len(file_sources),
        )

    # Legacy predictor import stays available for safe fallback.
    from app.tasks.vision import predict_images

    paintly_enabled = _paintly_enabled()
    logger.debug(
        "VISION_PAINTLY_ENABLED lead_id=%s paintly_enabled=%s",
        lead.id,
        paintly_enabled,
    )

    logger.debug(
        "VISION_PHOTO_COUNT lead_id=%s resolved_sources=%s collected_image_paths=%s",
        lead.id,
        len(file_sources),
        len(image_paths),
    )

    # Debug: keys are enough to map back to storage; local paths can be noisy.
    try:
        resolved_keys = [
            str(getattr(src, "s3_key", "") or "").strip() for src in file_sources
        ]
    except Exception:
        resolved_keys = []

    logger.debug(
        "VISION_IMAGE_KEYS lead_id=%s image_keys=%s",
        lead.id,
        resolved_keys,
    )

    # Debug: include local temp paths and best-effort OpenAI image URLs.
    # If APP_PUBLIC_BASE_URL is missing, URL building may fail; we keep going.
    logger.debug("VISION_IMAGE_PATHS lead_id=%s image_paths=%s", lead.id, image_paths)

    if not paintly_enabled:
        image_predictions = predict_images(image_paths)
        return {
            "mode": "image_predictions_only",
            "reason": "paintly_disabled",
            "image_predictions": image_predictions,
        }

    try:
        storage = get_storage()
        tenant_id = str(getattr(lead, "tenant_id", "") or "").strip()
        photo_predictions: List[VisionPhotoPrediction] = []
        vision_results: List[Dict[str, Any]] = []
        photo_inputs: List[Dict[str, Any]] = []

        logger.info(
            "VISION_RUN_START lead_id=%s photo_sources=%s source_breakdown=%s",
            lead.id,
            len(file_sources),
            [getattr(s, "source", "?") for s in file_sources],
        )

        # Best-effort image URLs for debug visibility (never blocks the flow).
        image_urls_debug: list[str | None] = []
        for src in file_sources:
            key = str(getattr(src, "s3_key", "") or "").strip()
            try:
                image_urls_debug.append(
                    _build_image_url_for_vision(storage, tenant_id=tenant_id, key=key)
                )
            except Exception as exc:
                logger.debug(
                    "VISION_IMAGE_URL_BUILD_FAILED lead_id=%s key=%s err=%s",
                    lead.id,
                    key,
                    exc,
                )
                image_urls_debug.append(None)
        logger.debug(
            "VISION_IMAGE_URLS lead_id=%s image_urls=%s",
            lead.id,
            image_urls_debug,
        )

        for idx, src in enumerate(file_sources):
            key = str(getattr(src, "s3_key", "") or "").strip()
            raw_s3_key = getattr(src, "raw_s3_key", None)
            raw_object_key = getattr(src, "raw_object_key", None)
            source = getattr(src, "source", "?")
            filename = Path(key).name if key else None

            if not key:
                logger.warning(
                    "VISION_SKIP_EMPTY_KEY lead_id=%s source=%s file_source_id=%r src=%r",
                    lead.id,
                    source,
                    getattr(src, "id", None),
                    src,
                )
                continue

            # Resolve strategies for each photo:
            # 1) local_path attr (rare; usually not present on our ORM rows)
            # 2) local download (download_to_temp_path) for legacy/fallback predictor
            # OpenAI step uses a best-effort image_url (public_url/APP_PUBLIC_BASE_URL).
            local_path_attr = getattr(src, "local_path", None)
            local_path_attr_ok = False
            if local_path_attr:
                try:
                    p = Path(str(local_path_attr))
                    local_path_attr_ok = (
                        p.exists() and p.is_file() and p.stat().st_size > 0
                    )
                except Exception:
                    local_path_attr_ok = False

            local_path_for_fallback = ""
            local_download_ok = False
            local_download_err: str | None = None
            try:
                local_path_for_fallback = str(
                    storage.download_to_temp_path(tenant_id=tenant_id, key=key)
                )
                local_download_ok = bool(
                    Path(local_path_for_fallback).exists()
                    and Path(local_path_for_fallback).is_file()
                )
            except Exception as e:
                local_download_err = f"{type(e).__name__}:{e}"
                # Keep flow running; OpenAI path may still succeed.
                local_path_for_fallback = ""

            image_url = ""
            image_url_build_ok = False
            image_url_build_err: str | None = None
            try:
                image_url = _build_image_url_for_vision(
                    storage, tenant_id=tenant_id, key=key
                )
                image_url_build_ok = bool(image_url)
            except Exception as exc:
                image_url_build_err = f"{type(exc).__name__}:{exc}"
                image_url = ""

            # Step 1..3 for a single photo (do not abort the whole lead).
            try:
                # Step 1: existing photo-quality inference (per photo).
                pq = predict_photo_quality([key], storage=storage, tenant_id=tenant_id)
                photo_quality = _build_photo_quality_input(
                    issues=list(getattr(pq, "issues", []) or []),
                    quality_score=float(getattr(pq, "quality_score", 0.0) or 0.0),
                )

                # Step 2: new OpenAI vision provider (with built-in fallback behavior).
                photo_id = str(getattr(src, "id", key))

                # pydantic metadata contract: dict[str, str]
                raw_s3_key_str = str(raw_s3_key or "").strip()
                raw_object_key_str = str(raw_object_key or "").strip()
                # Ensure these are never None in the metadata payload.
                raw_s3_key = raw_s3_key_str
                raw_object_key = raw_object_key_str
                local_path_attr_str = str(local_path_attr) if local_path_attr else ""

                logger.debug(
                    "VISION_PROVIDER_EXEC_START lead_id=%s idx=%s photo_id=%s source=%s s3_key=%r filename=%r image_url=%r local_path_for_fallback=%r raw_s3_key=%r raw_object_key=%r",
                    lead.id,
                    idx,
                    photo_id,
                    source,
                    key,
                    filename,
                    image_url,
                    local_path_for_fallback,
                    raw_s3_key_str,
                    raw_object_key_str,
                )

                raw_metadata: dict[str, Any] = {
                    "source": source,
                    "file_source": getattr(src, "source", "") or "",
                    "lead_file_id": getattr(src, "id", "") or "",
                    "s3_key": key,
                    "filename": filename,
                    "raw_s3_key": raw_s3_key,
                    "raw_object_key": raw_object_key,
                    # Needed by hard-wired legacy fallback predictor.
                    "local_path": local_path_for_fallback,
                    "local_path_attr": local_path_attr_str,
                }

                removed_none_keys = [k for k, v in raw_metadata.items() if v is None]
                sanitized_metadata = {
                    str(k): str(v) for k, v in raw_metadata.items() if v is not None
                }

                logger.info(
                    "VISION_METADATA_SANITIZED lead_id=%s removed_none_keys=%s sanitized_metadata=%r",
                    lead.id,
                    removed_none_keys,
                    sanitized_metadata,
                )

                storage_kind = _storage_kind()
                mime_type = str(getattr(src, "content_type", "") or "image/jpeg")
                photo_quality_input = photo_quality
                requested_tasks = [
                    "surface_detection",
                    "damage_detection",
                    "environment_classification",
                    "complexity_assessment",
                ]

                step_input = VisionStepInput(
                    lead_id=str(lead.id),
                    photo_id=str(photo_id),
                    image_url=image_url,
                    storage_kind=storage_kind,
                    mime_type=mime_type,
                    photo_quality=photo_quality_input,
                    requested_tasks=requested_tasks,
                    metadata=sanitized_metadata,
                )
                request_id = f"vision-{lead.id}-{photo_id}"

                logger.debug(
                    "VISION_STEP_INPUT_BUILT lead_id=%s photo_id=%s request_id=%s storage_kind=%s mime_type=%s requested_tasks=%s",
                    lead.id,
                    photo_id,
                    request_id,
                    step_input.storage_kind,
                    step_input.mime_type,
                    step_input.requested_tasks,
                )
                logger.debug(
                    "VISION_IMAGE_URL_VALUE lead_id=%s photo_id=%s image_url=%r",
                    lead.id,
                    photo_id,
                    image_url,
                )

                logger.debug(
                    "VISION_RUN_VISION_STEP_CALL lead_id=%s photo_id=%s",
                    lead.id,
                    photo_id,
                )
                result = run_vision_step(step_input)
                logger.debug(
                    "VISION_RUN_VISION_STEP_DONE lead_id=%s photo_id=%s provider_source=%s",
                    lead.id,
                    photo_id,
                    result.source,
                )

                logger.info(
                    "VISION_PHOTO_CLASSIFICATION lead_id=%s photo_id=%s provider=%s "
                    "review_flags=%r usability=%.3f uncertainty=%.3f relevance=%.3f "
                    "surfaces=%r damages=%r raw_review_flags=%r raw_summary=%r",
                    lead.id,
                    photo_id,
                    result.source,
                    list(result.prediction.review_flags or []),
                    float(result.prediction.photo_usability_score or 0.0),
                    float(result.prediction.uncertainty_score or 0.0),
                    float(result.prediction.quote_relevance_score or 0.0),
                    [
                        {
                            "label": getattr(s, "type", None),
                            "conf": float(getattr(s, "confidence", 0.0)),
                            "cov": float(getattr(s, "approximate_coverage", 0.0)),
                        }
                        for s in (result.prediction.surfaces or [])
                    ],
                    [
                        {
                            "label": getattr(d, "type", None),
                            "conf": float(getattr(d, "confidence", 0.0)),
                            "severity": getattr(d, "severity", None),
                        }
                        for d in (result.prediction.damages or [])
                    ],
                    (result.raw_response or {}).get("review_flags"),
                    (result.raw_response or {}).get("summary"),
                )

                photo_predictions.append(result.prediction)
                photo_inputs.append(step_input.model_dump())
                vision_results.append(
                    {
                        "request_id": request_id,
                        "photo_id": photo_id,
                        "file_source": getattr(src, "source", None),
                        "provider": result.source,
                        "model_name": result.prediction.model_name,
                        "prompt_version": result.prediction.prompt_version,
                        "latency_ms": int(result.prediction.model_latency_ms),
                        "error": result.error,
                        "raw_response": result.raw_response,
                        "normalized_prediction": result.prediction.model_dump(),
                    }
                )

            except Exception as exc:
                # Keep legacy fallback behavior as the last resort.
                logger.exception(
                    "VISION_PHOTO_ITERATION_FAILED lead_id=%s idx=%s s3_key=%r photo_source=%s exc=%s",
                    lead.id,
                    idx,
                    key,
                    source,
                    f"{type(exc).__name__}:{exc}",
                )
                continue

        if not photo_predictions:
            raise RuntimeError("no_photo_predictions_generated")

        # Step 3: lead-level aggregate over normalized photo predictions.
        lead_aggregate = aggregate_predictions(photo_predictions)

        # Best-effort persistence for observability and future ML training export.
        # Runtime vs training data are separated in metadata_json by the persistence service.
        try:
            persist_vision_artifacts(
                db,
                tenant_id=tenant_id,
                lead_id=str(lead.id),
                photo_vision_runs=vision_results,
                photo_vision_predictions=[p.model_dump() for p in photo_predictions],
                lead_vision_aggregate=lead_aggregate.model_dump(),
            )
        except Exception:
            # Never break pricing flow on logging/persistence issues.
            logger.exception(
                "VISION_PERSIST_BEST_EFFORT_FAILED lead_id=%s tenant_id=%s",
                lead.id,
                tenant_id,
            )

        # Compatibility bridge: keep existing pricing pipeline input shape.
        image_predictions = [
            _legacy_image_prediction_from_photo_pred(pred) for pred in photo_predictions
        ]

        # TODO: Persist photo_predictions/lead_aggregate once a dedicated storage field/repository is finalized.
        vision_output = {
            "mode": "photo_quality_openai_vision",
            "reason": "paintly_default",
            "image_predictions": image_predictions,
            "photo_predictions": [p.model_dump() for p in photo_predictions],
            "photo_inputs": photo_inputs,
            "file_skip_reasons": list(file_skip_reasons or [])[:25],
            "lead_aggregate": lead_aggregate.model_dump(),
            "needs_review": bool(lead_aggregate.needs_review),
            "review_reasons": list(lead_aggregate.review_reasons),
            "review_decision": {
                "decision": lead_aggregate.decision,
                "reasons": list(lead_aggregate.decision_reasons),
                "warning_reasons": list(lead_aggregate.warning_reasons),
                "confidence": float(lead_aggregate.decision_confidence),
                "quality_metrics": dict(lead_aggregate.quality_metrics),
            },
            "vision_results": vision_results,
        }
    except Exception as e:
        logger.exception(
            "Vision provider integration failed, falling back to legacy predictor lead_id=%s err=%s",
            lead_id,
            e,
        )
        logger.error(
            "VISION_PROVIDER_INTEGRATION_FALLBACK lead_id=%s exception=%s message=%s",
            lead_id,
            type(e).__name__,
            str(e),
        )
        image_predictions = predict_images(image_paths)
        vision_output = {
            "mode": "image_predictions_only",
            "reason": "provider_fallback_to_legacy",
            "image_predictions": image_predictions,
        }

    # Optional validation (only if we ever add surfaces aggregation)
    surfaces = (
        vision_output.get("surfaces") if isinstance(vision_output, dict) else None
    )
    if surfaces == []:
        logger.warning(
            f"Vision output has empty surfaces for lead_id={lead_id}. "
            f"images={len(image_paths)} preds={len(image_predictions)}"
        )

    return vision_output
