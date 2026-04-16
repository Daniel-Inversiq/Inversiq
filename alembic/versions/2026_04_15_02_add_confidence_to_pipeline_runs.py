"""add confidence columns to pipeline_step_runs and pipeline_runs

Revision ID: 2026_04_15_02
Revises: 3a1b2c4d5e6f, 2026_04_15_01
Create Date: 2026-04-15

Adds optional confidence columns so steps can annotate their output with a
0–1 confidence score.  All columns are nullable — existing rows and any step
that does not report confidence are unaffected.

pipeline_step_runs:
  confidence_score   Float     — 0.0–1.0, null = step did not report confidence
  confidence_label   String    — "low" | "medium" | "high", derived from score
  confidence_reason  Text      — optional plain-text explanation

pipeline_runs:
  overall_confidence_score  Float   — min() of step scores (weakest-link)
  overall_confidence_label  String  — derived label for the overall score
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_04_15_02"
# Merges the error_category branch (3a1b2c4d5e6f) and lead_feedback branch
# (2026_04_15_01) so the migration graph has a single head again.
down_revision: Union[str, Sequence[str], None] = ("3a1b2c4d5e6f", "2026_04_15_01")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step-level confidence
    op.add_column(
        "pipeline_step_runs",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "pipeline_step_runs",
        sa.Column("confidence_label", sa.String(10), nullable=True),
    )
    op.add_column(
        "pipeline_step_runs",
        sa.Column("confidence_reason", sa.Text(), nullable=True),
    )

    # Run-level overall confidence (weakest-link propagation)
    op.add_column(
        "pipeline_runs",
        sa.Column("overall_confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "pipeline_runs",
        sa.Column("overall_confidence_label", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_runs", "overall_confidence_label")
    op.drop_column("pipeline_runs", "overall_confidence_score")
    op.drop_column("pipeline_step_runs", "confidence_reason")
    op.drop_column("pipeline_step_runs", "confidence_label")
    op.drop_column("pipeline_step_runs", "confidence_score")
