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


def predict_preferred_category(customer_data):
    """Predict the preferred category for a customer.
    
    Args:
        customer_data: dict with keys: age, household_size, has_children, monthly_income_sgd,
                      gender, employment_status, occupation, education
    
    Returns:
        Predicted category string or None if prediction fails
    """
    model = _load_model()
    if model is None:
        return None
    
    try:
        columns = {
            'age':'int64', 'household_size':'int64', 'has_children':'int64', 'monthly_income_sgd':'float64',
            'gender_Female':'bool', 'gender_Male':'bool', 'employment_status_Full-time':'bool',
            'employment_status_Part-time':'bool', 'employment_status_Retired':'bool',
            'employment_status_Self-employed':'bool', 'employment_status_Student':'bool',
            'occupation_Admin':'bool', 'occupation_Education':'bool', 'occupation_Sales':'bool',
            'occupation_Service':'bool', 'occupation_Skilled Trades':'bool', 'occupation_Tech':'bool',
            'education_Bachelor':'bool', 'education_Diploma':'bool', 'education_Doctorate':'bool',
            'education_Master':'bool', 'education_Secondary':'bool'
        }

        df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in columns.items()})
        customer_df = pd.DataFrame([customer_data])
        customer_encoded = pd.get_dummies(customer_df, columns=['gender', 'employment_status', 'occupation', 'education'])    

        for col in df.columns:
            if col not in customer_encoded.columns:
                if df[col].dtype == bool:
                    df[col] = False
                else:
                    df[col] = 0
            else:
                df[col] = customer_encoded[col]
        
        prediction = model.predict(df)    
        return prediction[0] if len(prediction) > 0 else None
    
    except Exception:
        return None
