"""Kedro pipeline registry.

Registers all four pipelines so they are discoverable via:
    kedro run --pipeline=ingestion
    kedro run --pipeline=feature_engineering
    kedro run --pipeline=training
    kedro run --pipeline=inference

Pipeline implementations are stubs (empty Pipeline([])) until the
corresponding pipeline modules are implemented in later tasks.
"""

from kedro.pipeline import Pipeline

from wemakecalls.logging_config import setup_logging

# Configure structured JSON logging when pipelines are registered (Kedro startup)
setup_logging()


def register_pipelines() -> dict[str, Pipeline]:
    """Return a mapping of pipeline names to Pipeline objects.

    Kedro calls this function to discover all available pipelines.
    Each pipeline is currently a stub (empty Pipeline([])) that will be
    replaced with a real implementation as the project progresses.
    """
    # Import guards: attempt to import real pipeline factories if they exist,
    # fall back to empty stubs if the modules have not been implemented yet.
    try:
        from wemakecalls.pipelines.ingestion.pipeline import create_pipeline as ingestion_pipeline
    except ImportError:
        ingestion_pipeline = lambda: Pipeline([])  # noqa: E731

    try:
        from wemakecalls.pipelines.feature_engineering.pipeline import (
            create_pipeline as feature_engineering_pipeline,
        )
    except ImportError:
        feature_engineering_pipeline = lambda: Pipeline([])  # noqa: E731

    try:
        from wemakecalls.pipelines.training.pipeline import create_pipeline as training_pipeline
    except ImportError:
        training_pipeline = lambda: Pipeline([])  # noqa: E731

    try:
        from wemakecalls.pipelines.inference.pipeline import create_pipeline as inference_pipeline
    except ImportError:
        inference_pipeline = lambda: Pipeline([])  # noqa: E731

    return {
        "ingestion": ingestion_pipeline(),
        "feature_engineering": feature_engineering_pipeline(),
        "training": training_pipeline(),
        "inference": inference_pipeline(),
        # __default__ runs all pipelines in sequence when no --pipeline flag is given
        "__default__": (
            ingestion_pipeline()
            + feature_engineering_pipeline()
            + training_pipeline()
            + inference_pipeline()
        ),
    }
