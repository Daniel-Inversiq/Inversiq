from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.job import Job
from app.models.lead import Lead
from app.models.user import User

router = APIRouter(prefix="/app", tags=["app"])
DATE_FILTER_PRESETS = {
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


@router.get("/jobs")
def list_jobs(
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
    jobs_in_range_filter = or_(
        and_(Job.scheduled_at.isnot(None), Job.scheduled_at >= start_utc, Job.scheduled_at < end_utc),
        and_(Job.scheduled_at.is_(None), Job.created_at >= start_utc, Job.created_at < end_utc),
    )
    rows = (
        db.query(Job, Lead)
        .outerjoin(Lead, Lead.id == Job.lead_id)
        .filter(Job.tenant_id == str(user.tenant_id))
        .filter(jobs_in_range_filter)
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(200)
        .all()
    )

    return [
        {
            "id": job.id,
            "tenant_id": job.tenant_id,
            "lead_id": str(job.lead_id),
            "lead_name": lead.name if lead else None,
            "status": job.status,
            "scheduled_at": job.scheduled_at,
            "scheduled_tz": job.scheduled_tz,
            "started_at": job.started_at,
            "done_at": job.done_at,
            "notes": job.notes,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        for job, lead in rows
    ]
