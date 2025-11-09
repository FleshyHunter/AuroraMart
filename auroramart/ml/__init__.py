"""AuroraMart ML helpers.

This package provides light wrappers around persisted ML assets (joblib).
Place model files under `auroramart/ml/models/` or override paths via settings:
- ML_CLASSIFIER_PATH
- ML_ASSOC_RULES_PATH
"""
from __future__ import annotations

# Graceful import of ML helpers: if optional deps (joblib, sklearn) missing,
# provide lightweight stubs so the rest of the site still works.
try:  # pragma: no cover - optional path
    from .classifier import predict_preferred_category
except Exception:  # ModuleNotFoundError, ImportError, etc.
    def predict_preferred_category(*args, **kwargs):  # type: ignore[override]
        return None

try:  # pragma: no cover
    from .recommender import (
        get_recommendations,
        frequently_bought_together,
        cart_add_on_recommendations
    )
except Exception:
    def get_recommendations(*args, **kwargs):  # type: ignore[override]
        return []
    def frequently_bought_together(*args, **kwargs):  # type: ignore[override]
        return []
    def cart_add_on_recommendations(*args, **kwargs):  # type: ignore[override]
        return []

try:  # pragma: no cover
    from .integration import predict_customer_preferred_category
except Exception:
    def predict_customer_preferred_category(*args, **kwargs):  # type: ignore[override]
        return None

__all__ = [
    'predict_preferred_category',
    'get_recommendations',
    'frequently_bought_together',
    'cart_add_on_recommendations',
    'predict_customer_preferred_category'
]
__version__ = "0.1.0"
