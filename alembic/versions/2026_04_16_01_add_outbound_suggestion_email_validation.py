"""add email validation fields to outbound_suggestions

Revision ID: a1b2c3d4e5f6
Revises: 7e8f9a0b1c2d
Create Date: 2026-04-16 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7e8f9a0b1c2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbound_suggestions",
        sa.Column("email_validation_result", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "outbound_suggestions",
        sa.Column(
            "is_deliverability_risky",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "outbound_suggestions",
        sa.Column("validation_reason", sa.String(length=512), nullable=True),
    )
    op.alter_column(
        "outbound_suggestions",
        "is_deliverability_risky",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("outbound_suggestions", "validation_reason")
    op.drop_column("outbound_suggestions", "is_deliverability_risky")
    op.drop_column("outbound_suggestions", "email_validation_result")
