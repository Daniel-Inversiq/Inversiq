from __future__ import annotations

import hashlib
import json
from typing import Any

from app.billing.features import plan_supports_feature

_PLAN_NORMALIZATION_MAP = {
    "starter_99": "core",
    "starter": "core",
    "pro_199": "growth",
    "business_399": "pro",
    "business": "pro",
    "core": "core",
    "growth": "growth",
    "pro": "pro",
    "scale": "scale",
}


def normalize_plan(plan: str | None) -> str:
    raw = (plan or "").strip().lower()
    if not raw:
        return "unknown"
    return _PLAN_NORMALIZATION_MAP.get(raw, raw)


def is_custom_branding_allowed(plan: str | None) -> bool:
    # Branding is no longer plan-gated.
    return True


def log_branding_state(logger: Any, stage: str, data: dict[str, Any]) -> None:
    try:
        payload = json.dumps(data, ensure_ascii=True, sort_keys=True, default=str)
    except Exception:
        payload = str(data)
    logger.info("[BRANDING_DEBUG] %s %s", stage, payload)


def branding_html_debug_summary(
    html: str,
    *,
    branding_name: str | None = None,
    snippet_chars: int = 280,
) -> dict[str, Any]:
    text = html or ""
    lower = text.lower()
    name = (branding_name or "").strip()
    contains_branding_name = bool(name and name.lower() in lower)
    summary = {
        "contains_construction": "construction" in lower,
        "contains_img_tag": "<img" in lower,
        "contains_branding_name": contains_branding_name,
        "html_length": len(text),
        "html_sha1": hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest(),
    }
    if text:
        summary["branding_snippet"] = text[:snippet_chars].replace("\n", " ").strip()
    else:
        summary["branding_snippet"] = ""
    return summary

