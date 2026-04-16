"""add step_use, config_hash, step_contract_version

Revision ID: 5c6d7e8f9a0b
Revises: 4b5c6d7e8f9a
Create Date: 2026-04-15 14:00:00.000000

Data integrity layer — Phase 2 additions:

  pipeline_runs.config_hash (VARCHAR 12, nullable)
    12-char SHA-256 prefix over ordered (step_id, step_use) pairs.
    Two runs with the same hash used identical pipeline structure.

  pipeline_step_runs.step_use (VARCHAR 200, nullable)
    The registry key used to execute this step (e.g. "roofing.estimate.v1").
    Complements step_name (the pipeline step ID) for exact reproducibility.

  pipeline_step_runs.step_contract_version (VARCHAR 50, nullable)
    Semantic version from fn.__step_contract__, if the step declared one.
    NULL for steps with no declared contract.

All three columns are nullable and additive — existing rows read as NULL,
which is the correct sentinel for "recorded before this feature existed".
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5c6d7e8f9a0b"
down_revision: Union[str, Sequence[str], None] = "4b5c6d7e8f9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("config_hash", sa.String(12), nullable=True),
    )
    op.add_column(
        "pipeline_step_runs",
        sa.Column("step_use", sa.String(200), nullable=True),
    )
    op.add_column(
        "pipeline_step_runs",
        sa.Column("step_contract_version", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_step_runs", "step_contract_version")
    op.drop_column("pipeline_step_runs", "step_use")
    op.drop_column("pipeline_runs", "config_hash")
