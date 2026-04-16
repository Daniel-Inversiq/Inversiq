from datetime import datetime
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db import get_db
from app.dependencies.gmail import get_gmail_service
from app.modules.outreach.email_validation import (
    PUBLIC_MAILBOX_DOMAINS,
    validate_recipient_for_outreach,
)
from app.modules.outreach.models.outbound_suggestion import OutboundSuggestion
from app.modules.outreach.services.email_sender import EmailSenderService
from app.modules.outreach.services.followup_service import FollowUpService
from app.modules.outreach.services.gmail_provider import GmailProvider
from app.modules.outreach.services.metrics_service import OutreachMetricsService
from app.modules.outreach.services.suggestion_queue_actions import (
    bulk_send_suggestions,
    bulk_skip_suggestions,
    normalize_suggestion_ids,
)
from app.modules.outreach.services.used_domains_service import UsedDomainsService
from app.modules.outreach.models.outbound_message import OutboundMessage

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


def _build_gmail_provider(gmail_service) -> GmailProvider:
    return GmailProvider(
        service=gmail_service,
        signature_enabled=settings.OUTREACH_SIGNATURE_ENABLED,
        signature_signoff=settings.OUTREACH_SIGNATURE_SIGNOFF,
        signature_name=settings.OUTREACH_SIGNATURE_NAME,
        signature_company=settings.OUTREACH_SIGNATURE_COMPANY,
        signature_website=settings.OUTREACH_SIGNATURE_WEBSITE,
        signature_phone=settings.OUTREACH_SIGNATURE_PHONE,
    )


class SendEmailRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str
    lead_id: Optional[str] = None
    campaign_id: Optional[str] = None
    sender_email: Optional[str] = None
    prompt_version: Optional[str] = None
    soul_version: Optional[str] = None
    variant_id: Optional[str] = None


class SuggestionStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    skipped = "skipped"


class SuggestionCreateItem(BaseModel):
    company_name: str
    recipient_email: EmailStr
    subject: str
    body: str
    campaign_id: Optional[str] = None
    variant_id: Optional[str] = None


class BulkSuggestionsRequest(BaseModel):
    items: list[SuggestionCreateItem] = Field(default_factory=list)


class BulkSuggestionIdsRequest(BaseModel):
    suggestion_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


def _is_public_mailbox_domain(domain: str) -> bool:
    return domain.lower() in PUBLIC_MAILBOX_DOMAINS


def _normalize_domain(value: str | None) -> str | None:
    if not value:
        return None

    candidate = value.strip().lower()
    if not candidate:
        return None

    if "@" in candidate:
        parts = candidate.split("@")
        if len(parts) != 2:
            return None
        _, candidate = parts

    candidate = candidate.strip().strip(".")
    if candidate.startswith("www."):
        candidate = candidate[4:]

    if not candidate or "." not in candidate:
        return None
    return candidate


def _serialize_suggestion(record: OutboundSuggestion) -> dict:
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


@router.post("/send")
def send_outreach_email(
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    gmail_service=Depends(get_gmail_service),
):
    """
    Send an outreach email via Gmail and log it to the database.
    Called by Openclaw — protected by BasicAuth on the /api prefix.
    """
    provider = _build_gmail_provider(gmail_service)
    sender = EmailSenderService(db=db, gmail_provider=provider)

    try:
        record = sender.send_and_log(
            recipient_email=payload.recipient_email,
            subject=payload.subject,
            body=payload.body,
            lead_id=payload.lead_id,
            campaign_id=payload.campaign_id,
            sender_email=payload.sender_email or settings.GMAIL_SENDER_EMAIL,
            prompt_version=payload.prompt_version,
            soul_version=payload.soul_version,
            variant_id=payload.variant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Gmail send failed: {exc}"
        ) from exc

    return {
        "id": record.id,
        "gmail_message_id": record.gmail_message_id,
        "gmail_thread_id": record.gmail_thread_id,
        "sent_at": record.sent_at,
    }


@router.post("/draft")
def create_outreach_email_draft(
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    gmail_service=Depends(get_gmail_service),
):
    """
    Create an outreach email draft via Gmail without sending it.
    Called by Openclaw — protected by BasicAuth on the /api prefix.
    """
    provider = _build_gmail_provider(gmail_service)
    sender = EmailSenderService(db=db, gmail_provider=provider)

    try:
        draft = sender.create_draft(
            recipient_email=payload.recipient_email,
            subject=payload.subject,
            body=payload.body,
            lead_id=payload.lead_id,
            campaign_id=payload.campaign_id,
            sender_email=payload.sender_email or settings.GMAIL_SENDER_EMAIL,
            prompt_version=payload.prompt_version,
            soul_version=payload.soul_version,
            variant_id=payload.variant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Gmail draft creation failed: {exc}"
        ) from exc

    return {
        "draft_id": draft["gmail_draft_id"],
        "gmail_message_id": draft.get("gmail_message_id"),
        "gmail_thread_id": draft.get("gmail_thread_id"),
        "created_at": draft["created_at"],
    }


