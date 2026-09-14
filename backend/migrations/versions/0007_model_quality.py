"""Record the Phase 12 model quality gate and calibration status.

Additive only: two nullable columns. Existing model records (including the
pre-Phase 12 development models) keep NULL and are interpreted on read.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_metadata") as batch:
        batch.add_column(sa.Column("quality_status", sa.String(24), nullable=True))
        batch.add_column(sa.Column("calibration_status", sa.String(32), nullable=True))
        batch.create_index("ix_model_metadata_quality_status", ["quality_status"])


def downgrade() -> None:
    with op.batch_alter_table("model_metadata") as batch:
        batch.drop_index("ix_model_metadata_quality_status")
        batch.drop_column("calibration_status")
        batch.drop_column("quality_status")
