"""add engine_events table

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-04-15 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "7e8f9a0b1c2d"
down_revision: Union[str, Sequence[str], None] = "6d7e8f9a0b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engine_events",
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
        "engine_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_occurred_at"),
        "engine_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_tenant_id"),
        "engine_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_lead_id"),
        "engine_events",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_trace_id"),
        "engine_events",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_pipeline_run_id"),
        "engine_events",
        ["pipeline_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engine_events_pipeline_step_run_id"),
        "engine_events",
        ["pipeline_step_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_engine_events_pipeline_step_run_id"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_pipeline_run_id"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_trace_id"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_lead_id"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_tenant_id"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_occurred_at"), table_name="engine_events")
    op.drop_index(op.f("ix_engine_events_event_type"), table_name="engine_events")
    op.drop_table("engine_events")
