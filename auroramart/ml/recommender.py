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

loaded_rules = _load_rules()

def get_recommendations(loaded_rules, items, metric='confidence', top_n=5):
    """Use the loaded_rules to extract recommendations.

    items: list of SKU strings
    Returns: list of recommended SKU strings
    """
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
def frequently_bought_together(product: Product, top_n: int = 4) -> List[Product]:
    """Get frequently bought together recommendations for a product.
    
    Returns only ML-based association rule recommendations.
    Returns empty list if product has no association rules.
    """
    skus = get_recommendations(loaded_rules, [product.sku], metric='lift', top_n=top_n)
    if not skus:
        return []
    return list(Product.objects.filter(sku__in=skus, is_active=True))


def cart_add_on_recommendations(cart_items: Sequence[Product], top_n: int = 4) -> List[Product]:
    """Get add-on recommendations based on current basket.
    
    Returns only ML-based association rule recommendations.
    Returns empty list if cart items have no association rules.
    """
    skus = [p.sku for p in cart_items]
    rec_skus = get_recommendations(loaded_rules, skus, metric='confidence', top_n=top_n)
    if not rec_skus:
        return []
    # Exclude already in cart
    return list(Product.objects.filter(sku__in=rec_skus, is_active=True).exclude(sku__in=skus))


def category_exploration_recommendations(category_slug: str, top_n: int = 4) -> List[Product]:
    """Get category-based exploration recommendations using association rules.
    
    Uses ML-based association rules to suggest products from the same category
    but different subcategories, encouraging exploration within the category.
    Returns empty list if no ML-based recommendations found.
    
    Args:
        category_slug: The category slug to get recommendations for
        top_n: Number of recommendations to return
    
    Returns:
        List of recommended Product objects from same category, different subcategories,
        or empty list if no association rules apply
    """
    from auroramart.models import Category, Product as ProductModel
    
    try:
        category = Category.objects.get(slug=category_slug)
        # Get some popular products from this category as seed
        seed_products = list(
            ProductModel.objects.filter(
                category=category,
                is_active=True,
                quantity_on_hand__gt=0
            ).order_by('-rating', '-quantity_on_hand')[:3]
        )
        
        if not seed_products:
            return []
        
        seed_skus = [p.sku for p in seed_products]
        seed_subcategories = {p.subcategory_id for p in seed_products if p.subcategory_id}
        
        rec_skus = get_recommendations(loaded_rules, seed_skus, metric='lift', top_n=top_n * 3)
        
        if not rec_skus:
            return []
        
        # Get recommended products from association rules
        # Filter: same category, different subcategory, exclude seed products
        recommendations = list(
            ProductModel.objects.filter(
                sku__in=rec_skus,
                category=category,
                is_active=True,
                quantity_on_hand__gt=0
            ).exclude(
                sku__in=seed_skus
            ).exclude(
                subcategory_id__in=seed_subcategories
            )[:top_n]
        )
        return recommendations
    except Exception:
        return []
