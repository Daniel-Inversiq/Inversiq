from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.calendar_connection import CalendarConnection
from app.verticals.paintly.google_calendar_oauth import (
    create_google_calendar_event,
    decrypt_token,
    encrypt_token,
    refresh_access_token,
    token_expiry_from_response,
)


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

    calendar_id = (connection.calendar_id or "").strip() or "primary"
    return create_google_calendar_event(
        access_token=access_token,
        calendar_id=calendar_id,
        event_payload=event_payload,
        send_updates=send_updates,
    )
