from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
    # 12-char SHA-256 prefix over ordered (step_id, step_use) pairs.
    # Identical hash ⟺ identical pipeline structure (step IDs + registry keys).
    config_hash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)

    # Outcome
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="RUNNING", index=True
    )
    failure_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Top-level error category, denormalised from the failing step for easy querying.
    # Taxonomy: transient | permanent | validation | external_dependency | None
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Overall confidence — weakest-link min() of all step scores that provided one.
    # Null when no step in the run reported a confidence score.
    overall_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_confidence_label: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

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
    # Registry key used to execute this step (e.g. "roofing.estimate.v1").
    # step_name is the pipeline step ID; step_use is the exact function version.
    step_use: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Execution snapshots (nullable — may be omitted for large/sensitive payloads)
    # none_as_null=True: Python None persists as SQL NULL so IS NULL queries work correctly.
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)

    # Step contract metadata (from fn.__step_contract__, if declared)
    # Semantic version of the step implementation at time of run.
    step_contract_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Error detail
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Taxonomy category: transient | permanent | validation | external_dependency
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Per-step confidence — populated when the step returns a ConfidenceResult.
    # Null columns mean "this step did not report confidence" (not "zero confidence").
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_label: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    confidence_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
