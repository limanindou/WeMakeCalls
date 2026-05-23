"""Smoke test for feature engineering nodes."""
import sys
sys.path.insert(0, "src")

import pandas as pd
import numpy as np
from wemakecalls.pipelines.feature_engineering.nodes import (
    aggregate_hourly, compute_lag_features, compute_calendar_features,
    compute_rolling_avg, fill_missing_features, validate_feature_ranges
)

# Create sample call_logs data
np.random.seed(42)
dates = pd.date_range("2024-01-01", periods=100, freq="15min", tz="UTC")
call_logs = pd.DataFrame({
    "started_at": dates,
    "duration_seconds": np.random.randint(30, 600, size=100),
    "abandoned": np.random.choice([True, False], size=100, p=[0.1, 0.9])
})

# Test aggregate_hourly
hourly = aggregate_hourly(call_logs)
print(f"aggregate_hourly: {len(hourly)} rows, columns: {list(hourly.columns)}")
assert "hour_bucket" in hourly.columns
assert "call_count" in hourly.columns
assert "avg_duration" in hourly.columns
assert "abandonment_rate" in hourly.columns
# Verify one row per distinct hour bucket
assert len(hourly) == call_logs["started_at"].dt.floor("h").nunique()

# Test compute_lag_features
lag_windows = [1, 2, 24, 168]
with_lags = compute_lag_features(hourly, lag_windows)
assert "calls_lag_1h" in with_lags.columns
assert "calls_lag_2h" in with_lags.columns
assert "calls_lag_24h" in with_lags.columns
assert "calls_lag_168h" in with_lags.columns
assert "avg_duration_lag_1h" in with_lags.columns
assert "abandonment_rate_lag_1h" in with_lags.columns
print(f"compute_lag_features: all lag columns present")

# Test compute_calendar_features
holidays = ["2024-01-01", "2024-12-25"]
with_cal = compute_calendar_features(with_lags, holidays)
assert "hour_of_day" in with_cal.columns
assert "day_of_week" in with_cal.columns
assert "is_weekend" in with_cal.columns
assert "is_holiday" in with_cal.columns
print(f"compute_calendar_features: hour_of_day range=[{with_cal['hour_of_day'].min()}, {with_cal['hour_of_day'].max()}]")
print(f"  day_of_week range=[{with_cal['day_of_week'].min()}, {with_cal['day_of_week'].max()}]")
assert with_cal["is_holiday"].any(), "Jan 1 should be a holiday"

# Test compute_rolling_avg
with_rolling = compute_rolling_avg(with_cal)
assert "rolling_avg_7d" in with_rolling.columns
print(f"compute_rolling_avg: rolling_avg_7d present")

# Test fill_missing_features
filled = fill_missing_features(with_rolling)
assert filled.isnull().sum().sum() == 0
print(f"fill_missing_features: no nulls remain")

# Test validate_feature_ranges
validated = validate_feature_ranges(filled)
assert len(validated) == len(filled)
print(f"validate_feature_ranges: passed ({len(validated)} rows)")

# Test validate_feature_ranges raises on bad data
bad_df = filled.copy()
bad_df.loc[0, "hour_of_day"] = 25
try:
    validate_feature_ranges(bad_df)
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "hour_of_day" in str(e)
    print(f"validate_feature_ranges: correctly raises on hour_of_day=25")

bad_df2 = filled.copy()
bad_df2.loc[0, "day_of_week"] = 7
try:
    validate_feature_ranges(bad_df2)
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "day_of_week" in str(e)
    print(f"validate_feature_ranges: correctly raises on day_of_week=7")

bad_df3 = filled.copy()
bad_df3.loc[0, "abandonment_rate_lag_1h"] = 1.5
try:
    validate_feature_ranges(bad_df3)
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "abandonment_rate_lag_1h" in str(e)
    print(f"validate_feature_ranges: correctly raises on abandonment_rate_lag_1h=1.5")

print("\nAll smoke tests passed!")
