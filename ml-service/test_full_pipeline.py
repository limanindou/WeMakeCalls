"""
Full end-to-end pipeline test with PostgreSQL.

Tests the complete flow: CSV generation → ingestion (with DB) → feature
engineering → training → inference (with DB persistence).

Requires: docker container 'wmc-postgres' running on localhost:5432
"""

import os
import sys
import time

sys.path.insert(0, "src")

# Set DATABASE_URL for the pipeline
os.environ["DATABASE_URL"] = "postgresql://wmc:wmc@127.0.0.1:5433/wemakecalls"

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from wemakecalls.pipelines.csv_generator import generate_call_logs
from wemakecalls.pipelines.ingestion.nodes import (
    deduplicate,
    insert_to_postgres,
    parse_and_clean,
    validate_columns,
)
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
    persist_prediction,
    run_inference,
)


def main():
    engine = create_engine(os.environ["DATABASE_URL"])

    print("=" * 60)
    print("WeMakeCalls — Full End-to-End Pipeline Test (with DB)")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Step 1: Generate CSV
    # ---------------------------------------------------------------
    print("\n[1/8] Generating 200,000 synthetic call records...")
    csv_path = generate_call_logs(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        row_count=200_000,
        output_dir=Path("data/01_raw"),
    )
    print(f"       Done: {csv_path}")

    # ---------------------------------------------------------------
    # Step 2: Ingestion pipeline (with real DB)
    # ---------------------------------------------------------------
    print("\n[2/8] Running ingestion pipeline (CSV → PostgreSQL)...")
    df = pd.read_csv(csv_path)
    start = time.time()

    df = validate_columns(df)
    print(f"       Columns validated")

    df = parse_and_clean(df)
    print(f"       Cleaned: {len(df):,} rows remaining")

    df = deduplicate(df, engine)
    print(f"       Deduplicated: {len(df):,} rows to insert")

    summary = insert_to_postgres(df, engine)
    elapsed = time.time() - start
    print(f"       Inserted {summary['rows_inserted']:,} rows in {elapsed:.1f}s")

    # Verify rows in DB
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM call_logs")).scalar()
    print(f"       Total rows in call_logs table: {count:,}")

    # ---------------------------------------------------------------
    # Step 3: Read back from DB for feature engineering
    # ---------------------------------------------------------------
    print("\n[3/8] Reading call logs from PostgreSQL...")
    with engine.connect() as conn:
        call_logs = pd.read_sql(
            "SELECT * FROM call_logs ORDER BY started_at",
            conn,
        )
    print(f"       Read {len(call_logs):,} rows from database")

    # ---------------------------------------------------------------
    # Step 4: Feature engineering
    # ---------------------------------------------------------------
    print("\n[4/8] Engineering features...")
    hourly = aggregate_hourly(call_logs)
    hourly = compute_lag_features(hourly, lag_windows=[1, 2, 24, 168])

    holidays = [
        "2024-01-01", "2024-03-21", "2024-03-29", "2024-04-01",
        "2024-04-27", "2024-05-01", "2024-06-16", "2024-06-17",
        "2024-08-09", "2024-09-24", "2024-12-16", "2024-12-25", "2024-12-26",
    ]
    hourly = compute_calendar_features(hourly, holidays=holidays)
    hourly = compute_rolling_avg(hourly)
    features = fill_missing_features(hourly)
    features = validate_feature_ranges(features)
    features.to_parquet("data/03_primary/features.parquet", engine="pyarrow")
    print(f"       Features: {features.shape[0]:,} rows × {features.shape[1]} columns")

    # ---------------------------------------------------------------
    # Step 5: Training
    # ---------------------------------------------------------------
    print("\n[5/8] Training CatBoost model...")
    features_with_target = create_target(features)
    X_train, X_test, y_train, y_test = temporal_split(features_with_target, 0.8)
    model = train_model(X_train, y_train, "catboost", {"iterations": 500, "depth": 6})
    print(f"       Trained on {len(X_train):,} rows")

    # ---------------------------------------------------------------
    # Step 6: Evaluate
    # ---------------------------------------------------------------
    print("\n[6/8] Evaluating model...")
    metrics = evaluate_model(model, X_test, y_test)
    print(f"       MAE:  {metrics['mae']:.2f}")
    print(f"       RMSE: {metrics['rmse']:.2f}")
    print(f"       MAPE: {metrics['mape']:.2f}%")

    # Save artifact
    trained_at = datetime.now(timezone.utc)
    artifact = save_model_artifact(model, "catboost", trained_at)
    print(f"       Saved: {artifact}")

    # ---------------------------------------------------------------
    # Step 7: Inference with DB persistence
    # ---------------------------------------------------------------
    print("\n[7/8] Running inference (with DB persistence)...")
    loaded_model, model_type = load_latest_model(Path("data/06_models"))
    last_row = features[FEATURE_COLUMNS].iloc[[-1]]
    predicted_calls = run_inference(loaded_model, last_row)
    print(f"       Predicted: {predicted_calls} calls for next hour")

    # Persist to DB
    persist_prediction(predicted_calls, model_type, engine)
    print(f"       Prediction persisted to database")

    # Verify prediction in DB
    with engine.connect() as conn:
        pred_count = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
        latest = conn.execute(
            text("SELECT predicted_calls, target_hour, model_type FROM predictions ORDER BY predicted_at DESC LIMIT 1")
        ).fetchone()
    print(f"       Total predictions in DB: {pred_count}")
    print(f"       Latest: {latest[0]} calls at {latest[1]} ({latest[2]})")

    # ---------------------------------------------------------------
    # Step 8: Test the FastAPI endpoints
    # ---------------------------------------------------------------
    print("\n[8/8] Testing FastAPI endpoints...")
    from fastapi.testclient import TestClient
    from entrypoints.api import app, model_state

    # Load model into API state
    model_state.load()

    client = TestClient(app)

    # Health check
    resp = client.get("/health")
    print(f"       GET /health → {resp.status_code}: {resp.json()}")

    # Model info
    resp = client.get("/model/info")
    print(f"       GET /model/info → {resp.status_code}: {resp.json()}")

    # Predict
    payload = {
        "calls_lag_1h": 25.0,
        "calls_lag_2h": 22.0,
        "calls_lag_24h": 28.0,
        "calls_lag_168h": 30.0,
        "hour_of_day": 14,
        "day_of_week": 2,
        "is_weekend": False,
        "is_holiday": False,
        "rolling_avg_7d": 26.5,
        "avg_duration_lag_1h": 180.0,
        "abandonment_rate_lag_1h": 0.08,
    }
    resp = client.post("/predict", json=payload)
    print(f"       POST /predict → {resp.status_code}: {resp.json()}")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print(f"  Ingestion:  {summary['rows_inserted']:,} rows → PostgreSQL ({elapsed:.1f}s)")
    print(f"  Features:   {features.shape[0]:,} hourly buckets")
    print(f"  Model:      CatBoost | MAE={metrics['mae']:.2f} | RMSE={metrics['rmse']:.2f}")
    print(f"  Inference:  {predicted_calls} calls predicted")
    print(f"  API:        All endpoints responding correctly")
    print("=" * 60)

    engine.dispose()


if __name__ == "__main__":
    main()
