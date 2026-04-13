# app/services/photo_quality/inference.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image

from app.services.storage import Storage


@dataclass
class PhotoQualityResult:
    # New AI validation contract
    relevant: bool
    quality_score: float  # 0..1, higher is better
    confidence: float  # 0..1, confidence in this validation decision
    issues: List[str]

    # Backward-compatible helpers for old callers.
    @property
    def quality(self) -> str:
        return "good" if self.quality_score >= 0.6 else "bad"

    @property
    def score_bad(self) -> float:
        return float(max(0.0, min(1.0, 1.0 - self.quality_score)))

    @property
    def reasons(self) -> List[str]:
        return self.issues


def _maybe_strip_tenant(object_key: str, tenant_id: str) -> str:
    """
    Our DB stores object_key as tenant-prefixed:
      "<tenant_id>/uploads/....jpg"

    Storage helpers typically want:
      tenant_id + key_without_tenant

    So: if object_key starts with "<tenant_id>/", strip it.
    """
    if not object_key:
        return object_key
    prefix = f"{tenant_id}/"
    if tenant_id and object_key.startswith(prefix):
        return object_key[len(prefix) :]
    return object_key


def _laplacian_variance(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)

    up = np.roll(g, -1, axis=0)
    down = np.roll(g, 1, axis=0)
    left = np.roll(g, -1, axis=1)
    right = np.roll(g, 1, axis=1)

    lap = (4.0 * g) - up - down - left - right
    return float(lap.var())


def _analyze_image(local_path: str) -> Tuple[float, List[str]]:
    reasons: List[str] = []

    try:
        img = Image.open(local_path).convert("RGB")
    except Exception:
        return 0.0, ["photo_unreadable"]

    w, h = img.size
    if w < 640 or h < 480:
        reasons.append("resolution_too_low")

    # downscale for speed
    img_small = img.copy()
    img_small.thumbnail((1024, 1024))

    arr = np.asarray(img_small, dtype=np.uint8)
    gray = (
        0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    ).astype(np.float32)

    sharp = _laplacian_variance(gray)

    if sharp < 30:
        reasons.append("too_blurry")

    return sharp, reasons


def predict_photo_quality(
    image_refs: List[str],
    storage: Storage,
    tenant_id: str,
) -> PhotoQualityResult:
    """
    image_refs are UploadRecord.object_key values (often tenant-prefixed).
    storage must support download_to_temp_path(tenant_id, key) (your S3Storage/LocalStorage does).
    """
    if not image_refs:
        return PhotoQualityResult(
            relevant=False,
            quality_score=0.0,
            confidence=0.0,
            issues=["no_photos"],
        )

    sharps: List[float] = []
    reasons_all: List[str] = []
    analyzed_count = 0

    for obj in image_refs[:5]:
        key_wo_tenant = _maybe_strip_tenant(obj, tenant_id)
        if not key_wo_tenant:
            reasons_all.append("bad_object_key")
            continue

        try:
            tmp_path = storage.download_to_temp_path(tenant_id, key_wo_tenant)
        except Exception:
            reasons_all.append("download_failed")
            continue

        sharp, rs = _analyze_image(tmp_path)
        sharps.append(sharp)
        analyzed_count += 1
        reasons_all.extend(rs)

        # cleanup (best effort)
        try:
            import os

            os.remove(tmp_path)
        except Exception:
            pass

    if not sharps:
        # nothing analyzable
        issues = list(dict.fromkeys(reasons_all)) or ["no_readable_photos"]
        return PhotoQualityResult(
            relevant=False,
            quality_score=0.0,
            confidence=0.2,
            issues=issues,
        )

    best = max(sharps)

    # Quality mapping:
    # - best <= 20  -> 0.0
    # - best >= 80  -> 1.0
    quality_score = float(np.clip((best - 20.0) / 60.0, 0.0, 1.0))

    issues = list(dict.fromkeys(reasons_all))

    # Confidence increases with analyzable evidence, decreases on noisy signals.
    confidence = 0.55 + 0.35 * min(float(analyzed_count) / 3.0, 1.0)
    if "download_failed" in issues or "photo_unreadable" in issues:
        confidence -= 0.15
    if "resolution_too_low" in issues:
        confidence -= 0.10
    confidence = float(np.clip(confidence, 0.0, 1.0))

    # Relevant as long as we could analyze at least one image.
    relevant = analyzed_count > 0

    return PhotoQualityResult(
        relevant=relevant,
        quality_score=quality_score,
        confidence=confidence,
        issues=issues,
    )
