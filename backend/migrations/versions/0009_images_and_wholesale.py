"""Add image_url, image_urls, competition fields and Alibaba wholesale fields
to marketplace_snapshots; add business_type to users.
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketplace_snapshots", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("image_urls", sa.JSON(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("seller_count", sa.Integer(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("offer_count", sa.Integer(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("min_order_qty", sa.Integer(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("price_min", sa.Float(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("price_max", sa.Float(), nullable=True))
    op.add_column("marketplace_snapshots", sa.Column("supplier_years", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("business_type", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("marketplace_snapshots", "supplier_years")
    op.drop_column("marketplace_snapshots", "price_max")
    op.drop_column("marketplace_snapshots", "price_min")
    op.drop_column("marketplace_snapshots", "min_order_qty")
    op.drop_column("marketplace_snapshots", "offer_count")
    op.drop_column("marketplace_snapshots", "seller_count")
    op.drop_column("marketplace_snapshots", "image_urls")
    op.drop_column("marketplace_snapshots", "image_url")
    op.drop_column("users", "business_type")
