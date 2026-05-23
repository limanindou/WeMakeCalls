"""
Property-based tests for the Model Factory.

Tests Property 20 from the design document using Hypothesis.
"""

from __future__ import annotations

from catboost import CatBoostRegressor
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from wemakecalls.pipelines.training.model_factory import SUPPORTED_MODELS, get_model

# ---------------------------------------------------------------------------
# Expected type mapping for validation
# ---------------------------------------------------------------------------

_EXPECTED_TYPES: dict[str, type] = {
    "catboost": CatBoostRegressor,
    "xgboost": XGBRegressor,
    "lightgbm": LGBMRegressor,
    "random_forest": RandomForestRegressor,
    "linear_regression": LinearRegression,
}


# ---------------------------------------------------------------------------
# Property 20: model_type parameter drives model selection
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    model_type=st.sampled_from(["catboost", "xgboost", "lightgbm", "random_forest", "linear_regression"])
)
def test_property_20_model_type_drives_model_selection(model_type: str) -> None:
    """
    Property 20: model_type parameter drives model selection.

    For any supported model_type value (catboost, xgboost, lightgbm,
    random_forest, linear_regression), get_model instantiates a model of
    exactly that type without requiring source code changes.

    **Validates: Requirements 7.3**
    """
    model = get_model(model_type, params={})

    expected_type = _EXPECTED_TYPES[model_type]

    # The returned model is an instance of the expected class
    assert isinstance(model, expected_type), (
        f"For model_type='{model_type}', expected instance of "
        f"{expected_type.__name__}, got {type(model).__name__}"
    )

    # The model_type is in the SUPPORTED_MODELS registry
    assert model_type in SUPPORTED_MODELS, (
        f"model_type '{model_type}' not found in SUPPORTED_MODELS"
    )

    # The model has a fit method (can be trained)
    assert hasattr(model, "fit"), (
        f"Model of type '{model_type}' does not have a 'fit' method"
    )

    # The model has a predict method (can run inference)
    assert hasattr(model, "predict"), (
        f"Model of type '{model_type}' does not have a 'predict' method"
    )
