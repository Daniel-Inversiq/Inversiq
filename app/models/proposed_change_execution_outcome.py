from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeExecutionOutcome(Base):
    __tablename__ = "proposed_change_execution_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "execution_request_id", name="uq_pceo_tenant_exec_request"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Soft reference — no FK enforced, consistent with project pattern
    execution_request_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # success | partial | failed  — caller-supplied: did the execution succeed?
    outcome_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # improved | neutral | degraded | unstable  — server-computed from metric evaluation
    evaluation_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # JSON: {metric: {value, baseline, direction, delta_pct, verdict}} or raw scalars
    observed_metrics_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: optional caller override of what was expected
    expected_metrics_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: server-computed per-metric deviation analysis
    deviation_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    rollback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
