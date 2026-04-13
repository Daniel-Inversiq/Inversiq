from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    lead_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    sender_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    gmail_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    gmail_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    prompt_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    soul_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variant_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<OutboundMessage id={self.id} to={self.recipient_email!r} sent_at={self.sent_at}>"
