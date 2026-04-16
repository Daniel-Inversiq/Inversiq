from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class EngineEvent(Base):
    """
    Persistent log of discrete engine execution events.

    Designed as an append-only audit / analytics table — rows are never
    updated after insert.  All correlation fields are denormalised (no FK
    constraints) so that events survive deletion of their originating
    PipelineRun / PipelineStepRun.

    event_type naming convention: "<subject>.<verb>"
      e.g.  pipeline.started  pipeline.completed  pipeline.failed
            step.started      step.completed      step.failed  step.skipped

    Fields:
      occurred_at          — when the event happened (semantic time, set by caller)
      created_at           — DB insert time (server clock)

    payload                — event-specific structured data (inputs, outputs, etc.)
    meta                   — cross-cutting context (engine_version, env, config_hash, …)
    """

    __tablename__ = "engine_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Event identity ──────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ── Tenant / lead identity (denormalised, no FK) ─────────────────────────
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    vertical_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Pipeline correlation (soft references — no FK constraint) ────────────
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    pipeline_step_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # ── Step context ─────────────────────────────────────────────────────────
    step_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    step_use: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # ── Outcome ──────────────────────────────────────────────────────────────
    # status: RUNNING | COMPLETED | FAILED | SKIPPED
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Taxonomy: transient | permanent | validation | external_dependency
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Event body ───────────────────────────────────────────────────────────
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # ── DB audit ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
