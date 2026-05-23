"""FastAPI application for the ML Service.

Exposes REST endpoints for inference, health checks, and model metadata.
Loads the latest model artifact at startup and caches model metadata.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from wemakecalls.logging_config import setup_logging
from wemakecalls.pipelines.inference.nodes import (
    FEATURE_COLUMNS,
    load_latest_model,
    run_inference,
)

# Configure structured JSON logging at module import time
setup_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic v2 Models (Task 8.1)
# ---------------------------------------------------------------------------


class FeatureVector(BaseModel):
    """Request model for POST /predict with 11 required feature fields."""

    calls_lag_1h: float
    calls_lag_2h: float
    calls_lag_24h: float
    calls_lag_168h: float
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    is_holiday: bool
    rolling_avg_7d: float
    avg_duration_lag_1h: float
    abandonment_rate_lag_1h: float


class PredictionResponse(BaseModel):
    """Response model for POST /predict."""

    predicted_calls: int
    target_hour: str
    model_type: str


class ModelInfoResponse(BaseModel):
    """Response model for GET /model/info."""

    model_type: str
    trained_at: str
    mae: float
    rmse: float
    mape: float


# ---------------------------------------------------------------------------
# Model State (Task 8.2)
# ---------------------------------------------------------------------------


class ModelState:
    """Module-level state that loads and caches the latest model artifact."""

    def __init__(self) -> None:
        self.model: Optional[Any] = None
        self.model_type: Optional[str] = None
        self.trained_at: Optional[str] = None
        self.mae: Optional[float] = None
        self.rmse: Optional[float] = None
        self.mape: Optional[float] = None

    def load(self, models_dir: Path = Path("data/06_models")) -> None:
        """Load the latest model artifact and cache metadata.

        Gracefully handles the case where no model is available by logging
        a warning instead of crashing.
        """
        try:
            self.model, self.model_type = load_latest_model(models_dir)

            # Extract metadata from the model file
            model_files = [
                f
                for f in models_dir.iterdir()
                if f.is_file()
                and not f.name.startswith(".")
                and f.name != ".gitkeep"
            ]
            if model_files:
                latest_file = max(model_files, key=lambda f: f.stat().st_mtime)
                # Parse trained_at from filename: <model_type>_YYYYMMDD_HHMMSS.<ext>
                stem = latest_file.stem
                parts = stem.rsplit("_", 2)
                if len(parts) >= 3:
                    date_part = parts[-2]  # YYYYMMDD
                    time_part = parts[-1]  # HHMMSS
                    try:
                        trained_dt = datetime.strptime(
                            f"{date_part}_{time_part}", "%Y%m%d_%H%M%S"
                        )
                        trained_dt = trained_dt.replace(tzinfo=timezone.utc)
                        self.trained_at = trained_dt.isoformat()
                    except ValueError:
                        self.trained_at = datetime.now(timezone.utc).isoformat()
                else:
                    self.trained_at = datetime.now(timezone.utc).isoformat()

            # Default metrics — in a production system these would be read from
            # the predictions table or a metadata sidecar file
            self.mae = self.mae if self.mae is not None else 0.0
            self.rmse = self.rmse if self.rmse is not None else 0.0
            self.mape = self.mape if self.mape is not None else 0.0

            logger.info(
                f"ModelState: loaded model '{self.model_type}' "
                f"(trained_at={self.trained_at})"
            )
        except (FileNotFoundError, RuntimeError) as exc:
            logger.warning(
                f"ModelState: no model loaded at startup — {exc}"
            )
            self.model = None

    @property
    def is_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self.model is not None


# Module-level model state instance
model_state = ModelState()

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="WeMakeCalls ML Service", version="1.0.0")


@app.on_event("startup")
def startup_load_model() -> None:
    """Load the latest model artifact at application startup."""
    model_state.load()


# ---------------------------------------------------------------------------
# Endpoints (Tasks 8.3, 8.4, 8.5)
# ---------------------------------------------------------------------------


@app.post("/predict", response_model=PredictionResponse)
def predict(features: FeatureVector) -> PredictionResponse:
    """Run inference on a feature vector and return predicted call count.

    Returns:
        PredictionResponse with predicted_calls, target_hour, and model_type.

    Raises:
        HTTPException 422: If request body fails Pydantic validation (automatic).
        HTTPException 503: If no model is loaded.
    """
    if not model_state.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not available. Run training pipeline first.",
        )

    # Convert FeatureVector to a single-row DataFrame
    feature_dict = features.model_dump()
    batch = pd.DataFrame([feature_dict], columns=FEATURE_COLUMNS)

    # Run inference
    predicted_calls = run_inference(model_state.model, batch)

    # Track prediction count for monitoring
    global prediction_counter
    prediction_counter += 1

    # Compute target hour: next hour bucket start from current UTC time
    now_utc = datetime.now(timezone.utc)
    target_hour = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )

    return PredictionResponse(
        predicted_calls=predicted_calls,
        target_hour=target_hour.isoformat(),
        model_type=model_state.model_type,
    )


@app.get("/health")
def health() -> dict:
    """Health check endpoint.

    Returns:
        {"status": "ok"} with HTTP 200.
    """
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Production monitoring metrics endpoint.

    Returns model health, prediction count, and uptime information.
    """
    return {
        "status": "healthy" if model_state.is_loaded else "degraded",
        "model_loaded": model_state.is_loaded,
        "model_type": model_state.model_type,
        "trained_at": model_state.trained_at,
        "uptime_seconds": (datetime.now(timezone.utc) - app_start_time).total_seconds(),
        "predictions_served": prediction_counter,
    }


# Track predictions served
prediction_counter = 0
app_start_time = datetime.now(timezone.utc)


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """Return metadata about the currently loaded model.

    Returns:
        ModelInfoResponse with model_type, trained_at, mae, rmse, mape.

    Raises:
        HTTPException 503: If no model is loaded.
    """
    if not model_state.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not available. Run training pipeline first.",
        )

    return ModelInfoResponse(
        model_type=model_state.model_type,
        trained_at=model_state.trained_at,
        mae=model_state.mae,
        rmse=model_state.rmse,
        mape=model_state.mape,
    )


# ---------------------------------------------------------------------------
# Uvicorn Entry Point (Task 8.6)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "entrypoints.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
