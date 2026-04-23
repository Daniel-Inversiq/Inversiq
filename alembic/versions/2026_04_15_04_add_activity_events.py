"""add activity_events table

Revision ID: 6d7e8f9a0b1c
Revises: 5c6d7e8f9a0b
Create Date: 2026-04-15 16:30:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "6d7e8f9a0b1c"
down_revision = "5c6d7e8f9a0b"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "activity_events"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("link_url", sa.String(length=1024), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activity_events_tenant_id",
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_event_type",
        table_name,
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_created_at",
        table_name,
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "activity_events"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_activity_events_created_at", table_name=table_name)
    op.drop_index("ix_activity_events_event_type", table_name=table_name)
    op.drop_index("ix_activity_events_tenant_id", table_name=table_name)
    op.drop_table(table_name)
