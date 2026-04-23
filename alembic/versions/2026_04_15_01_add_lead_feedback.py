"""add lead_feedback table

Revision ID: 2026_04_15_01
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "2026_04_15_01"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "lead_feedback"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
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
        op.f("ix_lead_feedback_tenant_id"), table_name, ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_lead_feedback_lead_id"), table_name, ["lead_id"], unique=False
    )


def downgrade() -> None:
    table_name = "lead_feedback"
    if not _table_exists(table_name):
        return

    op.drop_index(op.f("ix_lead_feedback_lead_id"), table_name=table_name)
    op.drop_index(op.f("ix_lead_feedback_tenant_id"), table_name=table_name)
    op.drop_table(table_name)
