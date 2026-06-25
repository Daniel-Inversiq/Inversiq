from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base


class Workspace(Base):
    """
    A named container for a set of documents being analyzed together.

    Generic across verticals: CRE due diligence, insurance claims,
    construction bids, logistics assessments — all map to a Workspace.
    The vertical_id drives which pipeline steps and extraction schemas apply.
    """

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    vertical_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Processing lifecycle:
    # pending → processing → needs_review → ready | failed
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending", index=True
    )

    # Aggregated extraction output across all documents.
    # Populated after cross-document validation completes.
    extracted_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    # Overall confidence across all document extractions (0.0–1.0).
    overall_confidence: Mapped[Optional[float]] = mapped_column(
        String(10), nullable=True
    )

    # FK to the cross-document PipelineRun (nullable until processing starts).
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    documents: Mapped[list["WorkspaceDocument"]] = relationship(
        "WorkspaceDocument",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="WorkspaceDocument.created_at",
    )
    flags: Mapped[list["WorkspaceFlag"]] = relationship(
        "WorkspaceFlag",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="WorkspaceFlag.severity",
    )


class WorkspaceDocument(Base):
    """
    One document attached to a Workspace.

    Wraps an UploadRecord with workspace-specific state:
    the classified document type, extraction output, and the
    PipelineRun that processed this specific file.
    """

    __tablename__ = "workspace_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The underlying file. Nullable FK — UploadRecord may not yet exist at
    # the moment the row is created (client declares intent first).
    upload_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("upload_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Original filename as uploaded — kept here so it's accessible without
    # joining through upload_records every time.
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Document type taxonomy, populated by the classifier step.
    # Values are vertical-specific; the extraction step keys off this.
    # Examples: information_memorandum, rent_roll, tdd_report, valuation,
    #           lease_agreement, loan_termsheet, financial_statements, epc
    doc_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(
        String(10), nullable=True
    )

    # Structured extraction output for this document.
    extracted_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    # Per-document processing status:
    # uploaded → classifying → extracting → validated | failed
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="uploaded", index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FK to the PipelineRun that processed this document.
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="documents")


class WorkspaceFlag(Base):
    """
    An issue surfaced during document processing or cross-document validation.

    Generic: the flag_type is a string taxonomy value, severity is high/medium/low,
    source_docs is a list of document IDs involved.

    The resolution flow is: open → resolved | escalated.
    """

    __tablename__ = "workspace_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Taxonomy value — drives UI icon and filtering.
    # Examples: erv_deviation, capex_undisclosed, lease_date_invalid,
    #           missing_document, extraction_low_confidence, data_conflict
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # high | medium | low
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")

    # Human-readable title and detail — generated by the reasoning engine.
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    # IDs of WorkspaceDocument rows that contributed to this flag.
    source_document_ids: Mapped[list[int] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    # Extracted field values that caused the flag (for display in the review panel).
    # Shape: {"field": "erv_psm", "sources": [{"doc": "RentRoll", "value": 85}, ...]}
    conflict_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    # Resolution state: open → resolved | escalated
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="open", index=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="flags")
