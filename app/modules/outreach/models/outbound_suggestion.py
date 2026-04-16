from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OutboundSuggestion(Base):
    __tablename__ = "outbound_suggestions"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        default=lambda: uuid4().hex,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    recipient_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    variant_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    email_validation_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_deliverability_risky: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    validation_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
