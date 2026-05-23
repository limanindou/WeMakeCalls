"""Model factory for the training pipeline.

Maps model_type strings to model classes and provides a factory function
for instantiating models by name.
"""

import logging

from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

logger = logging.getLogger(__name__)

SUPPORTED_MODELS: dict[str, type] = {
    "catboost": CatBoostRegressor,
    "xgboost": XGBRegressor,
    "lightgbm": LGBMRegressor,
    "random_forest": RandomForestRegressor,
    "linear_regression": LinearRegression,
}


def get_model(model_type: str, params: dict | None = None):
    """Return an instantiated model for the given model_type.

    If model_type is not in SUPPORTED_MODELS, logs a WARNING and falls back
    to CatBoost.

    For CatBoost, verbose=0 is set by default to suppress training output.

    Args:
        model_type: Key identifying the model class (e.g. "catboost", "xgboost").
        params: Optional dict of keyword arguments passed to the model constructor.

    Returns:
        An instantiated model object ready for fitting.
    """
    if params is None:
        params = {}

    if model_type not in SUPPORTED_MODELS:
        supported = ", ".join(sorted(SUPPORTED_MODELS.keys()))
        logger.warning(
            "Unsupported model_type '%s'. Supported types: %s. "
            "Falling back to 'catboost'.",
            model_type,
            supported,
        )
        model_type = "catboost"

    model_class = SUPPORTED_MODELS[model_type]

    # Suppress CatBoost training output by default
    if model_type == "catboost":
        params = {"verbose": 0, **params}

    return model_class(**params)
