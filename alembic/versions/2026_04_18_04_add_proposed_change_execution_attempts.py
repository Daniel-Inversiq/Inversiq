"""add proposed_change_execution_attempts table

Revision ID: 2026_04_18_04
Revises: 2026_04_18_03
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_18_04"
down_revision: Union[str, Sequence[str], None] = "2026_04_18_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_execution_attempts",
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
        "proposed_change_execution_attempts",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_execution_request_id",
        "proposed_change_execution_attempts",
        ["execution_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_change_id",
        "proposed_change_execution_attempts",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_status",
        "proposed_change_execution_attempts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_pcea_created_at",
        "proposed_change_execution_attempts",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pcea_created_at", table_name="proposed_change_execution_attempts")
    op.drop_index("ix_pcea_status", table_name="proposed_change_execution_attempts")
    op.drop_index("ix_pcea_change_id", table_name="proposed_change_execution_attempts")
    op.drop_index(
        "ix_pcea_execution_request_id",
        table_name="proposed_change_execution_attempts",
    )
    op.drop_index("ix_pcea_tenant_id", table_name="proposed_change_execution_attempts")
    op.drop_table("proposed_change_execution_attempts")
