"""add run_review_states table

Revision ID: 2026_04_17_01
Revises: a1b2c3d4e5f6
Create Date: 2026-04-17 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "2026_04_17_01"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table_name = "run_review_states"
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    if dialect == "postgresql":
        existing_tables = inspector.get_table_names(schema="public")
    else:
        existing_tables = inspector.get_table_names()

    if table_name not in existing_tables:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pipeline_run_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.String(length=100), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("note", sa.Text(), nullable=True),
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
                "pipeline_run_id", name="uq_run_review_states_pipeline_run_id"
            ),
        )

    inspector = inspect(bind)
    if dialect == "postgresql":
        existing_tables = inspector.get_table_names(schema="public")
    else:
        existing_tables = inspector.get_table_names()

    if table_name in existing_tables:
        if dialect == "postgresql":
            existing_index_names = {
                idx["name"]
                for idx in inspector.get_indexes(table_name, schema="public")
            }
        else:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes(table_name)
            }

        index_specs = [
            ("ix_run_review_states_pipeline_run_id", ["pipeline_run_id"], True),
            ("ix_run_review_states_tenant_id", ["tenant_id"], False),
        ]

        for index_name, index_columns, is_unique in index_specs:
            if index_name not in existing_index_names:
                op.create_index(
                    index_name,
                    table_name,
                    index_columns,
                    unique=is_unique,
                )


def downgrade() -> None:
    table_name = "run_review_states"
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect = bind.dialect.name

    if dialect == "postgresql":
        existing_tables = inspector.get_table_names(schema="public")
    else:
        existing_tables = inspector.get_table_names()

    if table_name in existing_tables:
        if dialect == "postgresql":
            existing_index_names = {
                idx["name"]
                for idx in inspector.get_indexes(table_name, schema="public")
            }
        else:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes(table_name)
            }

        for index_name in [
            "ix_run_review_states_tenant_id",
            "ix_run_review_states_pipeline_run_id",
        ]:
            if index_name in existing_index_names:
                op.drop_index(index_name, table_name=table_name)

        op.drop_table(table_name)
