from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.job import Job
from app.models.lead import Lead
from app.models.user import User

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/jobs")
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Job, Lead)
        .outerjoin(Lead, Lead.id == Job.lead_id)
        .filter(Job.tenant_id == str(user.tenant_id))
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
