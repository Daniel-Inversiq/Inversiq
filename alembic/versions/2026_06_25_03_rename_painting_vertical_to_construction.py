"""Rename painting vertical ID to construction.

Revision ID: 2026_06_25_03
Revises: 2026_06_25_02
Create Date: 2026-06-25
"""

from alembic import op

revision = "2026_06_25_03"
down_revision = "2026_06_25_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate tenant.sector
    op.execute(
        """
        UPDATE tenants
        SET sector = 'construction'
        WHERE sector = 'painting'
        """
    )

    # Migrate tenant.enabled_verticals (stored as JSON array)
    op.execute(
        """
        UPDATE tenants
        SET enabled_verticals = (
            SELECT jsonb_agg(
                CASE WHEN v = 'painting' THEN 'construction' ELSE v END
            )
            FROM jsonb_array_elements_text(enabled_verticals::jsonb) AS v
        )
        WHERE enabled_verticals::jsonb @> '["painting"]'::jsonb
        """
    )

    # Migrate pipeline_runs.vertical_id (historical run data)
    op.execute(
        """
        UPDATE pipeline_runs
        SET vertical_id = 'construction'
        WHERE vertical_id IN ('painting', 'paintly', 'painters_us', 'painters_nl')
        """
    )

    # Migrate leads.vertical (if column exists)
    op.execute(
        """
        UPDATE leads
        SET vertical = 'construction'
        WHERE vertical IN ('painting', 'paintly', 'painters_us', 'painters_nl')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tenants
        SET sector = 'painting'
        WHERE sector = 'construction'
        """
    )

    op.execute(
        """
        UPDATE tenants
        SET enabled_verticals = (
            SELECT jsonb_agg(
                CASE WHEN v = 'construction' THEN 'painting' ELSE v END
            )
            FROM jsonb_array_elements_text(enabled_verticals::jsonb) AS v
        )
        WHERE enabled_verticals::jsonb @> '["construction"]'::jsonb
        """
    )

    op.execute(
        """
        UPDATE pipeline_runs
        SET vertical_id = 'paintly'
        WHERE vertical_id = 'construction'
        """
    )

    op.execute(
        """
        UPDATE leads
        SET vertical = 'paintly'
        WHERE vertical = 'construction'
        """
    )
