"""add calendar_events for persisted Google events

Revision ID: 2026_03_28_02
Revises: 2026_03_28_01
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_03_28_02"
down_revision = "2026_03_28_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "calendar_events"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("google_event_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("html_link", sa.Text(), nullable=True),
        sa.Column("quote_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "google_event_id",
            name="uq_calendar_events_tenant_google_event",
        ),
    )
    op.create_index(
        "ix_calendar_events_tenant_id",
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_quote_id",
        table_name,
        ["quote_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_tenant_start",
        table_name,
        ["tenant_id", "start_datetime"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "calendar_events"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_calendar_events_tenant_start", table_name=table_name)
    op.drop_index("ix_calendar_events_quote_id", table_name=table_name)
    op.drop_index("ix_calendar_events_tenant_id", table_name=table_name)
    op.drop_table(table_name)
