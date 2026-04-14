"""add message_replies

Revision ID: a70b786ab8de
Revises: 1d27b27f1f7e
Create Date: 2026-04-13 15:17:56.657108

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a70b786ab8de"
down_revision: Union[str, Sequence[str], None] = "1d27b27f1f7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "message_replies",
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
        "message_replies",
        ["outbound_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_gmail_message_id"),
        "message_replies",
        ["gmail_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_gmail_thread_id"),
        "message_replies",
        ["gmail_thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_replies_received_at"),
        "message_replies",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_message_replies_received_at"), table_name="message_replies")
    op.drop_index(
        op.f("ix_message_replies_gmail_thread_id"), table_name="message_replies"
    )
    op.drop_index(
        op.f("ix_message_replies_gmail_message_id"), table_name="message_replies"
    )
    op.drop_index(
        op.f("ix_message_replies_outbound_message_id"), table_name="message_replies"
    )
    op.drop_table("message_replies")
