"""add proposed_change_apply_intents table

Revision ID: 2026_04_18_01
Revises: 2026_04_17_03
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_18_01"
down_revision: Union[str, Sequence[str], None] = "2026_04_17_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_apply_intents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="ready_for_apply",
        ),
        sa.Column("change_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("proposal_payload", sa.Text(), nullable=True),
        sa.Column("governance_snapshot", sa.Text(), nullable=True),
        sa.Column("apply_plan_snapshot", sa.Text(), nullable=True),
        sa.Column("preflight_snapshot", sa.Text(), nullable=True),
        sa.Column("rollback_snapshot", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "change_id", name="uq_pcai_tenant_change"),
    )
    op.create_index(
        "ix_pcai_tenant_id",
        "proposed_change_apply_intents",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcai_change_id",
        "proposed_change_apply_intents",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcai_status",
        "proposed_change_apply_intents",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pcai_created_at",
        "proposed_change_apply_intents",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pcai_created_at", table_name="proposed_change_apply_intents")
    op.drop_index("ix_pcai_status", table_name="proposed_change_apply_intents")
    op.drop_index("ix_pcai_change_id", table_name="proposed_change_apply_intents")
    op.drop_index("ix_pcai_tenant_id", table_name="proposed_change_apply_intents")
    op.drop_table("proposed_change_apply_intents")
