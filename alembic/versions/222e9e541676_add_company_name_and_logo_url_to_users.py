"""add company_name and logo_url to users"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "222e9e541676"
down_revision = "2026_03_21_04"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("company_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("logo_url", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "logo_url")
    op.drop_column("users", "company_name")
