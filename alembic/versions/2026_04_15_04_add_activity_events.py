"""add activity_events table

Revision ID: 6d7e8f9a0b1c
Revises: 5c6d7e8f9a0b
Create Date: 2026-04-15 16:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d7e8f9a0b1c"
down_revision: Union[str, Sequence[str], None] = "5c6d7e8f9a0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
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
        "activity_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_event_type",
        "activity_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_created_at",
        "activity_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_index("ix_activity_events_tenant_id", table_name="activity_events")
    op.drop_table("activity_events")
