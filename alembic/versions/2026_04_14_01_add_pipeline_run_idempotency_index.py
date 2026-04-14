"""add pipeline_run idempotency index

Revision ID: f3g4h5i6j7k8
Revises: e2f3a4b5c6d7
Create Date: 2026-04-14 14:00:00.000000

Adds a composite index on pipeline_runs(tenant_id, lead_id, vertical_id, status)
to make the idempotency guard query in publish_quote efficient.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f3g4h5i6j7k8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index for the idempotency guard query."""
    op.create_index(
        "ix_pipeline_runs_tenant_lead_vertical_status",
        "pipeline_runs",
        ["tenant_id", "lead_id", "vertical_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_runs_tenant_lead_vertical_status",
        table_name="pipeline_runs",
    )
