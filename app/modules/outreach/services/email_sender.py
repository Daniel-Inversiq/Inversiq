from typing import Optional  # noqa: F401 — used in send_and_log signature

from sqlalchemy.orm import Session

from app.modules.outreach.models.outbound_message import OutboundMessage
from app.modules.outreach.repositories.outbound_message_repo import OutboundMessageRepository
from app.modules.outreach.services.gmail_provider import GmailProvider


class EmailSenderService:
    def __init__(self, db: Session, gmail_provider: GmailProvider) -> None:
        self.db = db
        self.gmail = gmail_provider
        self.repo = OutboundMessageRepository(db)

    def send_and_log(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        lead_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        sender_email: Optional[str] = None,
        prompt_version: Optional[str] = None,
        soul_version: Optional[str] = None,
        variant_id: Optional[str] = None,
    ) -> OutboundMessage:
        result = self.gmail.send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
        )

        record = self.repo.create(
            lead_id=lead_id,
            campaign_id=campaign_id,
            sender_email=sender_email,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            gmail_message_id=result["gmail_message_id"],
            gmail_thread_id=result["gmail_thread_id"],
            sent_at=result["sent_at"],
            prompt_version=prompt_version,
            soul_version=soul_version,
            variant_id=variant_id,
        )

        return record

    def create_draft(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        lead_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        sender_email: Optional[str] = None,
        prompt_version: Optional[str] = None,
        soul_version: Optional[str] = None,
        variant_id: Optional[str] = None,
    ) -> dict:
        # Keep parity with send payload; metadata is intentionally not persisted for drafts.
        _ = lead_id, campaign_id, sender_email, prompt_version, soul_version, variant_id
        return self.gmail.create_draft(
            to_email=recipient_email,
            subject=subject,
            body=body,
        )
