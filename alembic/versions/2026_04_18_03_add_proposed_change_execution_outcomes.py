"""add proposed_change_execution_outcomes table

Revision ID: 2026_04_18_03
Revises: 2026_04_18_02
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_18_03"
down_revision: Union[str, Sequence[str], None] = "2026_04_18_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_execution_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("execution_request_id", sa.Integer(), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column("outcome_status", sa.String(length=20), nullable=False),
        sa.Column("evaluation_status", sa.String(length=20), nullable=False),
        sa.Column("observed_metrics_snapshot", sa.Text(), nullable=True),
        sa.Column("expected_metrics_snapshot", sa.Text(), nullable=True),
        sa.Column("deviation_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "rollback_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
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
            "tenant_id", "execution_request_id", name="uq_pceo_tenant_exec_request"
        ),
    )
    op.create_index(
        "ix_pceo_tenant_id",
        "proposed_change_execution_outcomes",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pceo_execution_request_id",
        "proposed_change_execution_outcomes",
        ["execution_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_pceo_change_id",
        "proposed_change_execution_outcomes",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pceo_outcome_status",
        "proposed_change_execution_outcomes",
        ["outcome_status"],
        unique=False,
    )
    op.create_index(
        "ix_pceo_evaluation_status",
        "proposed_change_execution_outcomes",
        ["evaluation_status"],
        unique=False,
    )
    op.create_index(
        "ix_pceo_created_at",
        "proposed_change_execution_outcomes",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pceo_created_at", table_name="proposed_change_execution_outcomes")
    op.drop_index(
        "ix_pceo_evaluation_status", table_name="proposed_change_execution_outcomes"
    )
    op.drop_index(
        "ix_pceo_outcome_status", table_name="proposed_change_execution_outcomes"
    )
    op.drop_index("ix_pceo_change_id", table_name="proposed_change_execution_outcomes")
    op.drop_index(
        "ix_pceo_execution_request_id",
        table_name="proposed_change_execution_outcomes",
    )
    op.drop_index("ix_pceo_tenant_id", table_name="proposed_change_execution_outcomes")
    op.drop_table("proposed_change_execution_outcomes")
