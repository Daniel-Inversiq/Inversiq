from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.outreach.models.message_reply import MessageReply
from app.modules.outreach.models.outbound_message import OutboundMessage


class OutreachMetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_metrics(self) -> dict:
        sent_count: int = (
            self.db.query(func.count(OutboundMessage.id)).scalar() or 0
        )

        reply_count: int = (
            self.db.query(func.count(func.distinct(MessageReply.outbound_message_id)))
            .scalar() or 0
        )

        positive_reply_count: int = (
            self.db.query(func.count(func.distinct(MessageReply.outbound_message_id)))
            .filter(MessageReply.classification_label == "positive")
            .scalar() or 0
        )

        reply_rate = reply_count / sent_count if sent_count else 0.0
        positive_reply_rate = positive_reply_count / sent_count if sent_count else 0.0

        return {
            "sent_count": sent_count,
            "reply_count": reply_count,
            "positive_reply_count": positive_reply_count,
            "reply_rate": round(reply_rate, 4),
            "positive_reply_rate": round(positive_reply_rate, 4),
        }

    def get_campaign_variant_metrics(self) -> list[dict]:
        # Query 1: sent_count per (campaign_id, variant_id)
        sent_rows = (
            self.db.query(
                OutboundMessage.campaign_id,
                OutboundMessage.variant_id,
                func.count(OutboundMessage.id).label("sent_count"),
            )
            .group_by(OutboundMessage.campaign_id, OutboundMessage.variant_id)
            .all()
        )

        # Query 2: reply_count per group — distinct outbound messages with any reply
        reply_rows = (
            self.db.query(
                OutboundMessage.campaign_id,
                OutboundMessage.variant_id,
                func.count(func.distinct(MessageReply.outbound_message_id)).label("reply_count"),
            )
            .join(MessageReply, MessageReply.outbound_message_id == OutboundMessage.id)
            .group_by(OutboundMessage.campaign_id, OutboundMessage.variant_id)
            .all()
        )

        # Query 3: positive_reply_count per group — distinct outbound messages with a positive reply
        positive_rows = (
            self.db.query(
                OutboundMessage.campaign_id,
                OutboundMessage.variant_id,
                func.count(func.distinct(MessageReply.outbound_message_id)).label("positive_reply_count"),
            )
            .join(MessageReply, MessageReply.outbound_message_id == OutboundMessage.id)
            .filter(MessageReply.classification_label == "positive")
            .group_by(OutboundMessage.campaign_id, OutboundMessage.variant_id)
            .all()
        )

        # Index reply/positive counts by group key for O(1) lookup
        reply_index = {(r.campaign_id, r.variant_id): r.reply_count for r in reply_rows}
        positive_index = {(r.campaign_id, r.variant_id): r.positive_reply_count for r in positive_rows}

        results = []
        for row in sent_rows:
            key = (row.campaign_id, row.variant_id)
            sent = row.sent_count
            replied = reply_index.get(key, 0)
            positive = positive_index.get(key, 0)

            results.append({
                "campaign_id": row.campaign_id,
                "variant_id": row.variant_id,
                "sent_count": sent,
                "reply_count": replied,
                "positive_reply_count": positive,
                "reply_rate": round(replied / sent, 4) if sent else 0.0,
                "positive_reply_rate": round(positive / sent, 4) if sent else 0.0,
            })

        return results
