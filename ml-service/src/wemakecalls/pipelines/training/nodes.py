"""Training pipeline node functions.

Pure functions for creating targets, splitting data, training models,
evaluating performance, and saving model artifacts.
"""

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .model_factory import get_model

logger = logging.getLogger(__name__)

# Columns excluded from feature matrix X
_NON_FEATURE_COLUMNS = {
    "hour_bucket", "call_count", "next_hour_calls",
    "avg_duration", "abandonment_rate",
}


def create_target(features: pd.DataFrame) -> pd.DataFrame:
    """Create the prediction target by shifting call_count forward by one row.

    The target column `next_hour_calls` for row i equals the `call_count` of
    row i+1. The last row is dropped because it has no target value.

    Args:
        features: DataFrame containing at least a `call_count` column, sorted
            by temporal order (hour_bucket).

    Returns:
        DataFrame with `next_hour_calls` column appended and the last row
        removed.

    Raises:
        ValueError: If fewer than 168 rows remain after target creation.
    """
    df = features.copy()

    # Shift call_count by -1 to get next hour's call count as target
    df["next_hour_calls"] = df["call_count"].shift(-1)

    # Drop the last row (has no target)
    df = df.iloc[:-1].reset_index(drop=True)

    # Convert target to int (shift introduces float due to NaN before drop)
    df["next_hour_calls"] = df["next_hour_calls"].astype(int)

    # Validate minimum row count
    if len(df) < 168:
        raise ValueError(
            f"Feature vector has {len(df)} rows after target creation, "
            f"but the minimum required is 168 rows."
        )

    logger.info(
        f"create_target: created next_hour_calls target column, "
        f"{len(df)} rows remaining after dropping last row"
    )

    return df


def temporal_split(
    features: pd.DataFrame, ratio: float
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split features into train and test sets preserving temporal order.

    The training set consists of the first floor(N * ratio) rows and the test
    set consists of the remaining rows. No shuffling is performed.

    Args:
        features: DataFrame with feature columns and `next_hour_calls` target.
            Must contain `next_hour_calls` column.
        ratio: Float in (0.0, 1.0) representing the proportion of data used
            for training.

    Returns:
        Tuple of (X_train, X_test, y_train, y_test) where X contains only
        feature columns (excluding hour_bucket, call_count, next_hour_calls)
        and y contains the target column.
    """
    n = len(features)
    split_idx = math.floor(n * ratio)

    train = features.iloc[:split_idx]
    test = features.iloc[split_idx:]

    # Determine feature columns (exclude non-feature columns)
    feature_cols = [
        col for col in features.columns if col not in _NON_FEATURE_COLUMNS
    ]

    X_train = train[feature_cols].reset_index(drop=True)
    X_test = test[feature_cols].reset_index(drop=True)
    y_train = train["next_hour_calls"].reset_index(drop=True)
    y_test = test["next_hour_calls"].reset_index(drop=True)

    logger.info(
        f"temporal_split: train={len(X_train)} rows, test={len(X_test)} rows "
        f"(ratio={ratio}, split_idx={split_idx})"
    )

    return X_train, X_test, y_train, y_test


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str,
    params: dict,
) -> Any:
    """Instantiate and fit a model using the model factory.

    Args:
        X_train: Training feature matrix.
        y_train: Training target values.
        model_type: String key identifying the model class (e.g. "catboost").
        params: Dict of keyword arguments passed to the model constructor.

    Returns:
        A fitted model object.
    """
    model = get_model(model_type, params)
    model.fit(X_train, y_train)

    logger.info(
        f"train_model: fitted {model_type} model on {len(X_train)} samples "
        f"with {X_train.shape[1]} features"
    )

    return model


def evaluate_model(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    """Evaluate a trained model on the test set.

    Computes Mean Absolute Error (MAE), Root Mean Squared Error (RMSE),
    and Mean Absolute Percentage Error (MAPE). All metrics are guaranteed
    to be non-negative.

    MAPE handles zero values gracefully by excluding them from the
    calculation. If all actual values are zero, MAPE is set to 0.0.

    Args:
        model: A fitted model with a `predict` method.
        X_test: Test feature matrix.
        y_test: Test target values.

    Returns:
        Dict with keys "mae", "rmse", "mape", all non-negative floats.
    """
    predictions = model.predict(X_test)
    y_actual = np.array(y_test, dtype=float)
    y_pred = np.array(predictions, dtype=float)

    # MAE
    mae = float(np.mean(np.abs(y_actual - y_pred)))

    # RMSE
    rmse = float(np.sqrt(np.mean((y_actual - y_pred) ** 2)))

    # MAPE — handle zero values gracefully
    non_zero_mask = y_actual != 0
    if non_zero_mask.any():
        mape = float(
            np.mean(np.abs((y_actual[non_zero_mask] - y_pred[non_zero_mask]) / y_actual[non_zero_mask])) * 100
        )
    else:
        mape = 0.0

    # Ensure all metrics are non-negative
    metrics = {
        "mae": max(mae, 0.0),
        "rmse": max(rmse, 0.0),
        "mape": max(mape, 0.0),
    }

    logger.info(
        f"evaluate_model: MAE={metrics['mae']:.4f}, "
        f"RMSE={metrics['rmse']:.4f}, MAPE={metrics['mape']:.2f}%"
    )

    return metrics


def save_model_artifact(
    model: Any,
    model_type: str,
    trained_at: datetime,
) -> Path:
    """Serialise a trained model to disk.

    CatBoost models are saved using their native `save_model()` method with
    a `.cbm` extension. All other model types are serialised using joblib
    with a `.pkl` extension.

    Args:
        model: A fitted model object.
        model_type: String key identifying the model class (e.g. "catboost").
        trained_at: Datetime object used for the filename timestamp.

    Returns:
        Path to the saved model artifact file.
    """
    models_dir = Path("data/06_models")
    models_dir.mkdir(parents=True, exist_ok=True)

    # Format timestamp for filename
    timestamp_str = trained_at.strftime("%Y%m%d_%H%M%S")

    # Determine extension and save method
    if model_type == "catboost":
        extension = ".cbm"
        artifact_path = models_dir / f"{model_type}_{timestamp_str}{extension}"
        model.save_model(str(artifact_path))
    else:
        extension = ".pkl"
        artifact_path = models_dir / f"{model_type}_{timestamp_str}{extension}"
        joblib.dump(model, artifact_path)

    logger.info(f"save_model_artifact: saved model to {artifact_path}")

    return artifact_path
