from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.jwt import decode_token
from app.core.settings import settings
from app.models.user import User

security = HTTPBearer(auto_error=False)  # <- belangrijk: niet auto-error


def _dev_fallback_user(db: Session) -> User | None:
    env = (getattr(settings, "APP_ENV", "") or getattr(settings, "ENV", "") or "").lower()
    is_dev = env in {"dev", "development", "local"} or bool(getattr(settings, "DEBUG", False))
    if not is_dev:
        return None
    # Prefer a platform admin so unauthenticated local browsing (dev fallback) can reach /founder/*.
    return (
        db.query(User)
        .filter(User.is_active.is_(True))
        .order_by(desc(User.is_platform_admin), User.id.asc())
        .first()
    )


def _extract_token(
    request: Request, creds: HTTPAuthorizationCredentials | None
) -> str | None:
    # 1) cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    # 2) Authorization header
    if creds and creds.credentials:
        return creds.credentials

    return None


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request, creds)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_user_html(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request, creds)
    if not token:
        fallback_user = _dev_fallback_user(db)
        if fallback_user:
            return fallback_user
        path = request.url.path
        qs = request.url.query
        next_url = path + (("?" + qs) if qs else "")
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": f"/auth/login?next={next_url}"},
        )

    try:
        payload = decode_token(token)
    except Exception:
        fallback_user = _dev_fallback_user(db)
        if fallback_user:
            return fallback_user
        path = request.url.path
        qs = request.url.query
        next_url = path + (("?" + qs) if qs else "")
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Invalid token",
            headers={"Location": f"/auth/login?next={next_url}"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        fallback_user = _dev_fallback_user(db)
        if fallback_user:
            return fallback_user
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user
