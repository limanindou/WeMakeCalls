"""Inference pipeline definition.

Chains the four inference nodes into a Kedro Pipeline:
    load_latest_model → build_prediction_batch → run_inference → persist_prediction

Includes wrapper nodes to handle the tuple output from ``load_latest_model``
(model, model_type) and a logging node that reports target hour, predicted
call count, and model type on success.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from kedro.pipeline import Pipeline, node
from sqlalchemy.engine import Engine

from .nodes import (
    build_prediction_batch,
    load_latest_model,
    persist_prediction,
    run_inference,
)

logger = logging.getLogger(__name__)

# Default models directory path
MODELS_DIR = Path("data/06_models")


def _load_latest_model_wrapper() -> tuple[Any, str]:
    """Load the latest model artifact from the default models directory.

    Wraps ``load_latest_model`` to supply the models directory path,
    making it compatible with Kedro's node interface.

    Returns:
        Tuple of (model, model_type_str).
    """
    return load_latest_model(MODELS_DIR)


def _unpack_model(model_and_type: tuple) -> Any:
    """Extract the model object from the (model, model_type) tuple."""
    model, _ = model_and_type
    return model


def _unpack_model_type(model_and_type: tuple) -> str:
    """Extract the model_type string from the (model, model_type) tuple."""
    _, model_type = model_and_type
    return model_type


def _run_inference_wrapper(model: Any, batch: pd.DataFrame) -> int:
    """Run inference using the model and batch.

    Delegates to ``run_inference`` node function.
    """
    return run_inference(model, batch)


def _persist_and_log(
    prediction: int,
    model_type: str,
    engine: Engine,
) -> dict:
    """Persist the prediction and log success details.

    Calls ``persist_prediction`` to insert the row into PostgreSQL, then
    logs the target hour, predicted call count, and model type.

    Args:
        prediction: Non-negative integer predicted call count.
        model_type: String identifying the model type.
        engine: SQLAlchemy Engine for database access.

    Returns:
        Dict with inference summary (target_hour, predicted_calls, model_type).
    """
    # Compute target hour (next hour bucket start)
    now_utc = datetime.now(timezone.utc)
    target_hour = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    # Persist the prediction to the database
    persist_prediction(prediction, model_type, engine)

    # Log success with target hour, predicted call count, and model type
    logger.info(
        "Inference pipeline complete: "
        "target_hour=%s, predicted_calls=%d, model_type=%s",
        target_hour.strftime("%Y-%m-%dT%H:%M:%SZ"),
        prediction,
        model_type,
    )

    return {
        "target_hour": target_hour.isoformat(),
        "predicted_calls": prediction,
        "model_type": model_type,
    }


def create_pipeline(**kwargs) -> Pipeline:
    """Create the inference pipeline.

    The pipeline:
    1. Loads the latest model artifact from ``data/06_models/``
    2. Builds a prediction batch from the most recent feature vector
    3. Runs inference to produce a predicted call count
    4. Persists the prediction to PostgreSQL and logs the result

    Inputs from catalog:
    - ``feature_vectors``: Parquet dataset with engineered features
    - ``engine``: SQLAlchemy Engine for database persistence (provided via
      catalog as a MemoryDataset populated by a hook or session-scoped factory)
    """
    return Pipeline(
        [
            node(
                func=_load_latest_model_wrapper,
                inputs=None,
                outputs="model_and_type",
                name="load_latest_model",
            ),
            node(
                func=_unpack_model,
                inputs="model_and_type",
                outputs="inference_model",
                name="unpack_model",
            ),
            node(
                func=_unpack_model_type,
                inputs="model_and_type",
                outputs="inference_model_type",
                name="unpack_model_type",
            ),
            node(
                func=build_prediction_batch,
                inputs="feature_vectors",
                outputs="prediction_batch",
                name="build_prediction_batch",
            ),
            node(
                func=_run_inference_wrapper,
                inputs=["inference_model", "prediction_batch"],
                outputs="predicted_calls",
                name="run_inference",
            ),
            node(
                func=_persist_and_log,
                inputs=["predicted_calls", "inference_model_type", "engine"],
                outputs="inference_summary",
                name="persist_and_log_prediction",
            ),
        ]
    )
