"""add proposed_change_execution_attempts table

Revision ID: 2026_04_18_04
Revises: 2026_04_18_03
Create Date: 2026-04-18 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_04_18_04"
down_revision = "2026_04_18_03"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "proposed_change_execution_attempts"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("execution_request_id", sa.Integer(), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("preflight_result_snapshot", sa.Text(), nullable=True),
        sa.Column("execution_result_snapshot", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("rollback_snapshot", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_request_id", "attempt_number", name="uq_pcea_request_attempt"
        ),
    )
    op.create_index(
        "ix_pcea_tenant_id",
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_execution_request_id",
        table_name,
        ["execution_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_change_id",
        table_name,
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_status",
        table_name,
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_created_at",
        table_name,
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "proposed_change_execution_attempts"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_pcea_created_at", table_name=table_name)
    op.drop_index("ix_pcea_status", table_name=table_name)
    op.drop_index("ix_pcea_change_id", table_name=table_name)
    op.drop_index(
        "ix_pcea_execution_request_id",
        table_name=table_name,
    )
    op.drop_index("ix_pcea_tenant_id", table_name=table_name)
    op.drop_table(table_name)
