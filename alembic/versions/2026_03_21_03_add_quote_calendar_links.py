"""add quote calendar links table

Revision ID: 2026_03_21_03
Revises: 2026_03_21_02
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "2026_03_21_03"
down_revision = "2026_03_21_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    table_name = "quote_calendar_links"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("quote_id", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="google"),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quote_id",
            "provider",
            name="uq_quote_calendar_links_quote_provider",
        ),
    )
    op.create_index(
        "ix_quote_calendar_links_tenant_id",
        table_name,
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_calendar_links_quote_id",
        table_name,
        ["quote_id"],
        unique=False,
    )


def downgrade() -> None:
    table_name = "quote_calendar_links"
    if not _table_exists(table_name):
        return

    op.drop_index("ix_quote_calendar_links_quote_id", table_name=table_name)
    op.drop_index("ix_quote_calendar_links_tenant_id", table_name=table_name)
    op.drop_table(table_name)
