from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import LeadTrainingRecord

logger = logging.getLogger(__name__)
_MAX_RAW_RESPONSE_CHARS = 12000


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _truncate_raw_response(raw: Any) -> Any:
    safe = _to_json_safe(raw)
    if isinstance(safe, (dict, list)):
        import json

        s = json.dumps(safe, ensure_ascii=True, separators=(",", ":"))
        if len(s) <= _MAX_RAW_RESPONSE_CHARS:
            return safe
        return {
            "_truncated": True,
            "_max_chars": _MAX_RAW_RESPONSE_CHARS,
            "_preview": s[:_MAX_RAW_RESPONSE_CHARS],
        }
    if isinstance(safe, str) and len(safe) > _MAX_RAW_RESPONSE_CHARS:
        return safe[:_MAX_RAW_RESPONSE_CHARS]
    return safe


def _compact_runtime_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            compact.append({"raw": _to_json_safe(run)})
            continue
        r = dict(run)
        if "raw_response" in r:
            r["raw_response"] = _truncate_raw_response(r.get("raw_response"))
        compact.append(_to_json_safe(r))
    return compact


def persist_vision_artifacts(
    db: Session,
    *,
    tenant_id: str,
    lead_id: str,
    photo_vision_runs: list[dict[str, Any]],
    photo_vision_predictions: list[dict[str, Any]],
    lead_vision_aggregate: dict[str, Any] | None,
) -> LeadTrainingRecord:
    """
    Persist vision artifacts in existing LeadTrainingRecord (no schema migration).

    Separation:
    - metadata_json.vision_runtime: vendor/raw + runtime telemetry
    - metadata_json.vision_training: normalized labels/features for dataset export

    TODO(project wiring):
    - Add dedicated repositories/tables for:
      1) photo_vision_runs
      2) photo_vision_predictions
      3) lead_vision_aggregates
    - Keep this function as backward-compatible mirror sink during migration.
    """
    record = (
        db.query(LeadTrainingRecord)
        .filter(
            LeadTrainingRecord.tenant_id == tenant_id,
            LeadTrainingRecord.lead_id == lead_id,
        )
        .one_or_none()
    )
    if record is None:
        record = LeadTrainingRecord(tenant_id=tenant_id, lead_id=lead_id)
        db.add(record)

    metadata = record.metadata_json if isinstance(record.metadata_json, dict) else {}
    runtime = metadata.get("vision_runtime") if isinstance(metadata.get("vision_runtime"), dict) else {}
    training = metadata.get("vision_training") if isinstance(metadata.get("vision_training"), dict) else {}

    runtime["photo_vision_runs"] = _compact_runtime_runs(photo_vision_runs)
    runtime["lead_vision_aggregate"] = _to_json_safe(lead_vision_aggregate)
    runtime["latest_provider"] = "openai_provider_v1"

    training["photo_vision_predictions"] = _to_json_safe(photo_vision_predictions)
    training["lead_vision_aggregate"] = _to_json_safe(lead_vision_aggregate)
    # TODO: Attach human review labels/feedback once review tooling writes back.
    training.setdefault("human_review_feedback", None)
    # TODO: Add export marker / split assignment for offline training pipelines.
    training.setdefault("export_status", "pending")

    metadata["vision_runtime"] = runtime
    metadata["vision_training"] = training
    record.metadata_json = _to_json_safe(metadata)

    # Keep primary photo_refs useful for downstream dataset queries.
    if not record.photo_refs:
        refs = []
        for run in photo_vision_runs:
            photo_id = run.get("photo_id")
            if photo_id is not None:
                refs.append({"photo_id": str(photo_id)})
        record.photo_refs = refs

    try:
        db.flush()
    except Exception:
        db.rollback()
        logger.exception(
            "VISION_ARTIFACT_PERSIST_FAILED tenant_id=%s lead_id=%s",
            tenant_id,
            lead_id,
        )
        raise

    return record
