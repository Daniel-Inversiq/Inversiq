"""add outbound_messages

Revision ID: 1d27b27f1f7e
Revises: 2026_04_12_01
Create Date: 2026-04-13 14:18:48.327264

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d27b27f1f7e"
down_revision: Union[str, Sequence[str], None] = "2026_04_12_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbound_messages",
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
        "outbound_messages",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_gmail_message_id"),
        "outbound_messages",
        ["gmail_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_gmail_thread_id"),
        "outbound_messages",
        ["gmail_thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_lead_id"),
        "outbound_messages",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_recipient_email"),
        "outbound_messages",
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_messages_sent_at"),
        "outbound_messages",
        ["sent_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_outbound_messages_sent_at"), table_name="outbound_messages")
    op.drop_index(
        op.f("ix_outbound_messages_recipient_email"), table_name="outbound_messages"
    )
    op.drop_index(op.f("ix_outbound_messages_lead_id"), table_name="outbound_messages")
    op.drop_index(
        op.f("ix_outbound_messages_gmail_thread_id"), table_name="outbound_messages"
    )
    op.drop_index(
        op.f("ix_outbound_messages_gmail_message_id"), table_name="outbound_messages"
    )
    op.drop_index(
        op.f("ix_outbound_messages_campaign_id"), table_name="outbound_messages"
    )
    op.drop_table("outbound_messages")
