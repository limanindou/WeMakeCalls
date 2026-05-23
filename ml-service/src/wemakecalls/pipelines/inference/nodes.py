"""Inference pipeline node functions.

Pure functions for loading trained models, building prediction batches,
running inference, and persisting predictions to PostgreSQL.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# The 11 feature columns expected by the model
FEATURE_COLUMNS = [
    "calls_lag_1h",
    "calls_lag_2h",
    "calls_lag_24h",
    "calls_lag_168h",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "rolling_avg_7d",
    "avg_duration_lag_1h",
    "abandonment_rate_lag_1h",
]


def load_latest_model(models_dir: Path) -> tuple[Any, str]:
    """Load the most recently modified model artifact from the models directory.

    Finds the most recently modified file in the given directory by filesystem
    mtime. Determines model type from the filename (e.g., 'catboost_20240101_120000.cbm'
    yields 'catboost'). CatBoost models (.cbm) are loaded via CatBoostRegressor().load_model(),
    all others via joblib.

    After loading, performs a test prediction with an all-zero synthetic feature
    vector (11 features) to validate the artifact is not corrupted.

    Args:
        models_dir: Path to the directory containing model artifacts.

    Returns:
        Tuple of (model, model_type_str) where model is the loaded model object
        and model_type_str is the model type extracted from the filename.

    Raises:
        FileNotFoundError: If the models directory is empty (no model files).
        RuntimeError: If the loaded model fails the test prediction (corrupted artifact).
    """
    models_dir = Path(models_dir)

    # Find all model files (exclude .gitkeep and hidden files)
    model_files = [
        f for f in models_dir.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name != ".gitkeep"
    ]

    if not model_files:
        raise FileNotFoundError(
            f"No model artifacts found in '{models_dir}'. "
            "Please run the training pipeline first: "
            "kedro run --pipeline=training"
        )

    # Select the most recently modified file
    latest_file = max(model_files, key=lambda f: f.stat().st_mtime)

    # Determine model type from filename (first part before the timestamp)
    # e.g., "catboost_20240101_120000.cbm" -> "catboost"
    # e.g., "random_forest_20240101_120000.pkl" -> "random_forest"
    stem = latest_file.stem  # e.g., "catboost_20240101_120000"
    # The timestamp is always in format _YYYYMMDD_HHMMSS at the end
    # Split from the right to handle model types with underscores (e.g., random_forest)
    parts = stem.rsplit("_", 2)
    if len(parts) >= 3:
        model_type = "_".join(parts[:-2])
    else:
        model_type = parts[0]

    # Load the model based on extension
    if latest_file.suffix == ".cbm":
        model = CatBoostRegressor()
        model.load_model(str(latest_file))
    else:
        model = joblib.load(latest_file)

    # Perform test prediction with all-zero synthetic feature vector
    test_vector = pd.DataFrame(
        [[0] * len(FEATURE_COLUMNS)],
        columns=FEATURE_COLUMNS,
    )
    try:
        model.predict(test_vector)
    except Exception as exc:
        raise RuntimeError(
            f"Model artifact '{latest_file}' appears to be corrupted. "
            f"Test prediction with synthetic data failed: {exc}"
        ) from exc

    logger.info(
        f"load_latest_model: loaded '{latest_file.name}' "
        f"(type={model_type}, mtime={latest_file.stat().st_mtime})"
    )

    return model, model_type


def build_prediction_batch(features: pd.DataFrame) -> pd.DataFrame:
    """Select the single most recent row from the feature DataFrame.

    Selects the row with the most recent `hour_bucket` timestamp, fills any
    null values with 0, and returns a single-row DataFrame containing only
    the 11 feature columns.

    Args:
        features: DataFrame containing feature vectors with an `hour_bucket`
            column (datetime) and the 11 feature columns.

    Returns:
        Single-row DataFrame with the 11 feature columns, nulls filled with 0.

    Raises:
        FileNotFoundError: If the features DataFrame is empty.
    """
    if features.empty:
        raise FileNotFoundError(
            "Feature vector DataFrame is empty. "
            "Please run the feature engineering pipeline first: "
            "kedro run --pipeline=feature_engineering"
        )

    # Select the most recent row by hour_bucket
    most_recent_idx = features["hour_bucket"].idxmax()
    batch = features.loc[[most_recent_idx]].copy()

    # Fill null values with 0
    batch = batch.fillna(0)

    # Select only the feature columns for prediction
    batch = batch[FEATURE_COLUMNS].reset_index(drop=True)

    logger.info(
        f"build_prediction_batch: selected most recent row "
        f"(hour_bucket={features.loc[most_recent_idx, 'hour_bucket']})"
    )

    return batch


def run_inference(model: Any, batch: pd.DataFrame) -> int:
    """Run model prediction on the batch and return a non-negative integer.

    Calls model.predict(batch), clips the result to non-negative values,
    and returns the prediction as an integer.

    Args:
        model: A fitted model with a `predict` method.
        batch: Single-row DataFrame with the 11 feature columns.

    Returns:
        Non-negative integer predicted call count.
    """
    prediction = model.predict(batch)

    # Extract scalar value from prediction array
    predicted_value = float(prediction[0]) if hasattr(prediction, "__len__") else float(prediction)

    # Clip to non-negative and convert to integer
    predicted_calls = int(max(0, round(predicted_value)))

    logger.info(f"run_inference: predicted {predicted_calls} calls")

    return predicted_calls


def persist_prediction(
    prediction: int,
    model_type: str,
    engine: Engine,
) -> None:
    """Insert a prediction row into the PostgreSQL predictions table.

    Inserts a row with:
    - predicted_at: current UTC timestamp
    - target_hour: start of the next hour from current UTC time (ISO 8601)
    - predicted_calls: the predicted integer
    - model_type: name of the model used

    Args:
        prediction: Non-negative integer predicted call count.
        model_type: String identifying the model type (e.g., "catboost").
        engine: SQLAlchemy Engine connected to the PostgreSQL database.

    Raises:
        Exception: Re-raises any database insert error after logging.
    """
    now_utc = datetime.now(timezone.utc)

    # Compute next hour bucket start: truncate to current hour, then add 1 hour
    target_hour = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO predictions (predicted_at, target_hour, predicted_calls, model_type)
                    VALUES (:predicted_at, :target_hour, :predicted_calls, :model_type)
                    """
                ),
                {
                    "predicted_at": now_utc,
                    "target_hour": target_hour,
                    "predicted_calls": prediction,
                    "model_type": model_type,
                },
            )
        logger.info(
            f"persist_prediction: inserted prediction "
            f"(target_hour={target_hour.isoformat()}, "
            f"predicted_calls={prediction}, model_type={model_type})"
        )
    except Exception as exc:
        logger.error(
            f"persist_prediction: failed to insert prediction into database: {exc}"
        )
        raise
