"""add proposed_change_review_states table

Revision ID: 2026_04_17_02
Revises: 2026_04_17_01
Create Date: 2026-04-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_17_02"
down_revision: Union[str, Sequence[str], None] = "2026_04_17_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_change_review_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("change_id", sa.String(length=500), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("change_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("proposal_payload", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "change_id", name="uq_pcrs_tenant_change"),
    )
    op.create_index(
        "ix_pcrs_tenant_id",
        "proposed_change_review_states",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcrs_change_id",
        "proposed_change_review_states",
        ["change_id"],
        unique=False,
    )
    op.create_index(
        "ix_pcrs_status",
        "proposed_change_review_states",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pcrs_status", table_name="proposed_change_review_states")
    op.drop_index("ix_pcrs_change_id", table_name="proposed_change_review_states")
    op.drop_index("ix_pcrs_tenant_id", table_name="proposed_change_review_states")
    op.drop_table("proposed_change_review_states")
