"""add message_replies

Revision ID: a70b786ab8de
Revises: 1d27b27f1f7e
Create Date: 2026-04-13 15:17:56.657108

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "a70b786ab8de"
down_revision = "1d27b27f1f7e"
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
    table_name = "message_replies"
    if _table_exists(table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("outbound_message_id", sa.String(length=100), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=False),
        sa.Column("from_email", sa.String(length=320), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["outbound_message_id"],
            ["outbound_messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_replies_outbound_message_id"),
        table_name,
        ["outbound_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_gmail_message_id"),
        table_name,
        ["gmail_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_gmail_thread_id"),
        table_name,
        ["gmail_thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_received_at"),
        table_name,
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    table_name = "message_replies"
    if not _table_exists(table_name):
        return

    op.drop_index(op.f("ix_message_replies_received_at"), table_name=table_name)
    op.drop_index(
        op.f("ix_message_replies_gmail_thread_id"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_message_replies_gmail_message_id"), table_name=table_name
    )
    op.drop_index(
        op.f("ix_message_replies_outbound_message_id"), table_name=table_name
    )
    op.drop_table(table_name)
