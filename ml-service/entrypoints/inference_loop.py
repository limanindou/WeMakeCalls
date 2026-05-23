"""
Inference Simulation Loop — runs continuously, generating one prediction per second.

Each second simulates 1 hour of real time. The loop:
1. Reads the feature vectors from the primary data
2. Steps through them one at a time (1 row per second)
3. Runs inference using the trained model
4. Appends the prediction to a shared parquet file
5. The dashboard reads this file every 1 second to update the chart

This mimics the free-bootcamp-mlacademy pattern where inference runs
automatically every 1 second simulating 1h of dataset time.
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
os.chdir(project_root)

from wemakecalls.pipelines.inference.nodes import load_latest_model, run_inference, FEATURE_COLUMNS
from wemakecalls.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Paths
FEATURES_PATH = project_root / "data" / "03_primary" / "features.parquet"
PREDICTIONS_PATH = project_root / "data" / "07_model_output" / "predictions.parquet"
ACTUALS_PATH = project_root / "data" / "07_model_output" / "actuals.parquet"
MODELS_DIR = project_root / "data" / "06_models"

# Simulation speed: 1 second = 1 hour of simulated time
INTERVAL_SECONDS = 1


def main():
    """Run the inference simulation loop."""
    print("=" * 60)
    print("WeMakeCalls — Inference Simulation Loop")
    print("=" * 60)
    print(f"  Features: {FEATURES_PATH}")
    print(f"  Predictions output: {PREDICTIONS_PATH}")
    print(f"  Interval: {INTERVAL_SECONDS}s (1 hour per second)")
    print("=" * 60)

    # Load model
    try:
        model, model_type = load_latest_model(MODELS_DIR)
        logger.info(f"Loaded model: {model_type}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        print(f"ERROR: No model found in {MODELS_DIR}. Run training first.")
        sys.exit(1)

    # Load feature vectors
    if not FEATURES_PATH.exists():
        logger.error(f"Features file not found: {FEATURES_PATH}")
        print(f"ERROR: Features file not found at {FEATURES_PATH}")
        sys.exit(1)

    features_df = pd.read_parquet(FEATURES_PATH)
    features_df["hour_bucket"] = pd.to_datetime(features_df["hour_bucket"])
    features_df = features_df.sort_values("hour_bucket").reset_index(drop=True)

    logger.info(f"Loaded {len(features_df)} feature rows spanning "
                f"{features_df['hour_bucket'].min()} to {features_df['hour_bucket'].max()}")

    # Initialize predictions storage
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    predictions_list = []

    # Also prepare actuals for the dashboard comparison
    if "call_count" in features_df.columns:
        actuals_df = features_df[["hour_bucket", "call_count"]].copy()
        actuals_df.columns = ["datetime", "cnt"]
        actuals_df.to_parquet(ACTUALS_PATH, index=False)
        logger.info(f"Wrote {len(actuals_df)} actual data points to {ACTUALS_PATH}")

    # Start simulation loop
    print(f"\nStarting inference loop — stepping through {len(features_df)} hours...")
    print("Each second = 1 hour of simulated call center time\n")

    current_idx = 0

    while True:
        if current_idx >= len(features_df):
            # Loop back to start for continuous demo
            current_idx = 0
            predictions_list = []
            logger.info("Reached end of dataset, looping back to start")

        row = features_df.iloc[current_idx]
        hour_bucket = row["hour_bucket"]

        # Build feature batch for inference
        feature_dict = {}
        for col in FEATURE_COLUMNS:
            if col in row.index:
                feature_dict[col] = row[col]
            else:
                feature_dict[col] = 0.0

        batch = pd.DataFrame([feature_dict], columns=FEATURE_COLUMNS)

        # Run inference
        try:
            predicted_calls = run_inference(model, batch)
        except Exception as e:
            logger.warning(f"Inference failed for idx {current_idx}: {e}")
            predicted_calls = 0

        # Record prediction
        prediction_record = {
            "datetime": hour_bucket + pd.Timedelta(hours=1),  # predicting next hour
            "prediction": float(predicted_calls),
            "model_type": model_type,
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }
        predictions_list.append(prediction_record)

        # Write predictions to parquet (overwrite each time for simplicity)
        pred_df = pd.DataFrame(predictions_list)
        pred_df["datetime"] = pd.to_datetime(pred_df["datetime"])
        pred_df.to_parquet(PREDICTIONS_PATH, index=False)

        # Log progress
        actual = int(row.get("call_count", 0))
        logger.info(
            f"[{current_idx + 1}/{len(features_df)}] "
            f"Hour: {hour_bucket} | Predicted: {predicted_calls} | Actual: {actual}"
        )

        current_idx += 1
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
