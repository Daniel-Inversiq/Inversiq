# app/services/email_service.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

import httpx

from app.core.settings import settings

logger = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


class EmailSendError(Exception):
    """Raised by legacy `send_email` when Postmark rejects the message."""

    def __init__(
        self,
        message: str,
        *,
        to: str | None = None,
        subject: str | None = None,
        tag: str | None = None,
        http_status: int | None = None,
        error_code: int | None = None,
        provider_message: str | None = None,
        skip_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.to = to
        self.subject = subject
        self.tag = tag
        self.http_status = http_status
        self.error_code = error_code
        self.provider_message = provider_message
        self.skip_reason = skip_reason


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str
    message_stream: str
    tag: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    reply_to: str | None = None


@dataclass(frozen=True, slots=True)
class PostmarkSendResult:
    ok: bool
    skipped: bool = False
    skip_reason: str | None = None
    http_status: int | None = None
    message_id: str | None = None
    submitted_at: str | None = None
    error_code: int | None = None
    provider_message: str | None = None
    raw: dict[str, Any] | None = None


@runtime_checkable
class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> PostmarkSendResult: ...


def _format_from_header(from_raw: str, display_name: str) -> str:
    """
    Build a Postmark `From` header without double-wrapping.

    - If `from_raw` is already `Display <addr@domain>` or `<addr@domain>`, return it trimmed.
    - If `from_raw` is a bare email, return `display_name <email>`.
    """
    raw = (from_raw or "").strip()
    if not raw:
        return ""

    lt, gt = raw.find("<"), raw.rfind(">")
    if lt != -1 and gt != -1 and lt < gt:
        inner = raw[lt + 1 : gt].strip()
        if "@" in inner:
            return raw

    if "@" in raw and "<" not in raw:
        name = (display_name or "").strip() or "Inversiq"
        return f"{name} <{raw}>"

    return raw


def is_email_enabled() -> bool:
    """Backwards-compatible helper; prefer `settings.EMAIL_ENABLED`."""
    return bool(settings.EMAIL_ENABLED)


class PostmarkHttpEmailService:
    """
    Postmark HTTP API client (not SMTP).
    Does not raise on transport/API errors; inspect `PostmarkSendResult.ok`.
    """

    def __init__(
        self,
        *,
        server_token: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        default_message_stream: str | None = None,
        timeout_seconds: float | None = None,
        email_enabled: bool | None = None,
        default_reply_to: str | None = None,
    ) -> None:
        self._server_token = (server_token or settings.POSTMARK_SERVER_TOKEN or "").strip()
        from_raw = (from_email or settings.emails_from_address).strip()
        display_name = (from_name or settings.POSTMARK_FROM_NAME or "Inversiq").strip()
        self._from_header_value = _format_from_header(from_raw, display_name)
        self._default_stream = (
            default_message_stream or settings.POSTMARK_MESSAGE_STREAM or "outbound"
        ).strip()
        self._timeout = timeout_seconds if timeout_seconds is not None else float(
            settings.POSTMARK_HTTP_TIMEOUT_SECONDS
        )
        self._email_enabled = bool(
            email_enabled if email_enabled is not None else settings.EMAIL_ENABLED
        )
        self._default_reply_to = (default_reply_to or settings.POSTMARK_REPLY_TO or "").strip()

    def _from_header(self) -> str:
        return self._from_header_value

    async def send(self, message: EmailMessage) -> PostmarkSendResult:
        if not self._email_enabled:
            logger.info(
                "email skipped (EMAIL_ENABLED=false) to=%s tag=%s",
                message.to,
                message.tag,
            )
            return PostmarkSendResult(ok=False, skipped=True, skip_reason="EMAIL_ENABLED=false")

        to_addr = (message.to or "").strip()
        if not to_addr:
            logger.warning("Postmark send aborted: empty recipient (to)")
            return PostmarkSendResult(
                ok=False,
                skipped=False,
                skip_reason="invalid_to",
                provider_message="recipient address (to) is empty",
            )

        subject = (message.subject or "").strip()
        if not subject:
            logger.warning("Postmark send aborted: empty subject to=%s", to_addr)
            return PostmarkSendResult(
                ok=False,
                skipped=False,
                skip_reason="invalid_subject",
                provider_message="subject is empty",
            )

        if not self._server_token:
            logger.error("Postmark send aborted: POSTMARK_SERVER_TOKEN is empty")
            return PostmarkSendResult(
                ok=False,
                skipped=True,
                skip_reason="POSTMARK_SERVER_TOKEN_missing",
            )

        if not self._from_header_value:
            logger.error("Postmark send aborted: EMAILS_FROM / POSTMARK_FROM is empty")
            return PostmarkSendResult(
                ok=False,
                skipped=True,
                skip_reason="from_address_missing",
            )

        stream = (message.message_stream or self._default_stream).strip()
        meta: dict[str, str] = {str(k): str(v) for k, v in dict(message.metadata).items()}

        payload: dict[str, Any] = {
            "From": self._from_header(),
            "To": to_addr,
            "Subject": subject,
            "HtmlBody": message.html_body,
            "TextBody": message.text_body,
            "MessageStream": stream,
            "TrackOpens": True,
            "Metadata": meta,
        }
        if message.tag:
            payload["Tag"] = message.tag
        reply = (message.reply_to or self._default_reply_to or "").strip()
        if reply:
            payload["ReplyTo"] = reply

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self._server_token,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(POSTMARK_API_URL, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                logger.exception(
                    "Postmark HTTP error to=%s tag=%s: %s",
                    message.to,
                    message.tag,
                    exc,
                )
                return PostmarkSendResult(
                    ok=False,
                    http_status=None,
                    provider_message=str(exc),
                )

        body_text = response.text
        try:
            data = response.json()
        except ValueError:
            logger.error(
                "Postmark non-JSON response status=%s body=%s",
                response.status_code,
                body_text[:2000],
            )
            return PostmarkSendResult(
                ok=False,
                http_status=response.status_code,
                provider_message="invalid_json_response",
            )

        if response.status_code < 200 or response.status_code >= 300:
            logger.error(
                "Postmark HTTP %s to=%s tag=%s body=%s",
                response.status_code,
                message.to,
                message.tag,
                body_text[:2000],
            )
            return PostmarkSendResult(
                ok=False,
                http_status=response.status_code,
                error_code=data.get("ErrorCode") if isinstance(data, dict) else None,
                provider_message=data.get("Message") if isinstance(data, dict) else body_text[:500],
                raw=data if isinstance(data, dict) else None,
            )

        error_code = data.get("ErrorCode", -1)
        if error_code != 0:
            logger.error(
                "Postmark application error to=%s tag=%s ErrorCode=%s Message=%s",
                message.to,
                message.tag,
                error_code,
                data.get("Message"),
            )
            return PostmarkSendResult(
                ok=False,
                http_status=response.status_code,
                error_code=error_code,
                provider_message=str(data.get("Message")),
                raw=data,
            )

        message_id = data.get("MessageID")
        submitted_at = data.get("SubmittedAt")
        logger.info(
            "Postmark send ok to=%s tag=%s MessageID=%s SubmittedAt=%s",
            message.to,
            message.tag,
            message_id,
            submitted_at,
        )
        return PostmarkSendResult(
            ok=True,
            http_status=response.status_code,
            message_id=str(message_id) if message_id is not None else None,
            submitted_at=str(submitted_at) if submitted_at is not None else None,
            raw=data,
        )


def get_default_postmark_service() -> PostmarkHttpEmailService:
    """Build a client from current settings (no import-time singleton)."""
    return PostmarkHttpEmailService()


async def send_postmark_email(message: EmailMessage) -> PostmarkSendResult:
    """Typed Postmark send; does not raise on failure."""
    return await get_default_postmark_service().send(message)


def _email_send_error_from_result(
    result: PostmarkSendResult,
    *,
    message: str,
    to: str,
    subject: str,
    tag: str | None,
) -> EmailSendError:
    return EmailSendError(
        message,
        to=to,
        subject=subject,
        tag=tag,
        http_status=result.http_status,
        error_code=result.error_code,
        provider_message=result.provider_message,
        skip_reason=result.skip_reason,
    )


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    tag: str | None = None,
    reply_to: str | None = None,
    metadata: dict[str, str] | None = None,
    message_stream: str | None = None,
) -> dict[str, Any]:
    """
    Legacy async helper used by estimate / debug routes.
    Raises EmailSendError when the message could not be delivered.
    """
    to_clean = (to or "").strip()
    subject_clean = (subject or "").strip()
    if not to_clean:
        raise EmailSendError(
            "Cannot send email: recipient address (to) is empty",
            to=to_clean or None,
            subject=subject_clean or None,
            tag=tag,
        )
    if not subject_clean:
        raise EmailSendError(
            "Cannot send email: subject is empty",
            to=to_clean,
            subject=subject_clean or None,
            tag=tag,
        )

    msg = EmailMessage(
        to=to_clean,
        subject=subject_clean,
        html_body=html_body,
        text_body=text_body,
        message_stream=message_stream or settings.POSTMARK_MESSAGE_STREAM,
        tag=tag,
        metadata=metadata or {},
        reply_to=reply_to,
    )
    result = await get_default_postmark_service().send(msg)
    if result.skipped:
        if result.skip_reason == "EMAIL_ENABLED=false":
            return {"ok": False, "skipped": True, "reason": result.skip_reason}
        raise _email_send_error_from_result(
            result,
            message=(
                f"{result.skip_reason or 'email_send_skipped'} "
                f"(to={to_clean!r}, subject={subject_clean!r}, tag={tag!r})"
            ),
            to=to_clean,
            subject=subject_clean,
            tag=tag,
        )
    if not result.ok:
        core = result.provider_message or "Postmark send failed"
        detail = (
            f"{core} "
            f"(to={to_clean!r}, subject={subject_clean!r}, tag={tag!r}, "
            f"http_status={result.http_status}, error_code={result.error_code}, "
            f"skip_reason={result.skip_reason!r})"
        )
        raise _email_send_error_from_result(
            result,
            message=detail,
            to=to_clean,
            subject=subject_clean,
            tag=tag,
        )
    return {
        "ok": True,
        "provider": "postmark",
        "response": result.raw or {},
        "message_id": result.message_id,
    }
