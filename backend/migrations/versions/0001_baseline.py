"""Baseline schema as of Phase 3.

Represents the tables that create_all() produced before migrations existed.
An existing pre-Alembic database is stamped at this revision rather than
having it re-run, so no data is lost.

Revision ID: 0001
Revises:
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "marketplace_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("search_query", sa.String(length=255), nullable=True),
        sa.Column("product_name", sa.String(length=512), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("subcategory", sa.String(length=120), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("original_price", sa.Float(), nullable=True),
        sa.Column("discount_percentage", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("availability", sa.String(length=64), nullable=True),
        sa.Column("seller_name", sa.String(length=255), nullable=True),
        sa.Column("listing_url", sa.Text(), nullable=True),
        sa.Column("collection_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_snapshots_platform", "marketplace_snapshots", ["platform"])
    op.create_index("ix_marketplace_snapshots_source", "marketplace_snapshots", ["source"])
    op.create_index("ix_marketplace_snapshots_brand", "marketplace_snapshots", ["brand"])
    op.create_index("ix_marketplace_snapshots_category", "marketplace_snapshots", ["category"])
    op.create_index("ix_marketplace_snapshots_external_id", "marketplace_snapshots", ["external_id"])
    op.create_index("ix_marketplace_snapshots_collection_timestamp", "marketplace_snapshots", ["collection_timestamp"])
    op.create_index("ix_snapshot_platform_collected", "marketplace_snapshots", ["platform", "collection_timestamp"])
    op.create_index("ix_snapshot_platform_external_id", "marketplace_snapshots", ["platform", "external_id"])

    op.create_table(
        "model_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("dataset_rows", sa.Integer(), nullable=True),
        sa.Column("feature_names", sa.JSON(), nullable=True),
        sa.Column("hyperparameters", sa.JSON(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_metadata_model_name", "model_metadata", ["model_name"])
    op.create_index("ix_model_metadata_model_version", "model_metadata", ["model_version"])
    op.create_index("ix_model_metadata_status", "model_metadata", ["status"])
    op.create_index("ix_model_metadata_is_active", "model_metadata", ["is_active"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_metadata_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=512), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("target_platform", sa.String(length=32), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("recommended_platform", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("opportunity_scores", sa.JSON(), nullable=True),
        sa.Column("key_factors", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("snapshots_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["model_metadata_id"], ["model_metadata.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"])
    op.create_index("ix_predictions_model_metadata_id", "predictions", ["model_metadata_id"])
    op.create_index("ix_predictions_category", "predictions", ["category"])
    op.create_index("ix_predictions_recommended_platform", "predictions", ["recommended_platform"])


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("model_metadata")
    op.drop_table("marketplace_snapshots")
    op.drop_table("users")
