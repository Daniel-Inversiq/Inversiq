"""add welcome_email_sent_at to tenants

Revision ID: 2026_03_28_01
Revises: 2026_03_27_01
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_03_28_01"
down_revision: Union[str, Sequence[str], None] = "2026_03_27_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("welcome_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "welcome_email_sent_at")
