from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LeadFeedback(Base):
    __tablename__ = "lead_feedback"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        default=lambda: uuid4().hex,
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # "won" or "lost"
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)

    actual_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<LeadFeedback id={self.id} lead={self.lead_id} outcome={self.outcome!r}>"