@router.post("/suggestions/bulk")
def create_outbound_suggestions_bulk(
    payload: BulkSuggestionsRequest,
    db: Session = Depends(get_db),
):
    """
    Store outbound suggestions as pending approval queue items.
    Called by Openclaw — protected by BasicAuth on the /api prefix.

    Pre-ingest deduplication (pending or sent only; skipped does not block):
    - Business domains: one active suggestion per recipient_domain.
    - Public mailbox domains (gmail.com, icloud.com, outlook.com, hotmail.com, live.com):
      one active suggestion per full recipient_email (same domain is not a duplicate).
    - In-batch: same rules applied in request order.

    Recipient validation (syntax + DNS MX / A / AAAA via email-validator):
    - Clearly invalid addresses (syntax, non-existent domain, no mail path) are rejected.
    - Consumer domains and A/AAAA-only fallbacks may still be inserted but flagged as risky.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    active_statuses = (SuggestionStatus.pending.value, SuggestionStatus.sent.value)

    used_business_domains = {
        (row[0] or "").strip().lower()
        for row in db.query(OutboundSuggestion.recipient_domain)
        .filter(OutboundSuggestion.status.in_(active_statuses))
        .filter(~func.lower(OutboundSuggestion.recipient_domain).in_(PUBLIC_MAILBOX_DOMAINS))
        .distinct()
        .all()
        if row[0]
    }
    used_public_emails = {
        row[0].strip().lower()
        for row in db.query(OutboundSuggestion.recipient_email)
        .filter(OutboundSuggestion.status.in_(active_statuses))
        .filter(func.lower(OutboundSuggestion.recipient_domain).in_(PUBLIC_MAILBOX_DOMAINS))
        .distinct()
        .all()
    }

    batch_business_domains: set[str] = set()
    batch_public_emails: set[str] = set()

    now = datetime.utcnow()
    records: list[OutboundSuggestion] = []
    skipped: list[dict[str, Any]] = []
    skipped_validation: list[dict[str, Any]] = []

    for item in payload.items:
        ov = validate_recipient_for_outreach(
            str(item.recipient_email),
            dns_timeout_seconds=settings.OUTREACH_EMAIL_DNS_TIMEOUT_SECONDS,
        )
        if not ov.should_insert:
            skipped_validation.append(
                {
                    "recipient_email": ov.normalized_email,
                    "company_name": item.company_name,
                    "email_validation_result": ov.result,
                    "validation_reason": ov.validation_reason,
                    "is_deliverability_risky": ov.is_deliverability_risky,
                }
            )
            continue

        recipient_email = ov.normalized_email
        domain = ov.normalized_domain

        if _is_public_mailbox_domain(domain):
            if recipient_email in used_public_emails or recipient_email in batch_public_emails:
                skipped.append(
                    {
                        "recipient_email": recipient_email,
                        "company_name": item.company_name,
                        "reason": (
                            "duplicate_public_mailbox_email_existing"
                            if recipient_email in used_public_emails
                            else "duplicate_public_mailbox_email_batch"
                        ),
                    }
                )
                continue
            batch_public_emails.add(recipient_email)
        else:
            if domain in used_business_domains or domain in batch_business_domains:
                skipped.append(
                    {
                        "recipient_email": recipient_email,
                        "company_name": item.company_name,
                        "reason": (
                            "duplicate_business_domain_existing"
                            if domain in used_business_domains
                            else "duplicate_business_domain_batch"
                        ),
                    }
                )
                continue
            batch_business_domains.add(domain)

        records.append(
            OutboundSuggestion(
                company_name=item.company_name,
                recipient_email=recipient_email,
                recipient_domain=domain,
                subject=item.subject,
                body=item.body,
                campaign_id=item.campaign_id,
                variant_id=item.variant_id,
                status=SuggestionStatus.pending.value,
                email_validation_result=ov.result,
                is_deliverability_risky=ov.is_deliverability_risky,
                validation_reason=ov.validation_reason,
                created_at=now,
                updated_at=now,
            )
        )

    if records:
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)

    return {
        "items": [_serialize_suggestion(record) for record in records],
        "skipped_duplicates": skipped,
        "skipped_validation": skipped_validation,
    }


@router.get("/suggestions")
def list_outbound_suggestions(
    status: SuggestionStatus = Query(default=SuggestionStatus.pending),
    db: Session = Depends(get_db),
):
    """
    List outbound suggestions by status.
    Protected by BasicAuth on the /api prefix.
    """
    rows = (
        db.query(OutboundSuggestion)
        .filter(OutboundSuggestion.status == status.value)
        .order_by(OutboundSuggestion.created_at.asc())
        .all()
    )
    return {"items": [_serialize_suggestion(row) for row in rows]}


@router.post("/suggestions/bulk-send")
def bulk_send_outbound_suggestions(
    payload: BulkSuggestionIdsRequest,
    db: Session = Depends(get_db),
    gmail_service=Depends(get_gmail_service),
):
    """
    Send many pending suggestions via Gmail (same rules as single send per id).
    Protected by BasicAuth on the /api prefix.
    """
    ids = normalize_suggestion_ids(payload.suggestion_ids)
    if not ids:
        raise HTTPException(status_code=400, detail="suggestion_ids must not be empty")
    return bulk_send_suggestions(db, gmail_service, ids)


@router.post("/suggestions/bulk-skip")
def bulk_skip_outbound_suggestions(
    payload: BulkSuggestionIdsRequest,
    db: Session = Depends(get_db),
):
    """
    Mark many pending suggestions as skipped (idempotent for already-skipped).
    Protected by BasicAuth on the /api prefix.
    """
    ids = normalize_suggestion_ids(payload.suggestion_ids)
    if not ids:
        raise HTTPException(status_code=400, detail="suggestion_ids must not be empty")
    return bulk_skip_suggestions(db, ids)


@router.post("/suggestions/{suggestion_id}/send")
def send_outbound_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    gmail_service=Depends(get_gmail_service),
):
    """
    Send one approved suggestion and mark it as sent.
    Protected by BasicAuth on the /api prefix.
    """
    suggestion = (
        db.query(OutboundSuggestion)
        .filter(OutboundSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status == SuggestionStatus.sent.value:
        raise HTTPException(status_code=409, detail="Suggestion already sent")
    if suggestion.status == SuggestionStatus.skipped.value:
        raise HTTPException(status_code=409, detail="Suggestion was skipped")

    provider = _build_gmail_provider(gmail_service)
    sender = EmailSenderService(db=db, gmail_provider=provider)
    try:
        record = sender.send_and_log(
            recipient_email=suggestion.recipient_email,
            subject=suggestion.subject,
            body=suggestion.body,
            campaign_id=suggestion.campaign_id,
            sender_email=settings.GMAIL_SENDER_EMAIL,
            variant_id=suggestion.variant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Gmail send failed: {exc}"
        ) from exc

    suggestion.status = SuggestionStatus.sent.value
    db.commit()
    db.refresh(suggestion)

    return {
        "suggestion": _serialize_suggestion(suggestion),
        "outbound_message": {
            "id": record.id,
            "gmail_message_id": record.gmail_message_id,
            "gmail_thread_id": record.gmail_thread_id,
            "sent_at": record.sent_at,
        },
    }


@router.post("/suggestions/{suggestion_id}/skip")
def skip_outbound_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
):
    """
    Mark one suggestion as skipped.
    Protected by BasicAuth on the /api prefix.
    """
    suggestion = (
        db.query(OutboundSuggestion)
        .filter(OutboundSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status == SuggestionStatus.sent.value:
        raise HTTPException(status_code=409, detail="Suggestion already sent")
    if suggestion.status == SuggestionStatus.skipped.value:
        return {"suggestion": _serialize_suggestion(suggestion)}

    suggestion.status = SuggestionStatus.skipped.value
    db.commit()
    db.refresh(suggestion)
    return {"suggestion": _serialize_suggestion(suggestion)}


@router.get("/metrics")
def get_outreach_metrics(db: Session = Depends(get_db)):
    """
    Return global outreach effectiveness metrics.
    Protected by BasicAuth on the /api prefix.
    """
    return OutreachMetricsService(db).get_metrics()


@router.get("/metrics/by-campaign")
def get_outreach_metrics_by_campaign(db: Session = Depends(get_db)):
    """
    Return outreach metrics grouped by (campaign_id, variant_id).
    Protected by BasicAuth on the /api prefix.
    """
    return OutreachMetricsService(db).get_campaign_variant_metrics()


@router.get("/used-domains")
def get_used_domains(db: Session = Depends(get_db)):
    """
    Return unique recipient domains contacted via outreach outbound emails.
    Protected by BasicAuth on the /api prefix.
    """
    return UsedDomainsService(db).get_used_domains()


@router.get("/excluded-domains")
def get_excluded_domains(db: Session = Depends(get_db)):
    """
    Return unique normalized outreach domains to exclude from future prospecting.
    Protected by BasicAuth on the /api prefix.
    """
    suggestion_rows = db.query(OutboundSuggestion.recipient_domain).all()
    message_rows = db.query(OutboundMessage.recipient_email).all()

    domains = {
        domain
        for (raw_value,) in (list(suggestion_rows) + list(message_rows))
        for domain in [_normalize_domain(raw_value)]
        if domain
    }
    return {"domains": sorted(domains)}


@router.post("/followups/run")
def run_followups(
    db: Session = Depends(get_db),
):
    """
    Generate follow-up reply suggestions for positive replies.
    Protected by BasicAuth on the /api prefix.

    Contract notes:
    - Suggestions are regenerated on every run.
    - Inversiq performs no deduplication in this endpoint.
    - Openclaw must enforce idempotency when acting on suggestions, using `reply_id`.
    """
    return FollowUpService(db=db).generate_reply_suggestions_for_positive_replies()
