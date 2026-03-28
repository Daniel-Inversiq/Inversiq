from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.models.user import User


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    # Defensive explicit checks for founder-only routes.
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )

    return current_user
