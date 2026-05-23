"""
Generate realistic synthetic call center data for the last 7 days.

Creates hourly call volume data with realistic patterns:
- Peak hours: 9am-5pm (20-50 calls/hour)
- Evening: 5pm-9pm (10-25 calls/hour)
- Night: 9pm-7am (2-8 calls/hour)
- Weekends: 40% less volume
- Random noise for realism

Outputs:
- data/03_primary/features.parquet (feature vectors for inference)
- data/07_model_output/actuals.parquet (actual call counts for dashboard)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

np.random.seed(42)

# Generate 7 days of hourly data ending at current time
END_TIME = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
START_TIME = END_TIME - timedelta(days=7)

hours = pd.date_range(start=START_TIME, end=END_TIME, freq="h", tz="UTC")

def generate_call_count(dt):
    """Generate realistic call count for a given hour."""
    hour = dt.hour
    dow = dt.dayofweek  # 0=Monday, 6=Sunday
    is_weekend = dow >= 5
    
    # Base pattern by hour of day
    if 9 <= hour <= 17:  # Business hours
        base = np.random.randint(25, 50)
    elif 7 <= hour <= 9 or 17 <= hour <= 21:  # Shoulder hours
        base = np.random.randint(12, 28)
    else:  # Night
        base = np.random.randint(2, 10)
    
    # Weekend reduction
    if is_weekend:
        base = int(base * 0.6)
    
    # Add some noise
    noise = np.random.randint(-3, 4)
    return max(1, base + noise)


# Generate call counts
call_counts = [generate_call_count(h) for h in hours]

# Build the features dataframe
data = []
for i, (hour_bucket, call_count) in enumerate(zip(hours, call_counts)):
    row = {
        "hour_bucket": hour_bucket,
        "call_count": call_count,
        "calls_lag_1h": call_counts[i - 1] if i > 0 else call_count,
        "calls_lag_2h": call_counts[i - 2] if i > 1 else call_count,
        "calls_lag_24h": call_counts[i - 24] if i >= 24 else call_count,
        "calls_lag_168h": call_counts[i - 168] if i >= 168 else call_count,
        "hour_of_day": hour_bucket.hour,
        "day_of_week": hour_bucket.dayofweek,
        "is_weekend": hour_bucket.dayofweek >= 5,
        "is_holiday": False,
        "rolling_avg_7d": np.mean(call_counts[max(0, i - 168):i + 1]),
        "avg_duration_lag_1h": np.random.uniform(120, 360),  # 2-6 min avg call
        "abandonment_rate_lag_1h": np.random.uniform(0.02, 0.15),  # 2-15%
    }
    data.append(row)

features_df = pd.DataFrame(data)

# Save features
features_path = Path("data/03_primary/features.parquet")
features_path.parent.mkdir(parents=True, exist_ok=True)
features_df.to_parquet(features_path, index=False)
print(f"✓ Generated {len(features_df)} hourly feature rows")
print(f"  Time range: {features_df['hour_bucket'].min()} to {features_df['hour_bucket'].max()}")
print(f"  Saved to: {features_path}")

# Save actuals for dashboard
actuals_df = features_df[["hour_bucket", "call_count"]].copy()
actuals_df.columns = ["datetime", "cnt"]
actuals_path = Path("data/07_model_output/actuals.parquet")
actuals_path.parent.mkdir(parents=True, exist_ok=True)
actuals_df.to_parquet(actuals_path, index=False)
print(f"✓ Saved actuals to: {actuals_path}")

# Print sample
print(f"\nSample data (last 24 hours):")
print(features_df[["hour_bucket", "call_count", "hour_of_day", "day_of_week"]].tail(24).to_string(index=False))
