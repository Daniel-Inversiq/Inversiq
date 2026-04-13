from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.gmail import get_gmail_service
from app.modules.outreach.services.email_sender import EmailSenderService
from app.modules.outreach.services.gmail_provider import GmailProvider

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
            sender_email=payload.sender_email,
            prompt_version=payload.prompt_version,
            soul_version=payload.soul_version,
            variant_id=payload.variant_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail send failed: {exc}") from exc

    return {
        "id": record.id,
        "gmail_message_id": record.gmail_message_id,
        "gmail_thread_id": record.gmail_thread_id,
        "sent_at": record.sent_at,
    }
