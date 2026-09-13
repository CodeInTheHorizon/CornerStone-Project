"""Preserve complete Phase 7 prediction results without changing existing rows."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("result_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("predictions") as batch:
        batch.drop_column("result_payload")
