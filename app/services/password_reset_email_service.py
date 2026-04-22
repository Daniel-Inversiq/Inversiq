from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.settings import settings
from app.services.email_service import EmailMessage, PostmarkHttpEmailService, PostmarkSendResult

logger = logging.getLogger(__name__)

_SUBJECT = "Wachtwoord opnieuw instellen"
_EMAIL_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_EMAIL_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def build_password_reset_url(*, raw_token: str) -> str:
    base = settings.effective_app_base_url
    return f"{base}/reset-password?token={raw_token}"


def _render_bodies(*, reset_url: str, expiry_minutes: int) -> tuple[str, str]:
    context = {
        "reset_url": reset_url,
        "expiry_minutes": expiry_minutes,
    }
    html_t = _jinja_env.get_template("password_reset_request.html")
    text_t = _jinja_env.get_template("password_reset_request.txt")
    return html_t.render(**context), text_t.render(**context)


async def send_password_reset_email(
    *,
    to_email: str,
    reset_url: str,
    expiry_minutes: int = 60,
    postmark: PostmarkHttpEmailService | None = None,
) -> PostmarkSendResult:
    recipient = (to_email or "").strip()
    if not recipient:
        logger.warning("password reset email skipped: empty recipient")
        return PostmarkSendResult(ok=False, skipped=True, skip_reason="missing_recipient")

    html_body, text_body = _render_bodies(reset_url=reset_url, expiry_minutes=expiry_minutes)
    msg = EmailMessage(
        to=recipient,
        subject=_SUBJECT,
        html_body=html_body,
        text_body=text_body,
        message_stream=settings.POSTMARK_MESSAGE_STREAM,
        tag="password-reset",
        metadata={"email_type": "password_reset"},
    )
    client = postmark or PostmarkHttpEmailService()
    return await client.send(msg)
