"""One outbound LIVE fetch against a marketplace provider, successful or not.

This is the provenance log for LIVE data: every stored LIVE snapshot points at
its attempt through `collection_run_id`, which records which provider was
called, when, with what query and how it ended. Failed attempts are kept too,
so the status API can report the last failure and honour a provider's
rate-limit cooldown.

Never store credentials, request headers or raw provider bodies here.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow


class CollectionAttempt(Base):
    __tablename__ = "collection_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Stable provider/API identifier, e.g. "flipkart-affiliate-api-1.0".
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Always "live": only outbound marketplace fetches are logged here.
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    #: Matches MarketplaceSnapshot.collection_run_id for the rows this attempt stored.
    collection_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)

    search_query: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: success | empty | rate_limited | credentials_rejected | provider_error
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Machine-readable failure detail, e.g. "timeout", "http_503", "malformed_response".
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Sanitized, human-readable failure message. Never contains secrets.
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Earliest time the provider allows another request, after a 429.
    retry_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_stored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_collection_attempts_platform_started", "platform", "started_at"),
    )
