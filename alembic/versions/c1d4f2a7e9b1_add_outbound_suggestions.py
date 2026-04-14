"""add outbound_suggestions

Revision ID: c1d4f2a7e9b1
Revises: b8bf8f541c47
Create Date: 2026-04-14 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d4f2a7e9b1"
down_revision: Union[str, Sequence[str], None] = "b8bf8f541c47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbound_suggestions",
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
        "outbound_suggestions",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_created_at"),
        "outbound_suggestions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_recipient_domain"),
        "outbound_suggestions",
        ["recipient_domain"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_recipient_email"),
        "outbound_suggestions",
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_status"),
        "outbound_suggestions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_updated_at"),
        "outbound_suggestions",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_suggestions_variant_id"),
        "outbound_suggestions",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_outbound_suggestions_variant_id"), table_name="outbound_suggestions"
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_updated_at"), table_name="outbound_suggestions"
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_status"), table_name="outbound_suggestions"
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_recipient_email"), table_name="outbound_suggestions"
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_recipient_domain"),
        table_name="outbound_suggestions",
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_created_at"), table_name="outbound_suggestions"
    )
    op.drop_index(
        op.f("ix_outbound_suggestions_campaign_id"), table_name="outbound_suggestions"
    )
    op.drop_table("outbound_suggestions")
