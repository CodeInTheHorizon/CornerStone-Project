"""Listing-page sweeps: scrape_listing_pages, and many observations per attempt.

A search or best-seller page yields 20-30 observations from one request, so
product_observations.attempt_id stops being unique. SQLite cannot drop that
unnamed constraint in place: the table is rebuilt (rows preserved) and the
append-only trigger from 0012 is recreated on the new table.

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_BigId = sa.BigInteger().with_variant(sa.Integer, "sqlite")

_SQLITE_TRIGGER = """
CREATE TRIGGER product_observations_no_update
BEFORE UPDATE ON product_observations
BEGIN
    SELECT RAISE(ABORT, 'product_observations is append-only; insert a new observation instead');
END
"""


def _observations_0012_without_unique() -> sa.Table:
    """0012's product_observations, minus UNIQUE(attempt_id): the batch rebuild's template."""
    return sa.Table(
        "product_observations", sa.MetaData(),
        sa.Column("id", _BigId, primary_key=True, autoincrement=True),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("scrape_targets.id"), nullable=False),
        sa.Column("attempt_id", _BigId, sa.ForeignKey("scrape_attempts.id"), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("platform_product_id", sa.String(128), nullable=False),
        sa.Column("product_url", sa.Text, nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(1000), nullable=False),
        sa.Column("brand", sa.String(255)),
        sa.Column("category", sa.String(255)),
        sa.Column("category_path", sa.String(1000)),
        sa.Column("model", sa.String(255)),
        sa.Column("variant", sa.String(500)),
        sa.Column("current_price", sa.Numeric(10, 2)),
        sa.Column("mrp", sa.Numeric(10, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("discount_percentage", sa.Numeric(5, 2)),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("rating_count", sa.BigInteger),
        sa.Column("review_count", sa.BigInteger),
        sa.Column("availability", sa.String(24), nullable=False),
        sa.Column("availability_text", sa.String(255)),
        sa.Column("seller_name", sa.String(255)),
        sa.Column("warnings", sa.JSON),
        sa.Index("ix_product_observations_target_time", "target_id", "collected_at"),
        sa.Index("ix_product_observations_pid_time", "marketplace", "platform_product_id", "collected_at"),
    )


def upgrade() -> None:
    dialect = op.get_context().dialect.name

    op.create_table(
        "scrape_listing_pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("max_pages", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("auto_track", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("refresh_interval_minutes", sa.Integer, nullable=False, server_default=sa.text("1440")),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome", sa.String(32), nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_items", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("marketplace", "url", name="uq_scrape_listing_marketplace_url"),
    )
    op.create_index("ix_scrape_listing_pages_due", "scrape_listing_pages", ["marketplace", "is_active", "next_due_at"])

    with op.batch_alter_table("scrape_attempts") as batch:
        batch.add_column(sa.Column("listing_page_id", sa.Integer, nullable=True))
        batch.add_column(sa.Column("page_number", sa.Integer, nullable=True))
        batch.add_column(sa.Column("items_found", sa.Integer, nullable=True))
        batch.create_foreign_key("fk_scrape_attempts_listing_page", "scrape_listing_pages", ["listing_page_id"], ["id"])

    if dialect == "sqlite":
        batch_kwargs = {"copy_from": _observations_0012_without_unique(), "recreate": "always"}
    else:
        batch_kwargs = {}
        op.drop_constraint("product_observations_attempt_id_key", "product_observations", type_="unique")
    with op.batch_alter_table("product_observations", **batch_kwargs) as batch:
        batch.add_column(sa.Column("listing_page_id", sa.Integer, nullable=True))
        batch.add_column(sa.Column("list_rank", sa.Integer, nullable=True))
        batch.add_column(sa.Column("sponsored", sa.Boolean, nullable=True))
        batch.create_foreign_key("fk_product_observations_listing_page", "scrape_listing_pages", ["listing_page_id"], ["id"])
    op.create_index("ix_product_observations_attempt_id", "product_observations", ["attempt_id"])

    if dialect == "sqlite":
        # The rebuild dropped the 0012 trigger along with the old table.
        op.execute("DROP TRIGGER IF EXISTS product_observations_no_update")
        op.execute(_SQLITE_TRIGGER)


def downgrade() -> None:
    # Reinstating UNIQUE(attempt_id) would fail once listing observations exist; 0013 is one-way.
    raise NotImplementedError("0013 cannot be downgraded once listing observations share attempts.")
