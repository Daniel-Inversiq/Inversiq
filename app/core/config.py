# app/core/config.py
"""
Central configuration entry point.

Environment-backed fields live on `app.core.settings.Settings` (loaded from `.env`).
Import `settings` from here or from `app.core.settings` interchangeably.

Email / welcome flow (see `app.services.email_service`):
  POSTMARK_SERVER_TOKEN, POSTMARK_MESSAGE_STREAM, EMAILS_FROM (or POSTMARK_FROM / POSTMARK_FROM_EMAIL),
  POSTMARK_FROM_NAME, APP_BASE_URL (or APP_PUBLIC_BASE_URL), SUPPORT_EMAIL, SUPPORT_WHATSAPP,
  EMAIL_ENABLED, POSTMARK_HTTP_TIMEOUT_SECONDS
"""

from app.core.settings import Settings, settings

__all__ = ["Settings", "settings"]
