"""Log every LIVE provider fetch for provenance, status and rate-limit cooldowns.

Additive only: creates collection_attempts and touches no existing table or row.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("collection_run_id", sa.String(36), nullable=False),
        sa.Column("search_query", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_received", sa.Integer(), nullable=False),
        sa.Column("items_stored", sa.Integer(), nullable=False),
        sa.Column("items_rejected", sa.Integer(), nullable=False),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_run_id"),
    )
    op.create_index(
        "ix_collection_attempts_platform_started",
        "collection_attempts",
        ["platform", "started_at"],
    )


def downgrade() -> None:
    # Drops the fetch log only; stored snapshots are untouched.
    op.drop_index("ix_collection_attempts_platform_started", table_name="collection_attempts")
    op.drop_table("collection_attempts")
