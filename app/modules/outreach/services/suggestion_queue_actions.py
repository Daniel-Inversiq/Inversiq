"""Bulk send/skip for outbound suggestions (shared by API and founder UI)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.modules.outreach.models.outbound_suggestion import OutboundSuggestion
from app.modules.outreach.services.email_sender import EmailSenderService
from app.modules.outreach.services.gmail_provider import GmailProvider

MAX_BULK_SUGGESTIONS = 100

_PENDING = "pending"
_SENT = "sent"
_SKIPPED = "skipped"


def _email_sender(db: Session, gmail_service) -> EmailSenderService:
    provider = GmailProvider(
        service=gmail_service,
        signature_enabled=settings.OUTREACH_SIGNATURE_ENABLED,
        signature_signoff=settings.OUTREACH_SIGNATURE_SIGNOFF,
        signature_name=settings.OUTREACH_SIGNATURE_NAME,
        signature_company=settings.OUTREACH_SIGNATURE_COMPANY,
        signature_website=settings.OUTREACH_SIGNATURE_WEBSITE,
        signature_phone=settings.OUTREACH_SIGNATURE_PHONE,
    )
    return EmailSenderService(db=db, gmail_provider=provider)


def normalize_suggestion_ids(raw: list[str]) -> list[str]:
    """Deduplicate while preserving order; cap list length."""
    out: list[str] = []
    seen: set[str] = set()
    for s in raw:
        sid = (s or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
        if len(out) >= MAX_BULK_SUGGESTIONS:
            break
    return out


def _serialize_suggestion(record: OutboundSuggestion) -> dict[str, Any]:
    return {
        "id": record.id,
        "company_name": record.company_name,
        "recipient_email": record.recipient_email,
        "recipient_domain": record.recipient_domain,
        "subject": record.subject,
        "body": record.body,
        "campaign_id": record.campaign_id,
        "variant_id": record.variant_id,
        "status": record.status,
        "email_validation_result": record.email_validation_result,
        "is_deliverability_risky": record.is_deliverability_risky,
        "validation_reason": record.validation_reason,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def send_suggestion_by_id(
    db: Session,
    gmail_service,
    suggestion_id: str,
    *,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """
    Send one pending suggestion via Gmail.

    Loads the row from the database and, unless `subject`/`body` overrides are passed,
    refreshes from the DB so the latest saved edits are used.

    When both `subject` and `body` are provided (e.g. founder row "Send" with form fields),
    they are persisted to the row before sending so unsaved textarea edits are not lost.
    """
    sid = (suggestion_id or "").strip()
    if not sid:
        return {"suggestion_id": "", "ok": False, "error": "empty_id"}

    suggestion = (
        db.query(OutboundSuggestion).filter(OutboundSuggestion.id == sid).first()
    )
    if not suggestion:
        return {"suggestion_id": sid, "ok": False, "error": "not_found"}

    if subject is not None or body is not None:
        if subject is None or body is None:
            return {
                "suggestion_id": sid,
                "ok": False,
                "error": "incomplete_content: pass both subject and body or neither",
            }
        next_subject = subject.strip()
        next_body = body.strip()
        if not next_subject or not next_body:
            return {"suggestion_id": sid, "ok": False, "error": "empty_fields"}
        if suggestion.status != _PENDING:
            if suggestion.status == _SENT:
                return {"suggestion_id": sid, "ok": False, "error": "already_sent"}
            if suggestion.status == _SKIPPED:
                return {"suggestion_id": sid, "ok": False, "error": "was_skipped"}
            return {
                "suggestion_id": sid,
                "ok": False,
                "error": f"invalid_status:{suggestion.status}",
            }
        suggestion.subject = next_subject
        suggestion.body = next_body
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    else:
        db.refresh(suggestion)

    if suggestion.status == _SENT:
        return {"suggestion_id": sid, "ok": False, "error": "already_sent"}
    if suggestion.status == _SKIPPED:
        return {"suggestion_id": sid, "ok": False, "error": "was_skipped"}
    if suggestion.status != _PENDING:
        return {
            "suggestion_id": sid,
            "ok": False,
            "error": f"invalid_status:{suggestion.status}",
        }

    sender = _email_sender(db, gmail_service)
    try:
        record = sender.send_and_log(
            recipient_email=suggestion.recipient_email,
            subject=suggestion.subject,
            body=suggestion.body,
            campaign_id=suggestion.campaign_id,
            sender_email=settings.GMAIL_SENDER_EMAIL,
            variant_id=suggestion.variant_id,
            prepare_body=False,
        )
        suggestion.status = _SENT
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    except Exception as exc:
        return {"suggestion_id": sid, "ok": False, "error": str(exc)}

    return {
        "suggestion_id": sid,
        "ok": True,
        "suggestion": _serialize_suggestion(suggestion),
        "outbound_message": {
            "id": record.id,
            "gmail_message_id": record.gmail_message_id,
            "gmail_thread_id": record.gmail_thread_id,
            "sent_at": record.sent_at,
        },
    }


def bulk_send_suggestions(
    db: Session,
    gmail_service,
    suggestion_ids: list[str],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for sid in suggestion_ids:
        results.append(send_suggestion_by_id(db, gmail_service, sid))
    return {"results": results}


def bulk_skip_suggestions(db: Session, suggestion_ids: list[str]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for sid in suggestion_ids:
        suggestion = (
            db.query(OutboundSuggestion).filter(OutboundSuggestion.id == sid).first()
        )
        if not suggestion:
            results.append({"suggestion_id": sid, "ok": False, "error": "not_found"})
            continue
        if suggestion.status == _SENT:
            results.append({"suggestion_id": sid, "ok": False, "error": "already_sent"})
            continue
        if suggestion.status == _SKIPPED:
            results.append(
                {
                    "suggestion_id": sid,
                    "ok": True,
                    "suggestion": _serialize_suggestion(suggestion),
                    "note": "already_skipped",
                }
            )
            continue
        if suggestion.status != _PENDING:
            results.append(
                {
                    "suggestion_id": sid,
                    "ok": False,
                    "error": f"invalid_status:{suggestion.status}",
                }
            )
            continue

        suggestion.status = _SKIPPED
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
        results.append(
            {
                "suggestion_id": sid,
                "ok": True,
                "suggestion": _serialize_suggestion(suggestion),
            }
        )

    return {"results": results}
