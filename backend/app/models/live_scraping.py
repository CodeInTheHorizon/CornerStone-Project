"""Tables for live product-page collection (app/live_scraping).

* `scrape_targets`      -- what to track, and when each product is next due.
                           Mutable scheduling state only; no observed values.
* `product_observations` -- one row per successful look at a product. Append-
                           only: the ORM refuses updates, and migration 0012
                           adds a database trigger that rejects UPDATE too.
* `scrape_listing_pages` -- search / best-seller pages to sweep; each fetch
                           yields many observations (migration 0013).
* `scrape_attempts`     -- every fetch, successful or not, with its outcome.
* `scrape_source_states` -- per-marketplace availability, so a block pauses
                           the whole marketplace until its cooldown ends.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow

#: SQLite only autoincrements INTEGER PRIMARY KEY; PostgreSQL gets a bigint.
_BigId = BigInteger().with_variant(Integer, "sqlite")


class ScrapeTarget(Base, TimestampMixin):
    __tablename__ = "scrape_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    #: Optional link to the canonical cross-platform product.
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("marketplace", "platform_product_id", name="uq_scrape_target_marketplace_pid"),
        Index("ix_scrape_targets_due", "marketplace", "is_active", "next_due_at"),
    )


class ScrapeListingPage(Base, TimestampMixin):
    __tablename__ = "scrape_listing_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    #: A ListingKind value: "search" or "bestsellers".
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Canonical page-1 URL.
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Register every product seen here as a scrape target (for product-page detail).
    auto_track: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Distinct products stored by the most recent successful sweep.
    last_items: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("marketplace", "url", name="uq_scrape_listing_marketplace_url"),
        Index("ix_scrape_listing_pages_due", "marketplace", "is_active", "next_due_at"),
    )


class ScrapeAttempt(Base):
    __tablename__ = "scrape_attempts"

    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scrape_targets.id"), nullable=True)
    #: Set instead of target_id when the fetch was a listing page.
    listing_page_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scrape_listing_pages.id"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Products parsed off a listing page.
    items_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: A ScrapeOutcome value.
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Sanitized reason. Never page bodies, headers or proxy credentials.
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_scrape_attempts_marketplace_started", "marketplace", "started_at"),
        Index("ix_scrape_attempts_target_started", "target_id", "started_at"),
    )


class ProductObservation(Base):
    __tablename__ = "product_observations"

    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("scrape_targets.id"), nullable=False)
    #: One product-page attempt stores one row; one listing-page attempt stores many.
    attempt_id: Mapped[int] = mapped_column(_BigId, ForeignKey("scrape_attempts.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    #: Set when the observation came from a listing page rather than the product page.
    listing_page_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scrape_listing_pages.id"), nullable=True)
    list_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sponsored: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    product_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(500), nullable=True)

    current_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    discount_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    review_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    availability: Mapped[str] = mapped_column(String(24), nullable=False)
    availability_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_product_observations_target_time", "target_id", "collected_at"),
        Index("ix_product_observations_pid_time", "marketplace", "platform_product_id", "collected_at"),
    )


class ScrapeSourceState(Base):
    __tablename__ = "scrape_source_states"

    marketplace: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: "available" or "unavailable".
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The ScrapeOutcome that made it unavailable.
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unavailable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ObservationImmutableError(RuntimeError):
    """Raised when code tries to change a stored observation."""


@event.listens_for(ProductObservation, "before_update")
def _refuse_update(mapper, connection, target) -> None:  # pragma: no cover - exercised in tests
    raise ObservationImmutableError(
        "product_observations is append-only; record a new observation instead of editing one."
    )
