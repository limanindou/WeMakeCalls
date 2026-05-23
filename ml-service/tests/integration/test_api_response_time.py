"""Integration test: API response time.

Verifies that POST /predict and GET /model/info respond within 2 seconds
each under normal operating conditions (Requirement 6.9).

Uses FastAPI TestClient (in-process, no actual server needed).
"""

import time
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.integration

MODELS_DIR = Path("data/06_models")


def _has_model_artifact() -> bool:
    """Check if at least one model artifact exists in the models directory."""
    if not MODELS_DIR.exists():
        return False
    return any(
        f.is_file() and not f.name.startswith(".") and f.name != ".gitkeep"
        for f in MODELS_DIR.iterdir()
    )


_has_model = _has_model_artifact()


@pytest.fixture()
def client():
    """Create a FastAPI TestClient with a model loaded (real or mocked)."""
    from fastapi.testclient import TestClient

    from entrypoints.api import app, model_state

    if _has_model:
        # Load the real model
        model_state.load()
    else:
        # Mock a simple model so the endpoints don't return 503
        class _MockModel:
            def predict(self, X):
                return np.array([42.0])

        model_state.model = _MockModel()
        model_state.model_type = "mock_model"
        model_state.trained_at = "2024-01-01T00:00:00+00:00"
        model_state.mae = 1.5
        model_state.rmse = 2.0
        model_state.mape = 0.05

    yield TestClient(app)

    # Reset model state after test
    model_state.model = None
    model_state.model_type = None


def test_post_predict_response_within_2_seconds(client):
    """POST /predict should respond within 2 seconds."""
    payload = {
        "calls_lag_1h": 10.0,
        "calls_lag_2h": 12.0,
        "calls_lag_24h": 8.0,
        "calls_lag_168h": 9.0,
        "hour_of_day": 14,
        "day_of_week": 2,
        "is_weekend": False,
        "is_holiday": False,
        "rolling_avg_7d": 11.0,
        "avg_duration_lag_1h": 180.0,
        "abandonment_rate_lag_1h": 0.1,
    }

    start = time.time()
    response = client.post("/predict", json=payload)
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 2, (
        f"POST /predict took {elapsed:.2f}s, exceeding the 2s threshold"
    )

    # Verify response structure
    data = response.json()
    assert "predicted_calls" in data
    assert "target_hour" in data
    assert "model_type" in data


def test_get_model_info_response_within_2_seconds(client):
    """GET /model/info should respond within 2 seconds."""
    start = time.time()
    response = client.get("/model/info")
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 2, (
        f"GET /model/info took {elapsed:.2f}s, exceeding the 2s threshold"
    )

    # Verify response structure
    data = response.json()
    assert "model_type" in data
    assert "trained_at" in data
    assert "mae" in data
    assert "rmse" in data
    assert "mape" in data
