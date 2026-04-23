"""add pipeline_run models

Revision ID: e2f3a4b5c6d7
Revises: c1d4f2a7e9b1
Create Date: 2026-04-14 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "e2f3a4b5c6d7"
down_revision = "c1d4f2a7e9b1"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create pipeline_runs and pipeline_step_runs tables."""
    if not _table_exists("pipeline_runs"):
        op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.String(length=100), nullable=False),
        sa.Column("vertical_id", sa.String(length=100), nullable=False),
        sa.Column("trace_id", sa.String(length=100), nullable=False),
        sa.Column("pipeline_name", sa.String(length=200), nullable=False),
        sa.Column("engine_version", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="RUNNING",
            nullable=False,
        ),
        sa.Column("failure_step", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_pipeline_runs_tenant_id"),
            "pipeline_runs",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_pipeline_runs_lead_id"), "pipeline_runs", ["lead_id"], unique=False
        )
        op.create_index(
            op.f("ix_pipeline_runs_vertical_id"),
            "pipeline_runs",
            ["vertical_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_pipeline_runs_trace_id"), "pipeline_runs", ["trace_id"], unique=False
        )
        op.create_index(
            op.f("ix_pipeline_runs_status"), "pipeline_runs", ["status"], unique=False
        )

    if not _table_exists("pipeline_step_runs"):
        op.create_table(
        "pipeline_step_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=200), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("output_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=200), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_pipeline_step_runs_pipeline_run_id"),
            "pipeline_step_runs",
            ["pipeline_run_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_pipeline_step_runs_status"),
            "pipeline_step_runs",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    """Drop pipeline_step_runs then pipeline_runs."""
    if _table_exists("pipeline_step_runs"):
        op.drop_index(
            op.f("ix_pipeline_step_runs_status"), table_name="pipeline_step_runs"
        )
        op.drop_index(
            op.f("ix_pipeline_step_runs_pipeline_run_id"),
            table_name="pipeline_step_runs",
        )
        op.drop_table("pipeline_step_runs")

    if _table_exists("pipeline_runs"):
        op.drop_index(op.f("ix_pipeline_runs_status"), table_name="pipeline_runs")
        op.drop_index(op.f("ix_pipeline_runs_trace_id"), table_name="pipeline_runs")
        op.drop_index(op.f("ix_pipeline_runs_vertical_id"), table_name="pipeline_runs")
        op.drop_index(op.f("ix_pipeline_runs_lead_id"), table_name="pipeline_runs")
        op.drop_index(op.f("ix_pipeline_runs_tenant_id"), table_name="pipeline_runs")
        op.drop_table("pipeline_runs")
