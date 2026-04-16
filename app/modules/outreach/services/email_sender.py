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
        prepared_body = self._prepare_outreach_body(body)
        result = self.gmail.send_email(
            to_email=recipient_email,
            subject=subject,
            body=prepared_body,
        )

        record = self.repo.create(
            lead_id=lead_id,
            campaign_id=campaign_id,
            sender_email=sender_email,
            recipient_email=recipient_email,
            subject=subject,
            body=prepared_body,
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
        prepared_body = self._prepare_outreach_body(body)
        return self.gmail.create_draft(
            to_email=recipient_email,
            subject=subject,
            body=prepared_body,
        )

    @staticmethod
    def _prepare_outreach_body(body: str) -> str:
        """
        Keep outreach copy short and structured without rewriting personalization text.
        Target shape:
        1) short opening
        2) one pain point
        3) one value proposition
        4) one CTA
        """
        normalized = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return ""

        paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
        if not paragraphs:
            return ""

        # Remove repeated paragraphs while preserving order.
        unique_paragraphs: list[str] = []
        seen: set[str] = set()
        for p in paragraphs:
            key = " ".join(p.lower().split())
            if key in seen:
                continue
            seen.add(key)
            unique_paragraphs.append(p)

        if len(unique_paragraphs) <= 4:
            return "\n\n".join(unique_paragraphs)

        def pick_idx(candidates: list[str], used: set[int]) -> int | None:
            for i, p in enumerate(unique_paragraphs):
                if i in used:
                    continue
                lower = p.lower()
                if any(token in lower for token in candidates):
                    return i
            return None

        used_idx: set[int] = set()
        ordered: list[str] = []

        # Short opening: first paragraph, trimmed if very long.
        opening = unique_paragraphs[0]
        if len(opening) > 280:
            opening = opening[:277].rstrip() + "..."
        ordered.append(opening)
        used_idx.add(0)

        pain_idx = pick_idx(
            ["pain", "problem", "issue", "friction", "struggle", "missing", "slow", "manual"],
            used_idx,
        )
        if pain_idx is None:
            pain_idx = next((i for i in range(len(unique_paragraphs)) if i not in used_idx), None)
        if pain_idx is not None:
            ordered.append(unique_paragraphs[pain_idx])
            used_idx.add(pain_idx)

        value_idx = pick_idx(
            ["result", "outcome", "value", "improve", "faster", "save", "growth", "increase"],
            used_idx,
        )
        if value_idx is None:
            value_idx = next((i for i in range(len(unique_paragraphs)) if i not in used_idx), None)
        if value_idx is not None:
            ordered.append(unique_paragraphs[value_idx])
            used_idx.add(value_idx)

        cta_idx = pick_idx(
            ["?", "open to", "would you", "quick call", "chat", "meeting", "next week"],
            used_idx,
        )
        if cta_idx is None:
            cta_idx = next((i for i in range(len(unique_paragraphs)) if i not in used_idx), None)
        if cta_idx is not None:
            ordered.append(unique_paragraphs[cta_idx])

        return "\n\n".join(ordered[:4])
