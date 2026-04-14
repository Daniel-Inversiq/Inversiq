from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db import get_db
from app.dependencies.gmail import get_gmail_service
from app.modules.outreach.models.outbound_suggestion import OutboundSuggestion
from app.modules.outreach.services.email_sender import EmailSenderService
from app.modules.outreach.services.followup_service import FollowUpService
from app.modules.outreach.services.gmail_provider import GmailProvider
from app.modules.outreach.services.metrics_service import OutreachMetricsService
from app.modules.outreach.services.used_domains_service import UsedDomainsService

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


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


def _extract_domain(email: str) -> str:
    parts = email.strip().lower().split("@")
    if len(parts) != 2 or not parts[1] or "." not in parts[1]:
        raise HTTPException(status_code=422, detail=f"Invalid recipient_email: {email}")
    return parts[1]


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
    provider = GmailProvider(service=gmail_service)
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
    provider = GmailProvider(service=gmail_service)
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
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    now = datetime.utcnow()
    records: list[OutboundSuggestion] = []
    for item in payload.items:
        records.append(
            OutboundSuggestion(
                company_name=item.company_name,
                recipient_email=item.recipient_email,
                recipient_domain=_extract_domain(item.recipient_email),
                subject=item.subject,
                body=item.body,
                campaign_id=item.campaign_id,
                variant_id=item.variant_id,
                status=SuggestionStatus.pending.value,
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(records)
    db.commit()
    for record in records:
        db.refresh(record)

    return {"items": [_serialize_suggestion(record) for record in records]}


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
    suggestion = db.query(OutboundSuggestion).filter(OutboundSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status == SuggestionStatus.sent.value:
        raise HTTPException(status_code=409, detail="Suggestion already sent")
    if suggestion.status == SuggestionStatus.skipped.value:
        raise HTTPException(status_code=409, detail="Suggestion was skipped")

    provider = GmailProvider(service=gmail_service)
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
        raise HTTPException(status_code=502, detail=f"Gmail send failed: {exc}") from exc

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
    suggestion = db.query(OutboundSuggestion).filter(OutboundSuggestion.id == suggestion_id).first()
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
