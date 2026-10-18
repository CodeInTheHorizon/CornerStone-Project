"""Add variant & specifications to products, and mrp, rating_count, availability to price_history.

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    product_cols: list[str] = []
    history_cols: list[str] = []
    try:
        insp = sa.inspect(bind)
        product_cols = [c["name"] for c in insp.get_columns("products")]
        history_cols = [c["name"] for c in insp.get_columns("price_history")]
    except Exception:
        pass

    with op.batch_alter_table("products") as batch_op:
        if "variant" not in product_cols:
            batch_op.add_column(sa.Column("variant", sa.String(120), nullable=True))
        if "specifications" not in product_cols:
            batch_op.add_column(sa.Column("specifications", sa.JSON, nullable=True))

    with op.batch_alter_table("price_history") as batch_op:
        if "mrp" not in history_cols:
            batch_op.add_column(sa.Column("mrp", sa.Float, nullable=True))
        if "rating_count" not in history_cols:
            batch_op.add_column(sa.Column("rating_count", sa.Integer, nullable=True))
        if "availability" not in history_cols:
            batch_op.add_column(sa.Column("availability", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("price_history") as batch_op:
        batch_op.drop_column("availability")
        batch_op.drop_column("rating_count")
        batch_op.drop_column("mrp")

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("specifications")
        batch_op.drop_column("variant")
