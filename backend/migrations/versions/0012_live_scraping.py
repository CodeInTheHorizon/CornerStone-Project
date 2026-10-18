"""Live product-page scraping: targets, append-only observations, attempts, source states.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_BigId = sa.BigInteger().with_variant(sa.Integer, "sqlite")

_PG_FUNCTION = """
CREATE OR REPLACE FUNCTION product_observations_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'product_observations is append-only; insert a new observation instead';
END
$$
"""
_PG_TRIGGER = """
CREATE TRIGGER product_observations_no_update
BEFORE UPDATE ON product_observations
FOR EACH ROW EXECUTE FUNCTION product_observations_append_only()
"""
_SQLITE_TRIGGER = """
CREATE TRIGGER product_observations_no_update
BEFORE UPDATE ON product_observations
BEGIN
    SELECT RAISE(ABORT, 'product_observations is append-only; insert a new observation instead');
END
"""


def upgrade() -> None:
    op.create_table(
        "scrape_targets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("platform_product_id", sa.String(128), nullable=False),
        sa.Column("product_url", sa.Text, nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=True, index=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("refresh_interval_minutes", sa.Integer, nullable=False, server_default=sa.text("1440")),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome", sa.String(32), nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("marketplace", "platform_product_id", name="uq_scrape_target_marketplace_pid"),
    )
    op.create_index("ix_scrape_targets_due", "scrape_targets", ["marketplace", "is_active", "next_due_at"])

    op.create_table(
        "scrape_attempts",
        sa.Column("id", _BigId, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("scrape_targets.id"), nullable=True),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("elapsed_ms", sa.Integer, nullable=True),
        sa.Column("http_attempts", sa.Integer, nullable=True),
    )
    op.create_index("ix_scrape_attempts_marketplace_started", "scrape_attempts", ["marketplace", "started_at"])
    op.create_index("ix_scrape_attempts_target_started", "scrape_attempts", ["target_id", "started_at"])

    op.create_table(
        "product_observations",
        sa.Column("id", _BigId, primary_key=True, autoincrement=True),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("scrape_targets.id"), nullable=False),
        sa.Column("attempt_id", _BigId, sa.ForeignKey("scrape_attempts.id"), nullable=False, unique=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("platform_product_id", sa.String(128), nullable=False),
        sa.Column("product_url", sa.Text, nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(1000), nullable=False),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("category_path", sa.String(1000), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("variant", sa.String(500), nullable=True),
        sa.Column("current_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("mrp", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("rating_count", sa.BigInteger, nullable=True),
        sa.Column("review_count", sa.BigInteger, nullable=True),
        sa.Column("availability", sa.String(24), nullable=False),
        sa.Column("availability_text", sa.String(255), nullable=True),
        sa.Column("seller_name", sa.String(255), nullable=True),
        sa.Column("warnings", sa.JSON, nullable=True),
    )
    op.create_index("ix_product_observations_target_time", "product_observations", ["target_id", "collected_at"])
    op.create_index(
        "ix_product_observations_pid_time", "product_observations",
        ["marketplace", "platform_product_id", "collected_at"],
    )

    op.create_table(
        "scrape_source_states",
        sa.Column("marketplace", sa.String(32), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("unavailable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute(_PG_FUNCTION)
        op.execute(_PG_TRIGGER)
    elif dialect == "sqlite":
        op.execute(_SQLITE_TRIGGER)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    op.execute("DROP TRIGGER IF EXISTS product_observations_no_update" + (" ON product_observations" if dialect == "postgresql" else ""))
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS product_observations_append_only()")
    op.drop_table("scrape_source_states")
    op.drop_table("product_observations")
    op.drop_table("scrape_attempts")
    op.drop_table("scrape_targets")
