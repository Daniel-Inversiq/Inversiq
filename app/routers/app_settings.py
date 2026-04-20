from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/settings/company")
def get_company_settings(user: User = Depends(get_current_user)):
    return {
        "company_name": user.company_name or "",
        "support_email": user.email,
        "logo_url": user.logo_url,
    }
