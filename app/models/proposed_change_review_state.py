from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeReviewState(Base):
    __tablename__ = "proposed_change_review_states"
    __table_args__ = (
        UniqueConstraint("tenant_id", "change_id", name="uq_pcrs_tenant_change"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Stable deterministic change identifier — format: scope_type:scope_id:category:parameter
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # pending | approved | rejected | archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Snapshot of the proposed change object at persist time (JSON stored as text)
    proposal_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
