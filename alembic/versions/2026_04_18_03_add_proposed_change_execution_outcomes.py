"""add proposed_change_execution_outcomes table

Revision ID: 2026_04_18_03
Revises: 2026_04_18_02
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "2026_04_18_03"
down_revision: Union[str, Sequence[str], None] = "2026_04_18_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table_name = "proposed_change_execution_outcomes"
    bind = op.get_bind()
    inspector = inspect(bind)
    # Prefer has_table when available; fall back to listed names.
    table_exists = False
    if hasattr(inspector, "has_table"):
        table_exists = inspector.has_table(table_name)
    if not table_exists:
        table_exists = table_name in inspector.get_table_names()

    if not table_exists:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=100), nullable=False),
            sa.Column("execution_request_id", sa.Integer(), nullable=False),
            sa.Column("change_id", sa.String(length=500), nullable=False),
            sa.Column("scope_type", sa.String(length=50), nullable=False),
            sa.Column("scope_id", sa.String(length=200), nullable=False),
            sa.Column("outcome_status", sa.String(length=20), nullable=False),
            sa.Column("evaluation_status", sa.String(length=20), nullable=False),
            sa.Column("observed_metrics_snapshot", sa.Text(), nullable=True),
            sa.Column("expected_metrics_snapshot", sa.Text(), nullable=True),
            sa.Column("deviation_snapshot", sa.Text(), nullable=True),
            sa.Column(
                "rollback_triggered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("rollback_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "execution_request_id", name="uq_pceo_tenant_exec_request"
            ),
        )

    # Refresh inspector state before checking indexes.
    inspector = inspect(bind)
    table_exists = False
    if hasattr(inspector, "has_table"):
        table_exists = inspector.has_table(table_name)
    if not table_exists:
        table_exists = table_name in inspector.get_table_names()

    if table_exists:
        existing_index_names = {
            index["name"] for index in inspector.get_indexes(table_name)
        }
        index_specs = [
            ("ix_pceo_tenant_id", ["tenant_id"]),
            ("ix_pceo_execution_request_id", ["execution_request_id"]),
            ("ix_pceo_change_id", ["change_id"]),
            ("ix_pceo_outcome_status", ["outcome_status"]),
            ("ix_pceo_evaluation_status", ["evaluation_status"]),
            ("ix_pceo_created_at", ["created_at"]),
        ]

        for index_name, index_columns in index_specs:
            if index_name not in existing_index_names:
                op.create_index(index_name, table_name, index_columns, unique=False)


def downgrade() -> None:
    table_name = "proposed_change_execution_outcomes"
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if table_name in existing_tables:
        existing_index_names = {
            index["name"] for index in inspector.get_indexes(table_name)
        }
        for index_name in [
            "ix_pceo_created_at",
            "ix_pceo_evaluation_status",
            "ix_pceo_outcome_status",
            "ix_pceo_change_id",
            "ix_pceo_execution_request_id",
            "ix_pceo_tenant_id",
        ]:
            if index_name in existing_index_names:
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)
