"""add outbound_messages

Revision ID: 1d27b27f1f7e
Revises: 2026_04_12_01
Create Date: 2026-04-13 14:18:48.327264

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "1d27b27f1f7e"
down_revision = "2026_04_12_01"
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
    table_name = "outbound_messages"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.String(length=100), nullable=True),
        sa.Column("campaign_id", sa.String(length=100), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=True),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("soul_version", sa.String(length=100), nullable=True),
        sa.Column("variant_id", sa.String(length=100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_outbound_messages_campaign_id"),
        table_name,
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_gmail_message_id"),
        table_name,
        ["gmail_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_gmail_thread_id"),
        table_name,
        ["gmail_thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_lead_id"),
        table_name,
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_recipient_email"),
        table_name,
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_sent_at"),
        table_name,
        ["sent_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    table_name = "outbound_messages"
    if not _table_exists(table_name):
        return

    op.drop_index(op.f("ix_outbound_messages_sent_at"), table_name=table_name)
    op.drop_index(
        op.f("ix_outbound_messages_recipient_email"), table_name=table_name
    )
    op.drop_index(op.f("ix_outbound_messages_lead_id"), table_name=table_name)
    op.drop_index(
        op.f("ix_outbound_messages_gmail_thread_id"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_messages_gmail_message_id"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_outbound_messages_campaign_id"), table_name=table_name
    )
    op.drop_table(table_name)
