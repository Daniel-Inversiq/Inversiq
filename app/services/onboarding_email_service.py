# app/services/onboarding_email_service.py
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.tenant import Tenant
from app.models.user import User
from app.services.email_service import (
    EmailMessage,
    PostmarkSendResult,
    PostmarkHttpEmailService,
)

logger = logging.getLogger(__name__)

_SUBJECT = "Welkom bij Inversiq – jouw intake link staat klaar"
_TRIAL_DAYS = 14

# TODO: Under concurrent requests or retries, two workers could both pass
# welcome_email_sent_at IS NULL and send duplicate mail before either commits.
# Consider: DB-level unique partial index, SELECT … FOR UPDATE, or transactional outbox.

_EMAIL_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_EMAIL_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _support_whatsapp_url(raw: str) -> str:
    digits = re.sub(r"\D+", "", raw or "")
    if not digits:
        return ""
    return f"https://wa.me/{digits}"


def _greeting_first_name(_owner: User, _tenant: Tenant) -> str:
    # TODO: return owner.first_name when your User model stores it. Leave empty to avoid
    # guessing from email local parts (admin@, info@, sales@, etc.).
    return ""


def _build_context(*, owner: User, tenant: Tenant) -> dict[str, object]:
    base = settings.effective_app_base_url
    slug = (tenant.slug or "").strip()
    intake_url = f"{base}/intake/{slug}"

    company_name = (tenant.company_name or tenant.name or "").strip()
    support_email = (settings.SUPPORT_EMAIL or "").strip()
    support_whatsapp = (settings.SUPPORT_WHATSAPP or "").strip()

    return {
        "recipient_email": owner.email,
        "first_name": _greeting_first_name(owner, tenant),
        "company_name": company_name,
        "tenant_slug": slug,
        "intake_url": intake_url,
        "support_email": support_email,
        "support_whatsapp": support_whatsapp,
        "support_whatsapp_url": _support_whatsapp_url(support_whatsapp),
        "trial_days": _TRIAL_DAYS,
    }


def _render_bodies(context: dict[str, object]) -> tuple[str, str]:
    html_t = _jinja_env.get_template("welcome_paintly.html")
    text_t = _jinja_env.get_template("welcome_paintly.txt")
    return html_t.render(**context), text_t.render(**context)


async def send_welcome_email(
    *,
    tenant: Tenant,
    owner: User,
    postmark: PostmarkHttpEmailService | None = None,
) -> PostmarkSendResult:
    """
    Render and send the Paintly welcome mail to the tenant owner.
    Does not persist `welcome_email_sent_at`; the caller commits that after a successful send.
    """
    tenant_id = tenant.id
    tenant_slug = (tenant.slug or "").strip()

    if tenant.welcome_email_sent_at is not None:
        logger.warning(
            "welcome email skipped: already sent tenant_id=%s tenant_slug=%s at=%s",
            tenant_id,
            tenant_slug or "—",
            tenant.welcome_email_sent_at,
        )
        return PostmarkSendResult(ok=False, skipped=True, skip_reason="already_sent")

    if not tenant_slug:
        logger.warning(
            "welcome email skipped: missing tenant slug tenant_id=%s user_id=%s",
            tenant_id,
            owner.id,
        )
        return PostmarkSendResult(ok=False, skipped=True, skip_reason="missing_tenant_slug")

    recipient = (owner.email or "").strip()
    if not recipient:
        logger.warning(
            "welcome email skipped: missing owner email tenant_id=%s tenant_slug=%s user_id=%s",
            tenant_id,
            tenant_slug,
            owner.id,
        )
        return PostmarkSendResult(ok=False, skipped=True, skip_reason="missing_owner_email")

    ctx = _build_context(owner=owner, tenant=tenant)
    html_body, text_body = _render_bodies(ctx)

    client = postmark or PostmarkHttpEmailService()
    metadata = {
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant_slug,
        "user_id": str(owner.id),
        "email_type": "welcome",
    }
    msg = EmailMessage(
        to=recipient,
        subject=_SUBJECT,
        html_body=html_body,
        text_body=text_body,
        message_stream=settings.POSTMARK_MESSAGE_STREAM,
        tag="welcome-email",
        metadata=metadata,
    )
    result = await client.send(msg)

    if result.skipped:
        logger.warning(
            "welcome email provider skipped tenant_id=%s tenant_slug=%s user_id=%s recipient=%s reason=%s",
            tenant_id,
            tenant_slug,
            owner.id,
            recipient,
            result.skip_reason,
        )
        return result

    if not result.ok:
        logger.warning(
            "welcome email send failed tenant_id=%s tenant_slug=%s user_id=%s recipient=%s "
            "http_status=%s error_code=%s detail=%s",
            tenant_id,
            tenant_slug,
            owner.id,
            recipient,
            result.http_status,
            result.error_code,
            result.provider_message,
        )
        return result

    logger.info(
        "welcome email sent tenant_id=%s tenant_slug=%s user_id=%s recipient=%s message_id=%s",
        tenant_id,
        tenant_slug,
        owner.id,
        recipient,
        result.message_id,
    )
    return result


async def send_welcome_email_task(tenant_id: str, owner_user_id: str) -> None:
    """
    FastAPI `BackgroundTasks` entrypoint: isolated DB session, never raises to the client.
    """
    from app.db import SessionLocal

    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        owner = db.query(User).filter(User.id == owner_user_id).first()
        if not tenant or not owner:
            logger.warning(
                "welcome email task: missing tenant or user tenant_id=%s user_id=%s",
                tenant_id,
                owner_user_id,
            )
            return

        if tenant.welcome_email_sent_at is not None:
            logger.warning(
                "welcome email task skipped: already sent tenant_id=%s tenant_slug=%s at=%s",
                tenant.id,
                (tenant.slug or "").strip() or "—",
                tenant.welcome_email_sent_at,
            )
            return

        result = await send_welcome_email(tenant=tenant, owner=owner)

        if result.skipped or not result.ok:
            return

        tenant.welcome_email_sent_at = datetime.now(timezone.utc)
        db.add(tenant)
        db.commit()
        logger.info(
            "welcome email persisted tenant_id=%s tenant_slug=%s user_id=%s recipient=%s message_id=%s",
            tenant.id,
            (tenant.slug or "").strip(),
            owner.id,
            (owner.email or "").strip(),
            result.message_id,
        )
    except Exception:
        logger.exception(
            "welcome email task failed tenant_id=%s user_id=%s",
            tenant_id,
            owner_user_id,
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("rollback after welcome email failure")
    finally:
        db.close()
