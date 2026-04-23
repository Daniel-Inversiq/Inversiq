"""add proposed_change_execution_requests table

Revision ID: 2026_04_18_02
Revises: 2026_04_18_01
Create Date: 2026-04-18 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_04_18_02"
down_revision = "2026_04_18_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "proposed_change_execution_requests"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
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
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_change_id",
        table_name,
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_status",
        table_name,
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pcer_created_at",
        table_name,
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "proposed_change_execution_requests"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_pcer_created_at", table_name=table_name)
    op.drop_index("ix_pcer_status", table_name=table_name)
    op.drop_index("ix_pcer_change_id", table_name=table_name)
    op.drop_index("ix_pcer_tenant_id", table_name=table_name)
    op.drop_table(table_name)
