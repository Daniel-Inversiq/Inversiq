"""add proposed_change_execution_outcomes table

Revision ID: 2026_04_18_03
Revises: 2026_04_18_02
Create Date: 2026-04-18 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "2026_04_18_03"
down_revision = "2026_04_18_02"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    dialect = bind.dialect.name

    if dialect == "postgresql":
        result = bind.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
        return bool(result.scalar())

    if dialect == "sqlite":
        result = bind.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name=:table_name
                """
            ),
            {"table_name": table_name},
        )
        return result.scalar() is not None

    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name
    if dialect == "postgresql":
        return {
            idx["name"] for idx in inspector.get_indexes(table_name, schema="public")
        }
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    table_name = "proposed_change_execution_outcomes"
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS proposed_change_execution_outcomes (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(100) NOT NULL,
                    execution_request_id INTEGER NOT NULL,
                    change_id VARCHAR(500) NOT NULL,
                    scope_type VARCHAR(50) NOT NULL,
                    scope_id VARCHAR(200) NOT NULL,
                    outcome_status VARCHAR(20) NOT NULL,
                    evaluation_status VARCHAR(20) NOT NULL,
                    observed_metrics_snapshot TEXT,
                    expected_metrics_snapshot TEXT,
                    deviation_snapshot TEXT,
                    rollback_triggered BOOLEAN DEFAULT FALSE NOT NULL,
                    rollback_reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT uq_pceo_tenant_exec_request UNIQUE (tenant_id, execution_request_id)
                );
                """
            )
        )

        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_tenant_id ON proposed_change_execution_outcomes (tenant_id);"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_execution_request_id ON proposed_change_execution_outcomes (execution_request_id);"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_change_id ON proposed_change_execution_outcomes (change_id);"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_outcome_status ON proposed_change_execution_outcomes (outcome_status);"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_evaluation_status ON proposed_change_execution_outcomes (evaluation_status);"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pceo_created_at ON proposed_change_execution_outcomes (created_at);"
            )
        )
        return

    # fallback for sqlite/local
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if table_name not in existing_tables:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=100), nullable=False),
            sa.Column("execution_request_id", sa.Integer(), nullable=False),
            sa.Column("change_id", sa.String(length=500), nullable=False),
            sa.Column("scope_type", sa.String(length=50), nullable=False),
            sa.Column("scope_id", sa.String(length=200), nullable=False),
            sa.Column("outcome_status", sa.String(length=20), nullable=False),
            sa.Column("evaluation_status", sa.String(length=20), nullable=False),
            sa.Column("observed_metrics_snapshot", sa.Text(), nullable=True),
            sa.Column("expected_metrics_snapshot", sa.Text(), nullable=True),
            sa.Column("deviation_snapshot", sa.Text(), nullable=True),
            sa.Column(
                "rollback_triggered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("rollback_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "execution_request_id", name="uq_pceo_tenant_exec_request"
            ),
        )

    inspector = sa.inspect(bind)
    existing_index_names = {idx["name"] for idx in inspector.get_indexes(table_name)}

    index_specs = [
        ("ix_pceo_tenant_id", ["tenant_id"]),
        ("ix_pceo_execution_request_id", ["execution_request_id"]),
        ("ix_pceo_change_id", ["change_id"]),
        ("ix_pceo_outcome_status", ["outcome_status"]),
        ("ix_pceo_evaluation_status", ["evaluation_status"]),
        ("ix_pceo_created_at", ["created_at"]),
    ]

    for index_name, index_columns in index_specs:
        if index_name not in existing_index_names:
            op.create_index(index_name, table_name, index_columns, unique=False)
