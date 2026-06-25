"""add workspaces, workspace_documents, workspace_flags

Revision ID: 2026_06_25_01
Revises: 2026_04_28_01
Create Date: 2026-06-25 09:00:00.000000

"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "2026_06_25_01"
down_revision = "2026_04_28_01"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    schema = "public" if bind.dialect.name == "postgresql" else None
    return name in inspector.get_table_names(schema=schema)


def upgrade() -> None:
    if not _table_exists("workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(100), primary_key=True),
            sa.Column("tenant_id", sa.String(100), nullable=False, index=True),
            sa.Column("name", sa.String(500), nullable=False),
            sa.Column("vertical_id", sa.String(100), nullable=False, index=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("extracted_summary", sa.JSON(), nullable=True),
            sa.Column("overall_confidence", sa.String(10), nullable=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _table_exists("workspace_documents"):
        op.create_table(
            "workspace_documents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("upload_record_id", sa.Integer(), sa.ForeignKey("upload_records.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("filename", sa.String(1024), nullable=False),
            sa.Column("doc_type", sa.String(100), nullable=True, index=True),
            sa.Column("classification_confidence", sa.String(10), nullable=True),
            sa.Column("extracted_data", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="uploaded"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists("workspace_flags"):
        op.create_table(
            "workspace_flags",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("flag_type", sa.String(100), nullable=False, index=True),
            sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("source_document_ids", sa.JSON(), nullable=True),
            sa.Column("conflict_data", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="open"),
            sa.Column("resolved_by", sa.String(200), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("resolution_value", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    for table in ("workspace_flags", "workspace_documents", "workspaces"):
        if _table_exists(table):
            op.drop_table(table)
