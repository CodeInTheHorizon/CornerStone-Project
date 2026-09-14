"""Add immutable dataset/artifact bundles; preserve all existing application rows."""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('stored_objects',
        sa.Column('namespace', sa.String(16), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('payload', sa.LargeBinary(), nullable=False),
        sa.Column('manifest', sa.JSON(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('namespace', 'key'),
    )


def downgrade():
    # Operator-requested downgrade discards bundles; back up before downgrading.
    op.drop_table('stored_objects')
