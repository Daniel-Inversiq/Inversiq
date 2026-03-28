"""add calendar_events for persisted Google events

Revision ID: 2026_03_28_02
Revises: 2026_03_28_01
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_03_28_02"
down_revision: Union[str, Sequence[str], None] = "2026_03_28_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
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
        "calendar_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_quote_id",
        "calendar_events",
        ["quote_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_tenant_start",
        "calendar_events",
        ["tenant_id", "start_datetime"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_events_tenant_start", table_name="calendar_events")
    op.drop_index("ix_calendar_events_quote_id", table_name="calendar_events")
    op.drop_index("ix_calendar_events_tenant_id", table_name="calendar_events")
    op.drop_table("calendar_events")
