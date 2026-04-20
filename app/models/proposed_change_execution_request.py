from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeExecutionRequest(Base):
    __tablename__ = "proposed_change_execution_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "change_id", name="uq_pcer_tenant_change"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # Soft reference to the apply intent that backs this request (no FK)
    apply_intent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # requested | validated | blocked | cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, server_default="requested"
    )
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Execution-facing snapshots — JSON stored as text
    proposal_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    governance_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apply_intent_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_plan_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preflight_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monitoring_plan_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Populated when transitioning to blocked
    blocking_reasons_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
