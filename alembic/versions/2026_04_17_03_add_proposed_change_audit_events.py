"""add proposed_change_audit_events table

Revision ID: 2026_04_17_03
Revises: 2026_04_17_02
Create Date: 2026-04-17 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_04_17_03"
down_revision = "2026_04_17_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "proposed_change_audit_events"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=True),
        sa.Column("previous_note", sa.Text(), nullable=True),
        sa.Column("new_note", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pcae_tenant_id",
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcae_change_id",
        table_name,
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcae_created_at",
        table_name,
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "proposed_change_audit_events"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_pcae_created_at", table_name=table_name)
    op.drop_index("ix_pcae_change_id", table_name=table_name)
    op.drop_index("ix_pcae_tenant_id", table_name=table_name)
    op.drop_table(table_name)
