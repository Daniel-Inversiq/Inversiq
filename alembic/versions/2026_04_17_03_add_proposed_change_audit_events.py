"""add proposed_change_audit_events table

Revision ID: 2026_04_17_03
Revises: 2026_04_17_02
Create Date: 2026-04-17 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_17_03"
down_revision: Union[str, Sequence[str], None] = "2026_04_17_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_audit_events",
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
        "proposed_change_audit_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcae_change_id",
        "proposed_change_audit_events",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcae_created_at",
        "proposed_change_audit_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pcae_created_at", table_name="proposed_change_audit_events")
    op.drop_index("ix_pcae_change_id", table_name="proposed_change_audit_events")
    op.drop_index("ix_pcae_tenant_id", table_name="proposed_change_audit_events")
    op.drop_table("proposed_change_audit_events")
