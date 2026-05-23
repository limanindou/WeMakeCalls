"""Training pipeline definition.

Chains the five training nodes into a Kedro Pipeline:
    create_target → temporal_split → train_model → evaluate_model → save_model_artifact

Additionally includes a logging node that:
- Inserts a training-run row into the ``predictions`` table (with
  ``predicted_calls`` and ``target_hour`` as NULL)
- Logs training start time, model type, set sizes, and metrics
"""

import logging
import os
from datetime import datetime, timezone

import pandas as pd
from kedro.pipeline import Pipeline, node
from sqlalchemy import create_engine, text

from .nodes import (
    create_target,
    evaluate_model,
    save_model_artifact,
    temporal_split,
    train_model,
)

logger = logging.getLogger(__name__)


def _get_trained_at() -> datetime:
    """Return the current UTC time as the training start timestamp."""
    return datetime.now(timezone.utc)


def _train_model_with_timestamp(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str,
):
    """Wrapper around train_model that also captures training start time.

    Returns a tuple of (fitted_model, trained_at) so that the timestamp
    can be threaded through the pipeline to save_model_artifact.
    """
    trained_at = _get_trained_at()
    model = train_model(X_train, y_train, model_type, {})
    return model, trained_at


def _save_model_artifact_wrapper(
    model_and_timestamp: tuple,
    model_type: str,
):
    """Unwrap the (model, trained_at) tuple and delegate to save_model_artifact."""
    model, trained_at = model_and_timestamp
    artifact_path = save_model_artifact(model, model_type, trained_at)
    return artifact_path, model, trained_at


def _evaluate_and_log(
    model_and_timestamp: tuple,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    X_train: pd.DataFrame,
    model_type: str,
):
    """Evaluate the model, log training summary, and insert a row into predictions.

    This node:
    1. Evaluates the model on the test set (MAE, RMSE, MAPE)
    2. Logs training start time, model type, train/test set sizes, and metrics
    3. Inserts a training-run row into the ``predictions`` table with
       ``predicted_calls`` and ``target_hour`` set to NULL

    Args:
        model_and_timestamp: Tuple of (fitted_model, trained_at datetime).
        X_test: Test feature matrix.
        y_test: Test target values.
        X_train: Training feature matrix (used for logging set size).
        model_type: String key identifying the model class.

    Returns:
        Dict with training metrics (mae, rmse, mape).
    """
    model, trained_at = model_and_timestamp

    # Evaluate model
    metrics = evaluate_model(model, X_test, y_test)

    # Log training summary
    logger.info(
        "Training complete: "
        "trained_at=%s, model_type=%s, "
        "train_size=%d, test_size=%d, "
        "MAE=%.4f, RMSE=%.4f, MAPE=%.2f%%",
        trained_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        model_type,
        len(X_train),
        len(X_test),
        metrics["mae"],
        metrics["rmse"],
        metrics["mape"],
    )

    # Insert training-run row into predictions table
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            engine = create_engine(database_url)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO predictions "
                        "(predicted_at, target_hour, predicted_calls, model_type, mae, rmse, mape) "
                        "VALUES (:predicted_at, NULL, NULL, :model_type, :mae, :rmse, :mape)"
                    ),
                    {
                        "predicted_at": trained_at,
                        "model_type": model_type,
                        "mae": metrics["mae"],
                        "rmse": metrics["rmse"],
                        "mape": metrics["mape"],
                    },
                )
            logger.info(
                "Inserted training-run row into predictions table "
                "(predicted_calls=NULL, target_hour=NULL)"
            )
        except Exception as exc:
            logger.warning(
                "Failed to insert training-run row into predictions table: %s",
                exc,
            )
    else:
        logger.warning(
            "DATABASE_URL not set — skipping predictions table insert for training run"
        )

    return metrics


def create_pipeline(**kwargs) -> Pipeline:
    """Create the training pipeline.

    The pipeline reads the ``feature_vectors`` catalog entry, creates the
    prediction target, splits into train/test sets, trains the model,
    evaluates it, saves the artifact, and logs the training run to the
    ``predictions`` table.

    Parameters sourced from ``conf/base/parameters.yml``:
    - ``model_type``: Which model to train (default: catboost)
    - ``train_test_split_ratio``: Proportion of data for training (default: 0.8)
    """
    return Pipeline(
        [
            node(
                func=create_target,
                inputs="feature_vectors",
                outputs="features_with_target",
                name="create_target",
            ),
            node(
                func=temporal_split,
                inputs=["features_with_target", "params:train_test_split_ratio"],
                outputs=["X_train", "X_test", "y_train", "y_test"],
                name="temporal_split",
            ),
            node(
                func=_train_model_with_timestamp,
                inputs=["X_train", "y_train", "params:model_type"],
                outputs="model_and_timestamp",
                name="train_model",
            ),
            node(
                func=_save_model_artifact_wrapper,
                inputs=["model_and_timestamp", "params:model_type"],
                outputs=["artifact_path", "trained_model", "trained_at"],
                name="save_model_artifact",
            ),
            node(
                func=_evaluate_and_log,
                inputs=[
                    "model_and_timestamp",
                    "X_test",
                    "y_test",
                    "X_train",
                    "params:model_type",
                ],
                outputs="training_metrics",
                name="evaluate_and_log_training",
            ),
        ]
    )
