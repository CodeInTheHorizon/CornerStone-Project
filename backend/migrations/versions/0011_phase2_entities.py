"""Phase 2: products, platform_listings, price_history, tracked_products, opportunity_scores.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("canonical_title", sa.String(512), nullable=False),
        sa.Column("brand", sa.String(120), nullable=True, index=True),
        sa.Column("model_number", sa.String(120), nullable=True),
        sa.Column("category", sa.String(120), nullable=False, server_default="electronics"),
        sa.Column("subcategory", sa.String(120), nullable=True),
        sa.Column("primary_image_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_brand_category", "products", ["brand", "category"])

    op.create_table(
        "platform_listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("platform", sa.String(32), nullable=False, index=True),
        sa.Column("platform_product_id", sa.String(128), nullable=True),
        sa.Column("product_url", sa.Text, nullable=True),
        sa.Column("title_on_platform", sa.String(512), nullable=False),
        sa.Column("image_url", sa.Text, nullable=False),
        sa.Column("image_urls", sa.JSON, nullable=True),
        sa.Column("price_current", sa.Float, nullable=True),
        sa.Column("price_original", sa.Float, nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
        sa.Column("discount_pct", sa.Float, nullable=True),
        sa.Column("rating", sa.Float, nullable=True),
        sa.Column("review_count", sa.Integer, nullable=True),
        sa.Column("seller_name", sa.String(255), nullable=True),
        sa.Column("seller_count", sa.Integer, nullable=True),
        sa.Column("offer_count", sa.Integer, nullable=True),
        sa.Column("in_stock", sa.Boolean, nullable=True),
        sa.Column("min_order_qty", sa.Integer, nullable=True),
        sa.Column("price_min", sa.Float, nullable=True),
        sa.Column("price_max", sa.Float, nullable=True),
        sa.Column("match_confidence", sa.Float, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_stale", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "platform", name="uq_listing_product_platform"),
    )
    op.create_index("ix_listing_platform_pid", "platform_listings", ["platform", "platform_product_id"])

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("platform_listings.id"), nullable=False, index=True),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("discount_pct", sa.Float, nullable=True),
        sa.Column("rating", sa.Float, nullable=True),
        sa.Column("review_count", sa.Integer, nullable=True),
        sa.Column("seller_count", sa.Integer, nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index("ix_price_history_listing_time", "price_history", ["listing_id", "observed_at"])

    op.create_table(
        "tracked_products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("refresh_interval_minutes", sa.Integer, nullable=False, server_default=sa.text("360")),
        sa.UniqueConstraint("user_id", "product_id", name="uq_tracked_user_product"),
    )

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("components", sa.JSON, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("suggested_inventory_share_pct", sa.Float, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oppscore_product_platform", "opportunity_scores", ["product_id", "platform"])


def downgrade() -> None:
    op.drop_table("opportunity_scores")
    op.drop_table("tracked_products")
    op.drop_table("price_history")
    op.drop_table("platform_listings")
    op.drop_table("products")
