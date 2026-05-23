"""
Generate historical predictions for the dashboard.

Runs the trained model against historical feature data and inserts
predictions into the predictions table so the dashboard can show
predicted vs actual side by side.
"""

import os
import sys

sys.path.insert(0, "src")

os.environ["DATABASE_URL"] = "postgresql://wmc:wmc@127.0.0.1:5433/wemakecalls"

import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
from wemakecalls.pipelines.inference.nodes import load_latest_model, FEATURE_COLUMNS

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)


def main():
    print("Loading trained model...")
    model, model_type = load_latest_model(Path("data/06_models"))
    print(f"  Model: {model_type}")

    print("Loading features from Parquet...")
    features = pd.read_parquet("data/03_primary/features.parquet", engine="pyarrow")
    print(f"  Features: {len(features)} rows")

    # Use the last 200 hourly buckets for predictions (about 8 days)
    prediction_data = features.tail(200).copy()

    print(f"Generating predictions for {len(prediction_data)} hour buckets...")

    # Run predictions
    predictions = []
    for i, row in prediction_data.iterrows():
        batch = pd.DataFrame([row[FEATURE_COLUMNS].to_dict()])
        pred = model.predict(batch)
        predicted_calls = int(max(0, round(float(pred[0]))))

        predictions.append({
            "predicted_at": row["hour_bucket"],
            "target_hour": row["hour_bucket"] + pd.Timedelta(hours=1),
            "predicted_calls": predicted_calls,
            "model_type": model_type,
        })

    predictions_df = pd.DataFrame(predictions)
    print(f"  Generated {len(predictions_df)} predictions")
    print(f"  Range: {predictions_df['target_hour'].min()} → {predictions_df['target_hour'].max()}")

    # Clear old predictions and insert new ones
    print("Inserting into database...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM predictions"))
        predictions_df.to_sql("predictions", conn, if_exists="append", index=False)

    print(f"  Inserted {len(predictions_df)} predictions into database")

    # Verify
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
        sample = pd.read_sql(text("SELECT target_hour, predicted_calls FROM predictions ORDER BY target_hour DESC LIMIT 5"), conn)

    print(f"\nDone! {count} predictions in database")
    print(f"\nSample (latest 5):")
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
