from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import pandas as pd
from django.conf import settings

if TYPE_CHECKING:
    from ecommercemodule.models import Category, Customer

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "b2c_customers_100.joblib"

_loaded_model = None


def _model_path() -> Path:
    path = getattr(settings, "ML_CLASSIFIER_MODEL_PATH", None)
    if path:
        return Path(path)
    return DEFAULT_MODEL_PATH


def _load_model():
    global _loaded_model
    if _loaded_model is not None:
        return _loaded_model
    
    try:
        mp = _model_path()
        if mp.exists():
            _loaded_model = joblib.load(mp)
        else:
            _loaded_model = None
    except Exception:
        _loaded_model = None
    
    return _loaded_model

model = _load_model()

def predict_preferred_category(customer_data):
    """Predict the preferred category for a customer.
    
    Args:
        customer_data: dict with keys: age, household_size, has_children, monthly_income_sgd,
                      gender, employment_status, occupation, education
    
    Returns:
        Predicted category string or None if prediction fails
    """
    
    if model is None:
        return None
    
    try:
        # Convert has_children to int if it's boolean
        if isinstance(customer_data.get('has_children'), bool):
            customer_data['has_children'] = 1 if customer_data['has_children'] else 0
        
        # Convert raw input to DataFrame
        input_df = pd.DataFrame([customer_data])
        
        # One-hot encode categorical variables to match training data columns
        input_encoded = pd.get_dummies(input_df, columns=['gender', 'employment_status', 'occupation', 'education'])
        
        # Get the feature names from the model (these are the columns used during training)
        model_features = model.feature_names_in_
        
        # Ensure all required columns are present, add missing columns as False/0
        for col in model_features:
            if col not in input_encoded.columns:
                input_encoded[col] = 0
        
        # Reorder columns to match training data
        input_encoded = input_encoded[model_features]
        
        # Now input_encoded can be used for prediction
        prediction = model.predict(input_encoded)
        return prediction[0] if len(prediction) > 0 else None
    
    except Exception:
        return None


def predict_customer_preferred_category(customer):
    """Predict the preferred category for a Customer instance.
    
    Args:
        customer: Customer model instance
    
    Returns:
        Category instance or None if prediction fails or customer data is incomplete
    """
    from auroramart.models import Category
    
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
    
    predicted_name = predict_preferred_category(customer_data)
    if not predicted_name:
        return None
    
    try:
        return Category.objects.get(name=predicted_name)
    except Category.DoesNotExist:
        return None
