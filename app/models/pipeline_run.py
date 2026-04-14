from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base


class PipelineRun(Base):
    """
    One execution of the engine pipeline for a single lead.
    Deliberately does NOT replace Job — Job tracks scheduling and
    the service-layer lifecycle; PipelineRun tracks the engine's
    internal execution trace.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Tenant / lead identity (denormalised — no FK to leads to keep engine generic)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    vertical_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Correlation
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pipeline_name: Mapped[str] = mapped_column(String(200), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Outcome
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="RUNNING", index=True
    )
    failure_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    steps: Mapped[list["PipelineStepRun"]] = relationship(
        "PipelineStepRun",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
        order_by="PipelineStepRun.step_order",
    )


class PipelineStepRun(Base):
    """
    One step execution within a PipelineRun.
    Stores input/output snapshots as JSON for post-mortem debugging.
    """

    __tablename__ = "pipeline_step_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Execution snapshots (nullable — may be omitted for large/sensitive payloads)
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Error detail
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Perf
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    pipeline_run: Mapped["PipelineRun"] = relationship(
        "PipelineRun", back_populates="steps"
    )
