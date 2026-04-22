from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.deps import get_current_user
from app.models.user import User
from app.models.lead import Lead

router = APIRouter(prefix="/app", tags=["app"])
DATE_FILTER_PRESETS = {
    "all",
    "today",
    "last_7_days",
    "last_30_days",
    "this_month",
    "previous_month",
    "custom",
}
DEFAULT_DATE_PRESET = "last_7_days"


def _parse_iso_date(raw_value: str | None):
    if not raw_value:
        return None
    value = str(raw_value).strip()[:10]
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_date_range(
    *,
    date: str | None,
    start: str | None,
    end: str | None,
    tz_name: str,
):
    preset = (date or DEFAULT_DATE_PRESET).strip().lower()
    if preset not in DATE_FILTER_PRESETS:
        preset = DEFAULT_DATE_PRESET

    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    if preset == "all":
        return None, None
    if preset == "today":
        start_date = today
        end_date = today
    elif preset == "last_30_days":
        start_date = today - timedelta(days=29)
        end_date = today
    elif preset == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif preset == "previous_month":
        this_month_start = today.replace(day=1)
        previous_month_end = this_month_start - timedelta(days=1)
        start_date = previous_month_end.replace(day=1)
        end_date = previous_month_end
    elif preset == "custom":
        parsed_start = _parse_iso_date(start)
        parsed_end = _parse_iso_date(end)
        if not parsed_start or not parsed_end or parsed_start > parsed_end:
            start_date = today - timedelta(days=6)
            end_date = today
        else:
            start_date = parsed_start
            end_date = parsed_end
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    start_utc = datetime.combine(start_date, datetime.min.time(), tzinfo=tz).astimezone(
        timezone.utc
    )
    end_utc = datetime.combine(
        end_date + timedelta(days=1), datetime.min.time(), tzinfo=tz
    ).astimezone(timezone.utc)
    return start_utc, end_utc

@router.get("/leads")
def list_leads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    date: str | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    start_utc, end_utc = _resolve_date_range(
        date=date,
        start=start,
        end=end,
        tz_name=getattr(user, "timezone", None) or "Europe/Amsterdam",
    )
    query = db.query(Lead).filter(Lead.tenant_id == user.tenant_id)
    if start_utc is not None and end_utc is not None:
        query = query.filter(
            or_(
                and_(
                    Lead.updated_at.isnot(None),
                    Lead.updated_at >= start_utc,
                    Lead.updated_at < end_utc,
                ),
                and_(
                    Lead.updated_at.is_(None),
                    Lead.created_at >= start_utc,
                    Lead.created_at < end_utc,
                ),
            )
        )
    leads = query.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(200).all()
    return [
        {
            "id": l.id,
            "status": l.status,
            "email": l.email,
            "name": l.name,
            "created_at": l.created_at,
            "updated_at": l.updated_at,
            # Keep keys stable for frontend fallbacks used by review queue mapping.
            "submitted_at": None,
            "review_created_at": None,
            "review_updated_at": None,
            "next_action_at": None,
        }
        for l in leads
    ]
