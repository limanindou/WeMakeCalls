"""Integration test: Inference pipeline performance.

Verifies that a single inference pass end-to-end (load model, build batch,
predict) completes within 5 seconds excluding database write time (Requirement 5.8).
"""

import time
from pathlib import Path

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


skip_no_model = pytest.mark.skipif(
    not _has_model_artifact(),
    reason="No model artifact found in data/06_models/ — skipping integration test",
)


@skip_no_model
def test_inference_pass_within_5_seconds():
    """Run a single inference pass (load model, build batch, predict) within 5 seconds.

    Excludes database write time — only measures model loading, batch construction,
    and prediction.
    """
    import numpy as np
    import pandas as pd

    from wemakecalls.pipelines.inference.nodes import (
        FEATURE_COLUMNS,
        build_prediction_batch,
        load_latest_model,
        run_inference,
    )

    start = time.time()

    # Step 1: Load the latest model
    model, model_type = load_latest_model(MODELS_DIR)

    # Step 2: Build a prediction batch
    # Create a minimal feature DataFrame with one row to simulate real usage
    now = pd.Timestamp.now(tz="UTC").floor("h")
    feature_data = {col: [float(np.random.rand())] for col in FEATURE_COLUMNS}
    feature_data["hour_bucket"] = [now]
    features_df = pd.DataFrame(feature_data)

    batch = build_prediction_batch(features_df)

    # Step 3: Run inference
    predicted_calls = run_inference(model, batch)

    elapsed = time.time() - start

    # Verify the result is valid
    assert isinstance(predicted_calls, int)
    assert predicted_calls >= 0

    # Assert performance requirement
    assert elapsed < 5, (
        f"Inference pass took {elapsed:.2f}s, exceeding the 5s threshold"
    )
