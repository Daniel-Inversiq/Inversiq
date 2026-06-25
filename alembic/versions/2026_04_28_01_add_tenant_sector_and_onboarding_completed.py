"""add sector and onboarding_completed to tenants

Revision ID: 2026_04_28_01
Revises: 00705ebcbfe9
Create Date: 2026-04-28 10:20:00.000000

"""

from sqlalchemy import inspect
from alembic import op
import sqlalchemy as sa


revision = "2026_04_28_01"
down_revision = "00705ebcbfe9"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    for col in inspector.get_columns(table_name):
        if col.get("name") == column_name:
            return True
    return False


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    table_name = "tenants"
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "sector"):
        op.add_column(table_name, sa.Column("sector", sa.String(length=64), nullable=True))
    if not _column_exists(table_name, "onboarding_completed"):
        op.add_column(
            table_name,
            sa.Column(
                "onboarding_completed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if not _index_exists(table_name, "ix_tenants_sector"):
        op.create_index("ix_tenants_sector", table_name, ["sector"], unique=False)


def downgrade() -> None:
    table_name = "tenants"
    if not _table_exists(table_name):
        return

    if _index_exists(table_name, "ix_tenants_sector"):
        op.drop_index("ix_tenants_sector", table_name=table_name)
    if _column_exists(table_name, "onboarding_completed"):
        op.drop_column(table_name, "onboarding_completed")
    if _column_exists(table_name, "sector"):
        op.drop_column(table_name, "sector")
