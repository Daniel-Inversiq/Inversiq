# app/routers/app_me.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary
from app.services.activity_service import get_latest_activity_events, to_iso_utc

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email, "tenant_id": user.tenant_id}


@router.get("/api/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_dashboard_summary(db=db, tenant_id=str(user.tenant_id))


@router.get("/api/dashboard/activity")
def dashboard_activity(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    events = get_latest_activity_events(db, tenant_id=str(user.tenant_id), limit=5)
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "title": event.title,
                "link_url": event.link_url,
                "created_at": to_iso_utc(event.created_at),
            }
            for event in events
        ]
    }
