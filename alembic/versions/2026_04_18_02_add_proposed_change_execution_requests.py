"""add proposed_change_execution_requests table

Revision ID: 2026_04_18_02
Revises: 2026_04_18_01
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_18_02"
down_revision: Union[str, Sequence[str], None] = "2026_04_18_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_execution_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("apply_intent_id", sa.Integer(), nullable=True),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="requested",
        ),
        sa.Column("change_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("proposal_payload", sa.Text(), nullable=True),
        sa.Column("governance_snapshot", sa.Text(), nullable=True),
        sa.Column("apply_intent_snapshot", sa.Text(), nullable=True),
        sa.Column("execution_plan_snapshot", sa.Text(), nullable=True),
        sa.Column("preflight_snapshot", sa.Text(), nullable=True),
        sa.Column("monitoring_plan_snapshot", sa.Text(), nullable=True),
        sa.Column("blocking_reasons_snapshot", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "change_id", name="uq_pcer_tenant_change"),
    )
    op.create_index(
        "ix_pcer_tenant_id",
        "proposed_change_execution_requests",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_change_id",
        "proposed_change_execution_requests",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_status",
        "proposed_change_execution_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_created_at",
        "proposed_change_execution_requests",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pcer_created_at", table_name="proposed_change_execution_requests")
    op.drop_index("ix_pcer_status", table_name="proposed_change_execution_requests")
    op.drop_index("ix_pcer_change_id", table_name="proposed_change_execution_requests")
    op.drop_index("ix_pcer_tenant_id", table_name="proposed_change_execution_requests")
    op.drop_table("proposed_change_execution_requests")
