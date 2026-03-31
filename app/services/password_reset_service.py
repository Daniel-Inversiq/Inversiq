from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

RESET_TOKEN_TTL = timedelta(hours=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_reset_token(raw_token: str) -> str:
    # Include an app secret as a server-side pepper to reduce offline usefulness if DB-only leaks.
    payload = f"{settings.SECRET_KEY}:{raw_token}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_password_reset_token(
    db: Session,
    *,
    user: User,
    ttl: timedelta = RESET_TOKEN_TTL,
) -> tuple[str, PasswordResetToken]:
    """
    Create a new one-time reset token for a user.
    Returns (raw_token, persisted_row). Raw token is shown once to caller (for email).
    """
    now = _utc_now()

    # Invalidate any previous active reset tokens for this user.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).update({"used_at": now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=now + ttl,
    )
    db.add(token_row)
    db.flush()
    return raw_token, token_row


def validate_password_reset_token(
    db: Session,
    *,
    raw_token: str,
) -> PasswordResetToken | None:
    """
    Return a valid, unused, non-expired token row or None.
    """
    token_hash = _hash_reset_token(raw_token)
    now = _utc_now()
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )


def mark_password_reset_token_used(
    db: Session,
    *,
    token_row: PasswordResetToken,
) -> None:
    if token_row.used_at is None:
        token_row.used_at = _utc_now()
        db.add(token_row)


def consume_password_reset_token_atomic(
    db: Session,
    *,
    raw_token: str,
) -> str | None:
    """
    Atomically consume a reset token (single-use).

    Returns user_id when a token was consumed, otherwise None.
    A token is consumable only when hash matches, used_at is NULL, and not expired.
    """
    token_hash = _hash_reset_token(raw_token)
    now = _utc_now()
    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
    )
    row = db.execute(stmt).first()
    if not row:
        return None
    return str(row[0])


def cleanup_expired_password_reset_tokens(db: Session) -> int:
    """
    Delete expired reset tokens. Returns number of deleted rows.
    """
    stmt = delete(PasswordResetToken).where(PasswordResetToken.expires_at <= _utc_now())
    result = db.execute(stmt)
    return int(result.rowcount or 0)
