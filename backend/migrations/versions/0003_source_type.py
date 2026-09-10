"""Phase 4.5: source_type, and a snapshot constraint that allows time series.

The column previously held only live/demo. It now also holds `imported`, for
operator-supplied CSV/JSON uploads, so the name `source` was too vague to keep.

Existing values are preserved verbatim: every row already carrying 'live' or
'demo' keeps that value, so nothing is reclassified by this migration.

Also widens the snapshot uniqueness key to include collection_timestamp.
The Phase 4 key (run, platform, external_id) assumed one observation per
listing per batch, which holds for a live run but rejects an imported or
demo dataset carrying the same listing across several dates.

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "marketplace_snapshots"


def upgrade() -> None:
    # Drop the index first: on SQLite the batch rewrite would otherwise try to
    # recreate it against a column name that no longer exists.
    op.drop_index("ix_marketplace_snapshots_source", table_name=TABLE)

    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column(
            "source",
            new_column_name="source_type",
            existing_type=sa.String(length=16),
            existing_nullable=False,
        )

    op.create_index(
        "ix_marketplace_snapshots_source_type", TABLE, ["source_type"]
    )

    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("uq_snapshot_run_platform_item", type_="unique")
        batch.create_unique_constraint(
            "uq_snapshot_run_platform_item_time",
            ["collection_run_id", "platform", "external_id", "collection_timestamp"],
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(
            "uq_snapshot_run_platform_item_time", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_snapshot_run_platform_item",
            ["collection_run_id", "platform", "external_id"],
        )

    op.drop_index("ix_marketplace_snapshots_source_type", table_name=TABLE)

    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column(
            "source_type",
            new_column_name="source",
            existing_type=sa.String(length=16),
            existing_nullable=False,
        )

    op.create_index("ix_marketplace_snapshots_source", TABLE, ["source"])
