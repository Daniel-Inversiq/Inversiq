from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.lead import Lead
from app.models.upload_record import UploadRecord
from app.models.user import User

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/uploads")
def list_uploads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(UploadRecord, Lead)
        .outerjoin(Lead, Lead.id == UploadRecord.lead_id)
        .filter(UploadRecord.tenant_id == str(user.tenant_id))
        .order_by(UploadRecord.created_at.desc(), UploadRecord.id.desc())
        .limit(200)
        .all()
    )

    result = []
    for upload, lead in rows:
        filename = upload.object_key.split("/")[-1] if upload.object_key else ""
        result.append(
            {
                "id": upload.id,
                "tenant_id": upload.tenant_id,
                "lead_id": upload.lead_id,
                "lead_name": lead.name if lead else None,
                "object_key": upload.object_key,
                "filename": filename or upload.object_key,
                "status": upload.status.value if hasattr(upload.status, "value") else str(upload.status),
                "mime": upload.mime,
                "size": upload.size,
                "created_at": upload.created_at,
                "updated_at": upload.updated_at,
            }
        )

    return result
