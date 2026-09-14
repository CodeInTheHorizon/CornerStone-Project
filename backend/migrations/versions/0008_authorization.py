"""Add safe account roles and session invalidation; preserve all existing rows.

Existing accounts become viewers. No account is automatically promoted.
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(24), nullable=False, server_default="viewer"))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")))

def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("users", "role")
