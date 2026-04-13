"""add is_platform_admin to users

Revision ID: 2026_03_27_01
Revises: 222e9e541676
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026_03_27_01"
down_revision: Union[str, Sequence[str], None] = "222e9e541676"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("users", "is_platform_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
