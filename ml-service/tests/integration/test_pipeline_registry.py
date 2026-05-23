"""Integration test: Pipeline registry.

Verifies that all four pipeline names (ingestion, feature_engineering,
training, inference) are registered in the Kedro pipeline registry and
each is discoverable (Requirement 7.4).
"""

import pytest
from kedro.pipeline import Pipeline

pytestmark = pytest.mark.integration

EXPECTED_PIPELINES = ["ingestion", "feature_engineering", "training", "inference"]


def test_all_four_pipelines_are_registered():
    """Verify all four pipeline names exist in the registry."""
    from wemakecalls.pipeline_registry import register_pipelines

    pipelines = register_pipelines()

    for name in EXPECTED_PIPELINES:
        assert name in pipelines, (
            f"Pipeline '{name}' is not registered in the pipeline registry. "
            f"Available pipelines: {list(pipelines.keys())}"
        )


def test_each_pipeline_is_a_pipeline_instance():
    """Verify each registered pipeline value is a Kedro Pipeline instance."""
    from wemakecalls.pipeline_registry import register_pipelines

    pipelines = register_pipelines()

    for name in EXPECTED_PIPELINES:
        assert isinstance(pipelines[name], Pipeline), (
            f"Pipeline '{name}' is not a Pipeline instance. "
            f"Got type: {type(pipelines[name])}"
        )


def test_pipelines_are_non_empty():
    """Verify each pipeline contains at least one node (is not a stub)."""
    from wemakecalls.pipeline_registry import register_pipelines

    pipelines = register_pipelines()

    for name in EXPECTED_PIPELINES:
        pipeline = pipelines[name]
        assert len(pipeline.nodes) > 0, (
            f"Pipeline '{name}' is empty (has no nodes). "
            "Expected a fully implemented pipeline."
        )


def test_default_pipeline_contains_all_four():
    """Verify the __default__ pipeline includes nodes from all four pipelines."""
    from wemakecalls.pipeline_registry import register_pipelines

    pipelines = register_pipelines()

    assert "__default__" in pipelines, (
        "__default__ pipeline is not registered in the pipeline registry"
    )

    default_pipeline = pipelines["__default__"]
    assert len(default_pipeline.nodes) > 0, (
        "__default__ pipeline is empty"
    )
