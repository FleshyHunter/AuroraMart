from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import joblib
import pandas as pd
from django.conf import settings

from ecommercemodule.models import Product

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "models" / "b2c_products_500_transactions_50k.joblib"

# Module-level cache for loaded rules
_loaded_rules = None


def _rules_path() -> Path:
    path = getattr(settings, "ML_ASSOC_RULES_PATH", None)
    if path:
        return Path(path)
    return DEFAULT_RULES_PATH


def _load_rules():
    global _loaded_rules
    if _loaded_rules is not None:
        return _loaded_rules
    
    try:
        rp = _rules_path()
        if rp.exists():
            _loaded_rules = joblib.load(rp)
        else:
            _loaded_rules = None
    except Exception:
        _loaded_rules = None
    
    return _loaded_rules


def get_recommendations(items, metric='confidence', top_n=5):
    """Use the loaded_rules to extract recommendations.

    items: list of SKU strings
    Returns: list of recommended SKU strings
    """
    loaded_rules = _load_rules()
    if loaded_rules is None or not isinstance(loaded_rules, pd.DataFrame):
        return []
    
    try:
        recommendations = set()

        for item in items:
            # Find rules where the item is in the antecedents
            matched_rules = loaded_rules[loaded_rules['antecedents'].apply(lambda x: item in x)]
            # Sort by the specified metric and get the top N
            top_rules = matched_rules.sort_values(by=metric, ascending=False).head(top_n)

            for _, row in top_rules.iterrows():
                recommendations.update(row['consequents'])

        # Remove items that are already in the input list
        recommendations.difference_update(items)
        
        return list(recommendations)[:top_n]
    
    except Exception:
        return []


def frequently_bought_together(product: Product, top_n: int = 4) -> List[Product]:
    """Get frequently bought together recommendations for a product."""
    skus = get_recommendations([product.sku], metric='lift', top_n=top_n)
    if not skus:
        return []
    return list(Product.objects.filter(sku__in=skus, is_active=True))


def cart_add_on_recommendations(cart_items: Sequence[Product], top_n: int = 4) -> List[Product]:
    """Get add-on recommendations based on current basket."""
    skus = [p.sku for p in cart_items]
    rec_skus = get_recommendations(skus, metric='confidence', top_n=top_n)
    if not rec_skus:
        return []
    # Exclude already in cart
    return list(Product.objects.filter(sku__in=rec_skus, is_active=True).exclude(sku__in=skus))
