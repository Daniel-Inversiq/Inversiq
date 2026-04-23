"""add outbound_suggestions

Revision ID: c1d4f2a7e9b1
Revises: b8bf8f541c47
Create Date: 2026-04-14 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "c1d4f2a7e9b1"
down_revision = "b8bf8f541c47"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    if bind.dialect.name == "postgresql":
        return table_name in inspector.get_table_names(schema="public")
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema."""
    table_name = "outbound_suggestions"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_domain", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("campaign_id", sa.String(length=100), nullable=True),
        sa.Column("variant_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_outbound_suggestions_campaign_id"),
        table_name,
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_created_at"),
        table_name,
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_recipient_domain"),
        table_name,
        ["recipient_domain"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_recipient_email"),
        table_name,
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_status"),
        table_name,
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_updated_at"),
        table_name,
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_variant_id"),
        table_name,
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    table_name = "outbound_suggestions"
    if not _table_exists(table_name):
        return

    op.drop_index(
        op.f("ix_outbound_suggestions_variant_id"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_updated_at"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_status"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_recipient_email"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_recipient_domain"),
        table_name=table_name,
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_created_at"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_campaign_id"), table_name=table_name
    )
    op.drop_table(table_name)
