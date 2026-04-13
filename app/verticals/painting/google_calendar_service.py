from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.verticals.painting.google_calendar_oauth import (
    create_google_calendar_event,
    decrypt_token,
    encrypt_token,
    list_google_calendar_events,
    refresh_access_token,
    token_expiry_from_response,
)

logger = logging.getLogger(__name__)


def utc_normalize_appointment_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def build_appointment_event_payload(
    *,
    title: str,
    start_utc: datetime,
    end_utc: datetime,
    description: str | None,
    attendee_emails: list[str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": title.strip(),
        "start": {"dateTime": start_utc.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_utc.isoformat(), "timeZone": "UTC"},
    }
    desc = (description or "").strip()
    if desc:
        payload["description"] = desc
    emails: list[str] = []
    if attendee_emails:
        for raw in attendee_emails:
            e = str(raw).strip()
            if e:
                emails.append(e)
    if emails:
        payload["attendees"] = [{"email": e} for e in emails[:10]]
    return payload


def _safe_tz_name(name: str | None) -> str:
    tz = (name or "").strip()
    if not tz:
        return "Europe/Amsterdam"
    try:
        ZoneInfo(tz)
        return tz
    except Exception:
        return "Europe/Amsterdam"


def resolve_google_access_token(db: Session, connection: CalendarConnection) -> str:
    access_token = decrypt_token(connection.access_token_encrypted)
    expires_at = connection.token_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            if not connection.refresh_token_encrypted:
                raise HTTPException(
                    status_code=409,
                    detail="Google token expired. Reconnect integration.",
                )
            refreshed = refresh_access_token(
                decrypt_token(connection.refresh_token_encrypted)
            )
            refreshed_access = str(refreshed.get("access_token") or "").strip()
            if not refreshed_access:
                raise HTTPException(
                    status_code=409,
                    detail="Failed to refresh Google token. Reconnect integration.",
                )
            access_token = refreshed_access
            connection.access_token_encrypted = encrypt_token(refreshed_access)
            connection.token_expires_at = token_expiry_from_response(refreshed)
            db.add(connection)
            db.commit()
    return access_token


def _attendee_emails_from_google_event(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for row in item.get("attendees") or []:
        if not isinstance(row, dict):
            continue
        em = str(row.get("email") or "").strip()
        if em:
            out.append(em)
    return out[:50]


def format_upcoming_google_calendar_events(
    items: list[dict[str, Any]],
    tz_name: str,
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Minimal rows for API + Agenda: title, ISO start, html link, attendee emails."""
    tz = ZoneInfo(_safe_tz_name(tz_name))
    rows: list[dict[str, Any]] = []
    for item in items:
        if (item.get("status") or "").lower() == "cancelled":
            continue
        eid = str(item.get("id") or "").strip()
        title = (item.get("summary") or "").strip() or "(Geen titel)"
        html_raw = item.get("htmlLink")
        html_link = html_raw.strip() if isinstance(html_raw, str) and html_raw.strip() else None
        attendees = _attendee_emails_from_google_event(item)

        start = item.get("start") or {}
        if "date" in start:
            raw_date = str(start["date"] or "").strip()
            if len(raw_date) != 10 or raw_date.count("-") != 2:
                continue
            try:
                day = datetime.fromisoformat(raw_date + "T00:00:00").replace(tzinfo=UTC)
            except Exception:
                continue
            start_iso = day.isoformat()
            parts = raw_date.split("-")
            date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
            start_label = f"Hele dag · {date_str}"
            rows.append(
                {
                    "event_id": eid,
                    "title": title,
                    "start_datetime": start_iso,
                    "html_link": html_link,
                    "attendees": attendees,
                    "start_label": start_label,
                    "quote_id": None,
                }
            )
        else:
            raw_dt = start.get("dateTime")
            if not raw_dt:
                continue
            raw = str(raw_dt)
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            start_iso = dt.astimezone(UTC).isoformat()
            local = dt.astimezone(tz)
            start_label = f"{local.strftime('%d-%m-%Y %H:%M')}"
            rows.append(
                {
                    "event_id": eid,
                    "title": title,
                    "start_datetime": start_iso,
                    "html_link": html_link,
                    "attendees": attendees,
                    "start_label": start_label,
                    "quote_id": None,
                }
            )
        if len(rows) >= limit:
            break
    return rows


def fetch_upcoming_google_calendar_events_for_tenant(
    db: Session,
    tenant_id: str,
    *,
    tz_name: str,
    days_ahead: int = 30,
    max_results: int = 25,
) -> list[dict[str, Any]]:
    connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == tenant_id,
            CalendarConnection.provider == "google",
        )
        .first()
    )
    if not connection:
        return []
    try:
        access_token = resolve_google_access_token(db, connection)
        calendar_id = (connection.calendar_id or "").strip() or "primary"
        time_min = datetime.now(UTC)
        time_max = time_min + timedelta(days=days_ahead)
        body = list_google_calendar_events(
            access_token=access_token,
            calendar_id=calendar_id,
            time_min_utc=time_min,
            time_max_utc=time_max,
            max_results=max_results,
        )
        items = body.get("items") or []
    except HTTPException as exc:
        logger.warning("Google Calendar upcoming events: %s", exc.detail)
        return []
    except Exception as exc:
        logger.warning("Google Calendar upcoming events failed: %s", exc)
        return []
    return format_upcoming_google_calendar_events(items, tz_name, limit=max_results)


def _db_calendar_event_to_row(ce: CalendarEvent, tz_name: str) -> dict[str, Any]:
    tz = ZoneInfo(_safe_tz_name(tz_name))
    start = ce.start_datetime
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    else:
        start = start.astimezone(UTC)
    start_iso = start.isoformat()
    local = start.astimezone(tz)
    start_label = local.strftime("%d-%m-%Y %H:%M")
    return {
        "event_id": ce.google_event_id,
        "title": ce.title,
        "start_datetime": start_iso,
        "html_link": ce.html_link,
        "attendees": [],
        "start_label": start_label,
        "quote_id": ce.quote_id,
    }


def fetch_upcoming_calendar_events_merged(
    db: Session,
    tenant_id: str,
    *,
    tz_name: str,
    days_ahead: int = 30,
    max_results: int = 25,
) -> list[dict[str, Any]]:
    """Google API list enriched with DB `quote_id`, plus DB-only rows if API misses them."""
    google_rows = fetch_upcoming_google_calendar_events_for_tenant(
        db,
        tenant_id,
        tz_name=tz_name,
        days_ahead=days_ahead,
        max_results=max_results,
    )
    now = datetime.now(UTC)
    end = now + timedelta(days=days_ahead)
    db_rows = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.start_datetime >= now,
            CalendarEvent.start_datetime <= end,
        )
        .order_by(CalendarEvent.start_datetime.asc())
        .limit(max_results * 2)
        .all()
    )
    by_google = {ce.google_event_id: ce for ce in db_rows}
    google_ids = {r.get("event_id") for r in google_rows if r.get("event_id")}
    for row in google_rows:
        eid = row.get("event_id")
        if eid and eid in by_google:
            row["quote_id"] = by_google[eid].quote_id
    extra: list[dict[str, Any]] = []
    for ce in db_rows:
        if ce.google_event_id not in google_ids:
            extra.append(_db_calendar_event_to_row(ce, tz_name))
    merged = google_rows + extra
    merged.sort(key=lambda r: (r.get("start_datetime") or ""))
    return merged[:max_results]


def create_google_calendar_event_for_tenant(
    *,
    db: Session,
    tenant_id: str,
    event_payload: dict[str, Any],
    connection: CalendarConnection | None = None,
    not_connected_status: int = 409,
    not_connected_detail: str = "Google Calendar is not connected.",
    send_updates: str | None = None,
) -> dict[str, Any]:
    if connection is not None:
        if str(connection.tenant_id) != str(tenant_id):
            raise HTTPException(status_code=403, detail="Tenant mismatch for calendar connection.")
    else:
        connection = (
            db.query(CalendarConnection)
            .filter(
                CalendarConnection.tenant_id == tenant_id,
                CalendarConnection.provider == "google",
            )
            .first()
        )
        if not connection:
            raise HTTPException(status_code=not_connected_status, detail=not_connected_detail)

    access_token = resolve_google_access_token(db, connection)

    calendar_id = (connection.calendar_id or "").strip() or "primary"
    return create_google_calendar_event(
        access_token=access_token,
        calendar_id=calendar_id,
        event_payload=event_payload,
        send_updates=send_updates,
    )
