"""ORM models.

Importing this package registers every model on the shared declarative
Base metadata, which is what init_db() relies on.
"""

from app.models.enums import (
    DataSource,
    IngestionMode,
    Platform,
    SourceType,
    TrainingStatus,
)
from app.models.marketplace_snapshot import MarketplaceSnapshot
from app.models.model_metadata import ModelMetadata
from app.models.prediction import Prediction
from app.models.user import User
from app.storage.database import StoredObject

__all__ = [
    "DataSource",
    "IngestionMode",
    "MarketplaceSnapshot",
    "ModelMetadata",
    "Platform",
    "Prediction",
    "SourceType",
    "TrainingStatus",
    "User",
    "StoredObject",
]
