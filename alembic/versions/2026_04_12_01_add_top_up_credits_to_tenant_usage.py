"""add top_up_credits to tenant_usage

Revision ID: 2026_04_12_01
Revises: 2026_04_09_01
Create Date: 2026-04-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_12_01"
down_revision: Union[str, Sequence[str], None] = "2026_04_09_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_usage",
        sa.Column("top_up_credits", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE tenant_usage SET top_up_credits = 0 WHERE top_up_credits IS NULL")
    op.alter_column("tenant_usage", "top_up_credits", nullable=False)


def downgrade() -> None:
    op.drop_column("tenant_usage", "top_up_credits")
