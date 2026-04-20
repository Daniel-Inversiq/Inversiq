from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeApplyIntent(Base):
    __tablename__ = "proposed_change_apply_intents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "change_id", name="uq_pcai_tenant_change"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # ready_for_apply | cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, server_default="ready_for_apply"
    )
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Snapshot of the proposal_payload at intent creation time (JSON as text)
    proposal_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Compact governance attestation snapshot at intent creation time (JSON as text)
    governance_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Apply plan, preflight, rollback snapshots — reserved for future enrichment
    apply_plan_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preflight_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
