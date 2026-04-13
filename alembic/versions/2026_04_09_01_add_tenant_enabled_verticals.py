"""add enabled_verticals to tenants

Revision ID: 2026_04_09_01
Revises: 2026_03_28_02
Create Date: 2026-04-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_04_09_01"
down_revision: Union[str, Sequence[str], None] = "2026_03_28_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("enabled_verticals", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "enabled_verticals")
