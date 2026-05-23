"""
Property-based tests for the FastAPI API Server.

Tests Properties 17, 18, and 19 from the design document using Hypothesis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sklearn.linear_model import LinearRegression

from wemakecalls.pipelines.inference.nodes import FEATURE_COLUMNS

# ---------------------------------------------------------------------------
# Module-level setup: create a trained model and mock ModelState
# ---------------------------------------------------------------------------

_TRAINED_MODEL: LinearRegression | None = None


def _get_trained_model() -> LinearRegression:
    """Return a pre-trained LinearRegression model (trained once at module level)."""
    global _TRAINED_MODEL
    if _TRAINED_MODEL is None:
        rng = np.random.default_rng(42)
        X_train = rng.uniform(0.0, 100.0, size=(200, len(FEATURE_COLUMNS)))
        y_train = rng.integers(0, 200, size=200).astype(float)
        model = LinearRegression()
        model.fit(X_train, y_train)
        _TRAINED_MODEL = model
    return _TRAINED_MODEL


def _get_test_client_with_model() -> TestClient:
    """Create a TestClient with a loaded model in model_state."""
    from entrypoints.api import app, model_state

    # Load a trained model into model_state
    model_state.model = _get_trained_model()
    model_state.model_type = "linear_regression"
    model_state.trained_at = "2024-06-15T12:00:00+00:00"
    model_state.mae = 5.2
    model_state.rmse = 7.8
    model_state.mape = 12.3

    return TestClient(app)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def valid_feature_vector_payload(draw: st.DrawFn) -> dict:
    """Generate a valid JSON payload with all 11 required feature fields."""
    payload = {}
    for col in FEATURE_COLUMNS:
        if col == "hour_of_day":
            payload[col] = draw(st.integers(min_value=0, max_value=23))
        elif col == "day_of_week":
            payload[col] = draw(st.integers(min_value=0, max_value=6))
        elif col in ("is_weekend", "is_holiday"):
            payload[col] = draw(st.booleans())
        elif col == "abandonment_rate_lag_1h":
            payload[col] = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        else:
            payload[col] = draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    return payload


@st.composite
def incomplete_feature_vector_payload(draw: st.DrawFn) -> tuple[dict, set[str]]:
    """Generate a payload missing one or more of the 11 required feature fields.

    Returns a tuple of (payload_dict, set_of_missing_field_names).
    """
    # Decide which fields to remove (at least 1, up to all 11)
    fields_to_remove = draw(
        st.sets(
            st.sampled_from(FEATURE_COLUMNS),
            min_size=1,
            max_size=len(FEATURE_COLUMNS),
        )
    )

    # Build a full payload first
    payload = {}
    for col in FEATURE_COLUMNS:
        if col == "hour_of_day":
            payload[col] = draw(st.integers(min_value=0, max_value=23))
        elif col == "day_of_week":
            payload[col] = draw(st.integers(min_value=0, max_value=6))
        elif col in ("is_weekend", "is_holiday"):
            payload[col] = draw(st.booleans())
        elif col == "abandonment_rate_lag_1h":
            payload[col] = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        else:
            payload[col] = draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))

    # Remove the selected fields
    for field in fields_to_remove:
        del payload[field]

    return payload, fields_to_remove


# ---------------------------------------------------------------------------
# Property 17: POST /predict response contract
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(payload=valid_feature_vector_payload())
def test_property_17_post_predict_response_contract(payload: dict) -> None:
    """
    Property 17: POST /predict response contract.

    For any valid FeatureVector submitted to POST /predict with a model loaded,
    the API returns HTTP 200 with predicted_calls (non-negative integer),
    target_hour (valid ISO 8601 UTC string), and model_type (non-empty string).

    **Validates: Requirements 6.2**
    """
    client = _get_test_client_with_model()

    response = client.post("/predict", json=payload)

    # HTTP 200
    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # predicted_calls is a non-negative integer
    assert "predicted_calls" in body, "Response missing 'predicted_calls'"
    assert isinstance(body["predicted_calls"], int), (
        f"predicted_calls is not int: {type(body['predicted_calls'])}"
    )
    assert body["predicted_calls"] >= 0, (
        f"predicted_calls is negative: {body['predicted_calls']}"
    )

    # target_hour is a valid ISO 8601 UTC string
    assert "target_hour" in body, "Response missing 'target_hour'"
    assert isinstance(body["target_hour"], str), (
        f"target_hour is not str: {type(body['target_hour'])}"
    )
    # Validate it parses as ISO 8601
    parsed_dt = datetime.fromisoformat(body["target_hour"])
    assert parsed_dt.tzinfo is not None or "+" in body["target_hour"] or "Z" in body["target_hour"], (
        f"target_hour is not UTC-aware: {body['target_hour']}"
    )

    # model_type is a non-empty string
    assert "model_type" in body, "Response missing 'model_type'"
    assert isinstance(body["model_type"], str), (
        f"model_type is not str: {type(body['model_type'])}"
    )
    assert len(body["model_type"]) > 0, "model_type is empty string"


# ---------------------------------------------------------------------------
# Property 18: POST /predict rejects incomplete requests
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=incomplete_feature_vector_payload())
def test_property_18_post_predict_rejects_incomplete_requests(
    data: tuple[dict, set[str]],
) -> None:
    """
    Property 18: POST /predict validation rejects incomplete requests.

    For any request body missing one or more of the 11 required feature fields,
    the API returns HTTP 422 and the response body names every missing field.

    **Validates: Requirements 6.3, 6.10**
    """
    payload, missing_fields = data
    client = _get_test_client_with_model()

    response = client.post("/predict", json=payload)

    # HTTP 422
    assert response.status_code == 422, (
        f"Expected HTTP 422, got {response.status_code}: {response.text}"
    )

    # Response body should name every missing field
    body = response.json()
    response_text = str(body).lower()

    for field in missing_fields:
        assert field in response_text, (
            f"Missing field '{field}' not named in 422 response body: {body}"
        )


# ---------------------------------------------------------------------------
# Property 19: GET /model/info response contract
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    model_type=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Nd", "Pc"))),
    mae=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    rmse=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    mape=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_property_19_get_model_info_response_contract(
    model_type: str, mae: float, rmse: float, mape: float
) -> None:
    """
    Property 19: GET /model/info response contract.

    For any loaded Model Artifact, GET /model/info returns HTTP 200 with all
    five required fields: model_type, trained_at, mae, rmse, mape.

    **Validates: Requirements 6.6**
    """
    from entrypoints.api import app, model_state

    # Set up model_state with the generated metadata
    model_state.model = _get_trained_model()
    model_state.model_type = model_type
    model_state.trained_at = "2024-06-15T12:00:00+00:00"
    model_state.mae = mae
    model_state.rmse = rmse
    model_state.mape = mape

    client = TestClient(app)
    response = client.get("/model/info")

    # HTTP 200
    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # All five required fields are present
    assert "model_type" in body, "Response missing 'model_type'"
    assert "trained_at" in body, "Response missing 'trained_at'"
    assert "mae" in body, "Response missing 'mae'"
    assert "rmse" in body, "Response missing 'rmse'"
    assert "mape" in body, "Response missing 'mape'"

    # model_type matches what was set
    assert body["model_type"] == model_type, (
        f"Expected model_type='{model_type}', got '{body['model_type']}'"
    )

    # trained_at is a non-empty string (ISO 8601)
    assert isinstance(body["trained_at"], str) and len(body["trained_at"]) > 0, (
        f"trained_at should be a non-empty string: {body['trained_at']}"
    )

    # mae, rmse, mape are floats (or ints that represent floats)
    assert isinstance(body["mae"], (int, float)), f"mae is not numeric: {type(body['mae'])}"
    assert isinstance(body["rmse"], (int, float)), f"rmse is not numeric: {type(body['rmse'])}"
    assert isinstance(body["mape"], (int, float)), f"mape is not numeric: {type(body['mape'])}"
