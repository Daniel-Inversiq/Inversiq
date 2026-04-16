"""add lead_feedback table

Revision ID: 2026_04_15_01
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_04_15_01"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_feedback",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.String(length=100), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actual_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("override_reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lead_feedback_tenant_id"), "lead_feedback", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_lead_feedback_lead_id"), "lead_feedback", ["lead_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_feedback_lead_id"), table_name="lead_feedback")
    op.drop_index(op.f("ix_lead_feedback_tenant_id"), table_name="lead_feedback")
    op.drop_table("lead_feedback")
