"""add workspace_jobs

Revision ID: 2026_06_25_02
Revises: 2026_06_25_01
Create Date: 2026-06-25 09:30:00.000000

"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "2026_06_25_02"
down_revision = "2026_06_25_01"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    schema = "public" if bind.dialect.name == "postgresql" else None
    return name in inspector.get_table_names(schema=schema)


def upgrade() -> None:
    if not _table_exists("workspace_jobs"):
        op.create_table(
            "workspace_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(100), nullable=False, index=True),
            sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("job_type", sa.String(100), nullable=False, index=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="NEW", index=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    if _table_exists("workspace_jobs"):
        op.drop_table("workspace_jobs")
