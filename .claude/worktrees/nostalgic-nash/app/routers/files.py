# app/routers/files.py
from typing import Dict, Any

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging

from app.core.settings import settings
from app.services.s3 import generate_intake_upload_key, create_presigned_post
from app.services.storage import get_storage, LocalStorage

router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger(__name__)


class PresignUploadResponse(BaseModel):
    url: str
    fields: Dict[str, Any]
    key: str


@router.get("/presign-upload", response_model=PresignUploadResponse)
def presign_upload(
    filename: str = Query(...),
    content_type: str = Query("image/jpeg"),
    size_bytes: int = Query(0),
):
    """
    Legacy endpoint voor de intake upload widget.
    Wordt aangeroepen als:
      GET /files/presign-upload?filename=...&content_type=...&size_bytes=...

    Retourneert een S3 presigned POST:
      { "url": ..., "fields": {...}, "key": ... }
    """

    # 1) Validaties
    allowed_mimes = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
    }
    if content_type not in allowed_mimes:
        raise HTTPException(
            status_code=400,
            detail=f"content_type not allowed: {content_type}",
        )

    max_mb = getattr(settings, "S3_UPLOAD_MAX_MB", 25)
    max_bytes = max_mb * 1024 * 1024
    if size_bytes and size_bytes > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"file too large; max={max_bytes} bytes",
        )

    # 2) S3 key opbouwen (tenant nu gewoon 'default')
    tenant_id = "default"
    key = generate_intake_upload_key(tenant_id, filename)

    # 3) Presigned POST maken via onze centrale S3 helper
    try:
        presigned = create_presigned_post(
            key=key,
            content_type=content_type,
            max_mb=max_mb,
        )
    except RuntimeError as e:
        # komt rechtstreeks uit create_presigned_post (credentials, bucket etc.)
        raise HTTPException(status_code=500, detail=str(e))

    return PresignUploadResponse(
        url=presigned["url"],
        fields=presigned["fields"],
        key=key,
    )


@router.get("/{tenant_id}/{file_path:path}")
def serve_local_file(tenant_id: str, file_path: str):
    """
    Serve files from local storage when STORAGE_BACKEND=local.
    LocalStorage.public_url() generates /files/{tenant_id}/{key}, which is handled here.
    """
    storage = get_storage()

    # Only support LocalStorage here; S3 uses its own public URLs and won't hit this route.
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Local file serving not enabled")

    key = (file_path or "").lstrip("/")

    def _tenant_id_sane(tid: str) -> bool:
        # Keep it conservative to avoid turning path segments into arbitrary paths.
        tid = (tid or "").strip()
        if not tid or len(tid) > 120:
            return False
        # Allowed chars in our system are basically "slug-ish".
        return all(ch.isalnum() or ch in {"_", "-", "."} for ch in tid)

    attempts: list[dict[str, Any]] = []

    def _try_resolve(tid: str, k: str, why: str):
        k2 = (k or "").lstrip("/")
        full_path = storage._full_path(tid, k2)  # type: ignore[attr-defined]
        exists = bool(full_path.exists() and full_path.is_file())
        attempts.append(
            {
                "why": why,
                "tenant_id": tid,
                "key": k2,
                "full_path": str(full_path),
                "exists": exists,
                "size_bytes": int(full_path.stat().st_size) if exists else None,
            }
        )
        return full_path if exists else None

    # 1) direct lookup (expected: key without tenant prefix)
    direct = _try_resolve(tenant_id, key, "direct")

    # 2) normalize double-prefixes inside file_path: e.g. key="acme/acme/uploads/.."
    alt_key = key
    self_prefix = f"{tenant_id}/"
    while alt_key.startswith(self_prefix):
        alt_key = alt_key[len(self_prefix) :].lstrip("/")
    alt1 = None if alt_key == key else _try_resolve(tenant_id, alt_key, "strip_self_prefix_loop")

    # SECURITY: never resolve across tenant boundaries.
    resolved = direct or alt1
    if not resolved:
        logger.info(
            "[SECURITY_FIX] files_route_no_cross_tenant_fallback tenant_id=%r requested_key=%r",
            tenant_id,
            key,
        )
    logger.info(
        "FILES_ROUTE_LOCAL_RESOLVE tenant_id=%r requested_key=%r resolved=%r attempts_count=%s",
        tenant_id,
        key,
        str(resolved) if resolved else None,
        len(attempts),
    )

    if not resolved:
        # Provide the attempted keys/paths for debugging; keep response unchanged.
        logger.warning(
            "FILES_ROUTE_LOCAL_NOT_FOUND tenant_id=%r requested_key=%r attempts=%r",
            tenant_id,
            key,
            attempts,
        )
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(resolved))
