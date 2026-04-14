"""add classification_label to message_replies

Revision ID: b8bf8f541c47
Revises: a70b786ab8de
Create Date: 2026-04-13 15:34:55.660776

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8bf8f541c47"
down_revision: Union[str, Sequence[str], None] = "a70b786ab8de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "message_replies",
        sa.Column("classification_label", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("message_replies", "classification_label")
