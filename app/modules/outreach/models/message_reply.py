from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MessageReply(Base):
    __tablename__ = "message_replies"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    outbound_message_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("outbound_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    from_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    classification_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<MessageReply id={self.id} "
            f"from={self.from_email!r} "
            f"thread={self.gmail_thread_id!r}>"
        )
