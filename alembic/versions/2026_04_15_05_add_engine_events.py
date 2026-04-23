"""add engine_events table

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-04-15 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "7e8f9a0b1c2d"
down_revision = "6d7e8f9a0b1c"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "engine_events"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.String(length=100), nullable=True),
        sa.Column("vertical_id", sa.String(length=100), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=True),
        sa.Column("pipeline_step_run_id", sa.Integer(), nullable=True),
        sa.Column("step_name", sa.String(length=200), nullable=True),
        sa.Column("step_use", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("error_category", sa.String(length=50), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_engine_events_event_type"),
        table_name,
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_occurred_at"),
        table_name,
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_tenant_id"),
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_lead_id"),
        table_name,
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_trace_id"),
        table_name,
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_pipeline_run_id"),
        table_name,
        ["pipeline_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_pipeline_step_run_id"),
        table_name,
        ["pipeline_step_run_id"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "engine_events"
    if not _table_exists(table_name):
        return

    op.drop_index(op.f("ix_engine_events_pipeline_step_run_id"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_pipeline_run_id"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_trace_id"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_lead_id"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_tenant_id"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_occurred_at"), table_name=table_name)
    op.drop_index(op.f("ix_engine_events_event_type"), table_name=table_name)
    op.drop_table(table_name)
