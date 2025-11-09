from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .classifier import predict_preferred_category as _predict_category

if TYPE_CHECKING:
    from ecommercemodule.models import Category, Customer


def predict_customer_preferred_category(customer: Customer) -> Optional[Category]:
    """Predict the preferred category for a Customer instance.
    
    Args:
        customer: Customer model instance
    
    Returns:
        Category instance or None if prediction fails or customer data is incomplete
    """
    from ecommercemodule.models import Category
    
    if not all([
        customer.age,
        customer.household_size is not None,
        customer.has_children is not None,
        customer.monthly_income_sgd,
        customer.gender,
        customer.employment_status,
        customer.occupation,
        customer.education
    ]):
        return None
    
    customer_data = {
        'age': customer.age,
        'household_size': customer.household_size,
        'has_children': customer.has_children,
        'monthly_income_sgd': float(customer.monthly_income_sgd),
        'gender': customer.gender,
        'employment_status': customer.employment_status,
        'occupation': customer.occupation,
        'education': customer.education
    }
    
    predicted_name = _predict_category(customer_data)
    if not predicted_name:
        return None
    
    try:
        return Category.objects.get(name=predicted_name)
    except Category.DoesNotExist:
        return None
