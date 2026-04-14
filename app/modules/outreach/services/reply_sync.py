import base64
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.outreach.models.outbound_message import OutboundMessage
from app.modules.outreach.repositories.message_reply_repo import MessageReplyRepository
from app.modules.outreach.services.reply_classifier import ReplyClassifier

logger = logging.getLogger(__name__)


def _get_header(headers: list[dict], name: str) -> Optional[str]:
    """Return the first matching header value (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value")
    return None


def _extract_plain_body(payload: dict) -> str:
    """
    Walk a Gmail message payload and return the first plain-text body found.
    Handles both single-part and multipart messages.
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_plain_body(part)
        if result:
            return result

    return ""


def _parse_received_at(internal_date_ms: Optional[str]) -> datetime:
    """Convert Gmail internalDate (epoch milliseconds string) to a UTC datetime."""
    if internal_date_ms:
        try:
            ts = int(internal_date_ms) / 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    return datetime.now(tz=timezone.utc)


class ReplySyncService:
    def __init__(self, db: Session, gmail_service) -> None:
        self.db = db
        self.gmail = gmail_service
        self.reply_repo = MessageReplyRepository(db)
        self.classifier = ReplyClassifier()

    def sync_replies_for_message(self, outbound: OutboundMessage) -> int:
        """
        Fetch the Gmail thread for a single OutboundMessage and store any
        new replies. Returns the number of replies saved.
        """
        thread_id = outbound.gmail_thread_id
        if not thread_id:
            return 0

        try:
            thread = (
                self.gmail.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch Gmail thread %s", thread_id)
            return 0

        messages = thread.get("messages", [])
        saved = 0

        for msg in messages:
            gmail_message_id = msg.get("id")
            if not gmail_message_id:
                continue

            # Skip the original outbound message
            if gmail_message_id == outbound.gmail_message_id:
                continue

            # Skip already-stored replies
            if self.reply_repo.exists_by_gmail_message_id(gmail_message_id):
                continue

            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            from_email = _get_header(headers, "From")
            body = _extract_plain_body(payload)
            received_at = _parse_received_at(msg.get("internalDate"))

            if not body:
                logger.debug("Skipping message %s — no plain text body", gmail_message_id)
                continue

            label = self.classifier.classify(body)

            self.reply_repo.create(
                outbound_message_id=outbound.id,
                gmail_message_id=gmail_message_id,
                gmail_thread_id=thread_id,
                from_email=from_email,
                body=body,
                received_at=received_at,
                classification_label=label,
            )
            saved += 1
            logger.info(
                "Stored reply gmail_message_id=%s thread=%s from=%s label=%s",
                gmail_message_id,
                thread_id,
                from_email,
                label,
            )

        return saved

    def sync_all(self) -> dict:
        """
        Sync replies for all OutboundMessages that have a gmail_thread_id.
        Returns a summary dict.
        """
        outbound_messages = (
            self.db.query(OutboundMessage)
            .filter(OutboundMessage.gmail_thread_id.isnot(None))
            .all()
        )

        total_messages = len(outbound_messages)
        total_replies = 0

        for outbound in outbound_messages:
            total_replies += self.sync_replies_for_message(outbound)

        logger.info(
            "reply_sync_complete threads_checked=%d replies_saved=%d",
            total_messages,
            total_replies,
        )

        return {
            "threads_checked": total_messages,
            "replies_saved": total_replies,
        }
