"""Phase 4: marketplace collection fields.

Adds the optional normalized fields, the per-run identifier used for
deduplication, and the ingest warning list. Every column is nullable, so
existing rows are preserved untouched.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "marketplace_snapshots"

NEW_COLUMNS = [
    sa.Column("collection_run_id", sa.String(length=36), nullable=True),
    sa.Column("shipping_info", sa.String(length=255), nullable=True),
    sa.Column("delivery_time", sa.String(length=120), nullable=True),
    sa.Column("badge", sa.String(length=64), nullable=True),
    sa.Column("sponsored", sa.Boolean(), nullable=True),
    sa.Column("specifications", sa.JSON(), nullable=True),
    sa.Column("stock_status", sa.String(length=64), nullable=True),
    sa.Column("warnings", sa.JSON(), nullable=True),
]


def upgrade() -> None:
    # batch_alter_table so SQLite gets a table rewrite that keeps its data,
    # while PostgreSQL uses plain ALTER TABLE.
    with op.batch_alter_table(TABLE) as batch:
        for column in NEW_COLUMNS:
            batch.add_column(column)

    op.create_index(
        "ix_marketplace_snapshots_collection_run_id",
        TABLE,
        ["collection_run_id"],
    )

    # One row per listing per run. Repeated runs over time are the point of
    # this table, so the constraint is scoped to a single run.
    with op.batch_alter_table(TABLE) as batch:
        batch.create_unique_constraint(
            "uq_snapshot_run_platform_item",
            ["collection_run_id", "platform", "external_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("uq_snapshot_run_platform_item", type_="unique")

    op.drop_index("ix_marketplace_snapshots_collection_run_id", table_name=TABLE)

    with op.batch_alter_table(TABLE) as batch:
        for column in reversed(NEW_COLUMNS):
            batch.drop_column(column.name)
