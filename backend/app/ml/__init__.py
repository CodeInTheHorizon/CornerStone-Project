"""Machine-learning pipeline.

Phase 5 built the dataset and features; Phase 6 adds the target, training
and evaluation. Prediction and the opportunity score arrive in Phase 7.
"""

from app.ml import dataset_builder, features, normalization, target, training

__all__ = [
    "dataset_builder",
    "features",
    "normalization",
    "target",
    "training",
]
