"""add run_review_states table

Revision ID: 2026_04_17_01
Revises: a1b2c3d4e5f6
Create Date: 2026-04-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_17_01"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "run_review_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("pipeline_run_id", name="uq_run_review_states_pipeline_run_id"),
    )
    op.create_index(
        "ix_run_review_states_pipeline_run_id",
        "run_review_states",
        ["pipeline_run_id"],
        unique=True,
    )
    op.create_index(
        "ix_run_review_states_tenant_id",
        "run_review_states",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_run_review_states_tenant_id", table_name="run_review_states")
    op.drop_index("ix_run_review_states_pipeline_run_id", table_name="run_review_states")
    op.drop_table("run_review_states")
