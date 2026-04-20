from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class ProposedChangeAuditEvent(Base):
    __tablename__ = "proposed_change_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    change_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # created | status_changed | note_updated
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    previous_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
