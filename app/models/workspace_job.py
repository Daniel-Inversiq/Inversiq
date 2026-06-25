from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WorkspaceJob(Base):
    """
    Background job record for workspace pipeline steps.

    job_type:
      "process_document"   — classify + extract one WorkspaceDocument
      "cross_check"        — run cross-document validation for a Workspace

    payload: {"workspace_doc_id": int} or {"workspace_id": str}
    """

    __tablename__ = "workspace_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)

    # NEW → IN_PROGRESS → DONE | FAILED
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="NEW", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
