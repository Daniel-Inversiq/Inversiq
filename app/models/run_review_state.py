from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class RunReviewState(Base):
    __tablename__ = "run_review_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # One row per pipeline_run_id — unique constraint enforces the upsert invariant.
    pipeline_run_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # pending | acknowledged | resolved | ignored
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
