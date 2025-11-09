"""AuroraMart ML helpers.

This package provides light wrappers around persisted ML assets (joblib).
Place model files under `auroramart/ml/models/` or override paths via settings:
- ML_CLASSIFIER_PATH
- ML_ASSOC_RULES_PATH
"""
from __future__ import annotations

from .classifier import predict_preferred_category
from .recommender import (
    get_recommendations,
    frequently_bought_together,
    cart_add_on_recommendations
)
from .integration import predict_customer_preferred_category

__all__ = [
    'predict_preferred_category',
    'get_recommendations',
    'frequently_bought_together',
    'cart_add_on_recommendations',
    'predict_customer_preferred_category'
]
__version__ = "0.1.0"
