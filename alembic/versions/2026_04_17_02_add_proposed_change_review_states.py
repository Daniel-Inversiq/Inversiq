"""add proposed_change_review_states table

Revision ID: 2026_04_17_02
Revises: 2026_04_17_01
Create Date: 2026-04-17 10:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "2026_04_17_02"
down_revision = "2026_04_17_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table_name = "proposed_change_review_states"
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
            sa.Column("tenant_id", sa.String(length=100), nullable=False),
            sa.Column("change_id", sa.String(length=500), nullable=False),
            sa.Column("scope_type", sa.String(length=50), nullable=False),
            sa.Column("scope_id", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("change_type", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("proposal_payload", sa.Text(), nullable=True),
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
                "tenant_id", "change_id", name="uq_pcrs_tenant_change"
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
                idx["name"] for idx in inspector.get_indexes(table_name, schema="public")
            }
        else:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes(table_name)
            }

        index_specs = [
            ("ix_pcrs_tenant_id", ["tenant_id"], False),
            ("ix_pcrs_change_id", ["change_id"], False),
            ("ix_pcrs_status", ["status"], False),
            ("ix_pcrs_scope_type", ["scope_type"], False),
            ("ix_pcrs_scope_id", ["scope_id"], False),
            ("ix_pcrs_created_at", ["created_at"], False),
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
    table_name = "proposed_change_review_states"
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
                idx["name"] for idx in inspector.get_indexes(table_name, schema="public")
            }
        else:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes(table_name)
            }

        for index_name in [
            "ix_pcrs_created_at",
            "ix_pcrs_scope_id",
            "ix_pcrs_scope_type",
            "ix_pcrs_status",
            "ix_pcrs_change_id",
            "ix_pcrs_tenant_id",
        ]:
            if index_name in existing_index_names:
                op.drop_index(index_name, table_name=table_name)

        op.drop_table(table_name)