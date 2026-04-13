from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.auth.deps import require_user_html
from app.db import get_db
from app.models.calendar_connection import CalendarConnection
from app.models.user import User
from app.verticals.painting.google_calendar_oauth import (
    build_google_auth_url,
    encrypt_token,
    exchange_code_for_tokens,
    token_expiry_from_response,
    validate_oauth_state,
)
from app.verticals.painting.google_calendar_service import (
    create_google_calendar_event_for_tenant,
)

router = APIRouter(
    prefix="/integrations/google-calendar",
    tags=["paintly_integrations"],
    dependencies=[Depends(require_user_html)],
)


@router.get("/connect")
def connect_google_calendar(current_user: User = Depends(require_user_html)):
    tenant_id = str(current_user.tenant_id)
    auth_url = build_google_auth_url(tenant_id)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback")
def google_calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    state_tenant_id = validate_oauth_state(state)
    user_tenant_id = str(current_user.tenant_id)
    if state_tenant_id != user_tenant_id:
        raise HTTPException(status_code=403, detail="OAuth tenant mismatch.")

    token_payload = exchange_code_for_tokens(code)
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="Google OAuth did not return access token.")

    refresh_token = str(token_payload.get("refresh_token") or "").strip()
    expires_at = token_expiry_from_response(token_payload)

    connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == user_tenant_id,
            CalendarConnection.provider == "google",
        )
        .first()
    )
    if not connection:
        connection = CalendarConnection(
            tenant_id=user_tenant_id,
            provider="google",
            calendar_id="primary",
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
            token_expires_at=expires_at,
        )
    else:
        connection.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            connection.refresh_token_encrypted = encrypt_token(refresh_token)
        connection.token_expires_at = expires_at
        if not connection.calendar_id:
            connection.calendar_id = "primary"

    db.add(connection)
    db.commit()

    return RedirectResponse(url="/app/settings?saved=integrations", status_code=303)


@router.get("/test-event")
def google_calendar_test_event(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    if not settings.ENABLE_DEV_ROUTES:
        raise HTTPException(status_code=404, detail="Not found")

    tenant_id = str(current_user.tenant_id)
    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    event_payload = {
        "summary": "Paintly Test Event",
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
    }
    return create_google_calendar_event_for_tenant(
        db=db,
        tenant_id=tenant_id,
        event_payload=event_payload,
        not_connected_status=404,
        not_connected_detail="Google Calendar is not connected.",
    )


@router.delete("/disconnect")
def disconnect_google_calendar(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tenant_id = str(current_user.tenant_id)
    connection = (
        db.query(CalendarConnection)
        .filter(
            CalendarConnection.tenant_id == tenant_id,
            CalendarConnection.provider == "google",
        )
        .first()
    )
    if connection:
        db.delete(connection)
        db.commit()
    return {"ok": True}
