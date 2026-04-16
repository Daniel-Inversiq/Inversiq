from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent


def log_activity_event(
    db: Session,
    *,
    tenant_id: str,
    event_type: str,
    title: str,
    link_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        tenant_id=str(tenant_id),
        event_type=event_type,
        title=title,
        link_url=link_url,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    db.add(event)
    return event


def get_latest_activity_events(
    db: Session,
    *,
    tenant_id: str,
    limit: int = 5,
) -> list[ActivityEvent]:
    safe_limit = max(1, min(int(limit), 20))
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.tenant_id == str(tenant_id))
        .order_by(ActivityEvent.created_at.desc())
        .limit(safe_limit)
        .all()
    )


def to_iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
