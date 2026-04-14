import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.modules.outreach.models.message_reply import MessageReply
from app.modules.outreach.models.outbound_message import OutboundMessage

logger = logging.getLogger(__name__)

_POSITIVE_REPLY_SUGGESTION = (
    "Thanks for your reply. Happy to hear this is relevant. "
    "Would you be open to a quick call this week to discuss next steps?"
)


class FollowUpService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_reply_suggestions_for_positive_replies(self) -> Dict[str, Any]:
        """
        Generate reply suggestions for all replies classified as "positive".

        Contract notes:
        - Suggestions are regenerated on every run from current DB state.
        - No deduplication is performed in Inversiq for this flow.
        - Openclaw is responsible for idempotency (for example, by `reply_id`).
        """
        positive_replies = (
            self.db.query(MessageReply)
            .filter(MessageReply.classification_label == "positive")
            .all()
        )

        processed = 0
        suggestions: List[Dict[str, str]] = []

        for reply in positive_replies:
            outbound = (
                self.db.query(OutboundMessage)
                .filter(OutboundMessage.id == reply.outbound_message_id)
                .first()
            )
            if not outbound:
                logger.warning(
                    "Positive reply %s references missing outbound_message_id=%s — skipping",
                    reply.id,
                    reply.outbound_message_id,
                )
                continue

            processed += 1
            suggestions.append(
                {
                    "reply_id": reply.id,
                    "classification_label": reply.classification_label or "other",
                    "recipient_email": outbound.recipient_email,
                    "original_subject": outbound.subject,
                    "suggested_reply": _POSITIVE_REPLY_SUGGESTION,
                }
            )

        return {"processed": processed, "suggestions": suggestions}
