"""add error_category to pipeline_step_runs

Revision ID: 3a1b2c4d5e6f
Revises: f3g4h5i6j7k8
Create Date: 2026-04-15 10:00:00.000000

Adds error_category (transient | permanent | validation | external_dependency)
to pipeline_step_runs so structured failure taxonomy is persisted alongside
existing error_type / error_message columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3a1b2c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_step_runs",
        sa.Column("error_category", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_step_runs", "error_category")
