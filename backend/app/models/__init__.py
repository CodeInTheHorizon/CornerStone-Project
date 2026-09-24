"""ORM models.

Importing this package registers every model on the shared declarative
Base metadata, which is what init_db() relies on.
"""

from app.models.enums import (
    AttemptOutcome,
    CollectorState,
    DataSource,
    IngestionMode,
    Platform,
    SourceType,
    TrainingStatus,
)
from app.models.alert import PriceAlert
from app.models.collection_attempt import CollectionAttempt
from app.models.marketplace_snapshot import MarketplaceSnapshot
from app.models.model_metadata import ModelMetadata
from app.models.opportunity_score import OpportunityScore
from app.models.platform_listing import PlatformListing
from app.models.prediction import Prediction
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.tracked_product import TrackedProduct
from app.models.user import User
from app.storage.database import StoredObject

__all__ = [
    "AttemptOutcome",
    "CollectionAttempt",
    "CollectorState",
    "PriceAlert",
    "DataSource",
    "IngestionMode",
    "MarketplaceSnapshot",
    "ModelMetadata",
    "OpportunityScore",
    "Platform",
    "PlatformListing",
    "Prediction",
    "PriceHistory",
    "Product",
    "SourceType",
    "TrackedProduct",
    "TrainingStatus",
    "User",
    "StoredObject",
]
