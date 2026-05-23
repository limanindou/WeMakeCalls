"""
Local training script — exercises the full ML pipeline without a database.

Generates 200,000 synthetic call records spanning a full year, engineers
features, trains a CatBoost model, evaluates it, and runs a test inference.
"""

import sys
sys.path.insert(0, "src")

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from wemakecalls.pipelines.csv_generator import generate_call_logs
from wemakecalls.pipelines.feature_engineering.nodes import (
    aggregate_hourly,
    compute_calendar_features,
    compute_lag_features,
    compute_rolling_avg,
    fill_missing_features,
    validate_feature_ranges,
)
from wemakecalls.pipelines.training.nodes import (
    create_target,
    evaluate_model,
    save_model_artifact,
    temporal_split,
    train_model,
)
from wemakecalls.pipelines.inference.nodes import (
    FEATURE_COLUMNS,
    load_latest_model,
    run_inference,
)


def main():
    print("=" * 60)
    print("WeMakeCalls ML Service — Local Training Pipeline")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Step 1: Generate synthetic call data (200k rows, full year)
    # ---------------------------------------------------------------
    print("\n[1/7] Generating 200,000 synthetic call records...")
    csv_path = generate_call_logs(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        row_count=200_000,
        output_dir=Path("data/01_raw"),
    )
    print(f"       CSV written to: {csv_path}")

    # ---------------------------------------------------------------
    # Step 2: Read CSV and simulate ingestion (rename datetime → started_at)
    # ---------------------------------------------------------------
    print("\n[2/7] Reading and preparing data...")
    df = pd.read_csv(csv_path, parse_dates=["datetime"])
    df = df.rename(columns={"datetime": "started_at"})
    print(f"       Loaded {len(df):,} rows")

    # ---------------------------------------------------------------
    # Step 3: Feature engineering
    # ---------------------------------------------------------------
    print("\n[3/7] Engineering features...")

    hourly = aggregate_hourly(df)
    print(f"       Hourly buckets: {len(hourly):,}")

    hourly = compute_lag_features(hourly, lag_windows=[1, 2, 24, 168])
    print(f"       Lag features added (windows: 1h, 2h, 24h, 168h)")

    holidays = [
        "2024-01-01", "2024-03-21", "2024-03-29", "2024-04-01",
        "2024-04-27", "2024-05-01", "2024-06-16", "2024-06-17",
        "2024-08-09", "2024-09-24", "2024-12-16", "2024-12-25", "2024-12-26",
    ]
    hourly = compute_calendar_features(hourly, holidays=holidays)
    print(f"       Calendar features added (SA holidays: {len(holidays)})")

    hourly = compute_rolling_avg(hourly)
    print(f"       Rolling 7-day average added")

    features = fill_missing_features(hourly)
    features = validate_feature_ranges(features)
    print(f"       Feature validation passed. Shape: {features.shape}")

    # Save features to Parquet
    features.to_parquet("data/03_primary/features.parquet", engine="pyarrow")
    print(f"       Features saved to data/03_primary/features.parquet")

    # ---------------------------------------------------------------
    # Step 4: Create target and split
    # ---------------------------------------------------------------
    print("\n[4/7] Creating target and splitting data...")
    features_with_target = create_target(features)
    X_train, X_test, y_train, y_test = temporal_split(features_with_target, 0.8)
    print(f"       Train: {len(X_train):,} rows | Test: {len(X_test):,} rows")

    # ---------------------------------------------------------------
    # Step 5: Train model
    # ---------------------------------------------------------------
    print("\n[5/7] Training CatBoost model...")
    model = train_model(X_train, y_train, "catboost", {"iterations": 500, "depth": 6})
    print(f"       Training complete!")

    # ---------------------------------------------------------------
    # Step 6: Evaluate
    # ---------------------------------------------------------------
    print("\n[6/7] Evaluating model...")
    metrics = evaluate_model(model, X_test, y_test)
    print(f"       MAE:  {metrics['mae']:.2f} calls")
    print(f"       RMSE: {metrics['rmse']:.2f} calls")
    print(f"       MAPE: {metrics['mape']:.2f}%")

    # Save model artifact
    trained_at = datetime.now(timezone.utc)
    artifact_path = save_model_artifact(model, "catboost", trained_at)
    print(f"       Model saved to: {artifact_path}")

    # ---------------------------------------------------------------
    # Step 7: Test inference
    # ---------------------------------------------------------------
    print("\n[7/7] Running test inference...")
    loaded_model, model_type = load_latest_model(Path("data/06_models"))
    print(f"       Loaded model: {model_type}")

    # Use the last row of features as the prediction batch
    last_row = features[FEATURE_COLUMNS].iloc[[-1]]
    predicted_calls = run_inference(loaded_model, last_row)
    print(f"       Predicted calls for next hour: {predicted_calls}")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Data:       200,000 call records (Jan–Dec 2024)")
    print(f"  Features:   {features.shape[1]} columns, {features.shape[0]:,} hourly buckets")
    print(f"  Model:      CatBoost (500 iterations, depth 6)")
    print(f"  MAE:        {metrics['mae']:.2f} calls")
    print(f"  RMSE:       {metrics['rmse']:.2f} calls")
    print(f"  MAPE:       {metrics['mape']:.2f}%")
    print(f"  Artifact:   {artifact_path}")
    print(f"  Prediction: {predicted_calls} calls (next hour)")
    print("=" * 60)


if __name__ == "__main__":
    main()
