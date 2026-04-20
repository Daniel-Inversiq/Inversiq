from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeExecutionAttempt(Base):
    __tablename__ = "proposed_change_execution_attempts"
    __table_args__ = (
        UniqueConstraint(
            "execution_request_id", "attempt_number",
            name="uq_pcea_request_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Soft reference — no FK enforced
    execution_request_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # queued | running | succeeded | failed | rolled_back | cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, server_default="queued"
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    preflight_result_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_result_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
