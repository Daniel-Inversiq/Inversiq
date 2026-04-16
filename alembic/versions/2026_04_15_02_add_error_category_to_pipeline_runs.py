"""add error_category to pipeline_runs

Revision ID: 4b5c6d7e8f9a
Revises: 3a1b2c4d5e6f
Create Date: 2026-04-15 12:00:00.000000

Adds error_category (transient | permanent | validation | external_dependency)
to pipeline_runs, denormalised from the failing step so callers can filter
failed runs by recoverability without joining on pipeline_step_runs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4b5c6d7e8f9a"
down_revision: Union[str, Sequence[str], None] = "3a1b2c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("error_category", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_runs", "error_category")
