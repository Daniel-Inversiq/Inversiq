"""merge migration heads

Revision ID: 00705ebcbfe9
Revises: 2026_04_15_02, 2026_04_18_04
Create Date: 2026-04-22 17:37:05.661101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00705ebcbfe9'
down_revision: Union[str, Sequence[str], None] = ('2026_04_15_02', '2026_04_18_04')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
