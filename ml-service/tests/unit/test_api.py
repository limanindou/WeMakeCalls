"""Unit tests for the FastAPI application (entrypoints/api.py)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from entrypoints.api import ModelState, app


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200_with_status_ok(self, client):
        """GET /health returns HTTP 200 with {"status": "ok"}."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPredictEndpoint:
    """Tests for POST /predict."""

    def test_predict_returns_503_when_no_model_loaded(self, client):
        """POST /predict returns HTTP 503 when no model is loaded."""
        with patch("entrypoints.api.model_state") as mock_state:
            mock_state.is_loaded = False

            response = client.post(
                "/predict",
                json={
                    "calls_lag_1h": 10.0,
                    "calls_lag_2h": 12.0,
                    "calls_lag_24h": 8.0,
                    "calls_lag_168h": 9.0,
                    "hour_of_day": 14,
                    "day_of_week": 2,
                    "is_weekend": False,
                    "is_holiday": False,
                    "rolling_avg_7d": 11.5,
                    "avg_duration_lag_1h": 120.0,
                    "abandonment_rate_lag_1h": 0.05,
                },
            )

        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower() or "model" in response.json()["detail"].lower()

    def test_predict_returns_422_when_required_fields_missing(self, client):
        """POST /predict returns HTTP 422 when required fields are missing."""
        # Send a request body missing most of the 11 required fields
        incomplete_body = {
            "calls_lag_1h": 10.0,
            "calls_lag_2h": 12.0,
            # Missing: calls_lag_24h, calls_lag_168h, hour_of_day,
            # day_of_week, is_weekend, is_holiday, rolling_avg_7d,
            # avg_duration_lag_1h, abandonment_rate_lag_1h
        }

        response = client.post("/predict", json=incomplete_body)

        assert response.status_code == 422
        # Verify the response body references missing fields
        error_detail = response.json()["detail"]
        missing_fields = {err["loc"][-1] for err in error_detail}
        assert "calls_lag_24h" in missing_fields
        assert "calls_lag_168h" in missing_fields
        assert "hour_of_day" in missing_fields
        assert "day_of_week" in missing_fields
        assert "is_weekend" in missing_fields
        assert "is_holiday" in missing_fields
        assert "rolling_avg_7d" in missing_fields
        assert "avg_duration_lag_1h" in missing_fields
        assert "abandonment_rate_lag_1h" in missing_fields


class TestModelInfoEndpoint:
    """Tests for GET /model/info."""

    def test_model_info_returns_503_when_no_model_loaded(self, client):
        """GET /model/info returns HTTP 503 when no model is loaded."""
        with patch("entrypoints.api.model_state") as mock_state:
            mock_state.is_loaded = False

            response = client.get("/model/info")

        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower() or "model" in response.json()["detail"].lower()
