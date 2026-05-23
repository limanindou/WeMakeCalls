"""
Property-based tests for the Feature Engineering Pipeline.

Tests Properties 5, 6, 7, 8, 9, and 10 from the design document using Hypothesis.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.pandas import column, data_frames

from wemakecalls.pipelines.feature_engineering.nodes import (
    aggregate_hourly,
    compute_calendar_features,
    compute_lag_features,
    fill_missing_features,
    validate_feature_ranges,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@st.composite
def call_log_dataframe(draw: st.DrawFn) -> pd.DataFrame:
    """Generate a DataFrame with started_at, duration_seconds, and abandoned columns.

    Produces 1-50 rows with valid call log data suitable for aggregate_hourly.
    """
    n_rows = draw(st.integers(min_value=1, max_value=50))

    started_at_values = [
        draw(st.datetimes(
            min_value=pd.Timestamp("2024-01-01").to_pydatetime(),
            max_value=pd.Timestamp("2024-01-07 23:59:59").to_pydatetime(),
        ))
        for _ in range(n_rows)
    ]

    duration_values = [
        draw(st.integers(min_value=0, max_value=1800))
        for _ in range(n_rows)
    ]

    abandoned_values = [
        draw(st.booleans())
        for _ in range(n_rows)
    ]

    df = pd.DataFrame({
        "started_at": pd.to_datetime(started_at_values),
        "duration_seconds": duration_values,
        "abandoned": abandoned_values,
    })

    return df


@st.composite
def hourly_dataframe(draw: st.DrawFn) -> pd.DataFrame:
    """Generate a DataFrame resembling output of aggregate_hourly.

    Produces consecutive hourly rows with call_count, avg_duration,
    and abandonment_rate columns.
    """
    n_rows = draw(st.integers(min_value=2, max_value=50))

    base_time = pd.Timestamp("2024-01-01 00:00:00")
    hour_buckets = [base_time + pd.Timedelta(hours=i) for i in range(n_rows)]

    call_counts = [
        draw(st.integers(min_value=1, max_value=100))
        for _ in range(n_rows)
    ]

    avg_durations = [
        draw(st.floats(min_value=30.0, max_value=1800.0, allow_nan=False, allow_infinity=False))
        for _ in range(n_rows)
    ]

    abandonment_rates = [
        draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        for _ in range(n_rows)
    ]

    df = pd.DataFrame({
        "hour_bucket": hour_buckets,
        "call_count": call_counts,
        "avg_duration": avg_durations,
        "abandonment_rate": abandonment_rates,
    })

    return df


@st.composite
def feature_vector_dataframe(draw: st.DrawFn) -> pd.DataFrame:
    """Generate a complete feature vector DataFrame with all expected columns.

    Produces valid data that should pass validate_feature_ranges.
    """
    n_rows = draw(st.integers(min_value=1, max_value=50))

    base_time = pd.Timestamp("2024-01-01 00:00:00")
    hour_buckets = [base_time + pd.Timedelta(hours=i) for i in range(n_rows)]

    df = pd.DataFrame({
        "hour_bucket": hour_buckets,
        "call_count": [draw(st.integers(min_value=0, max_value=200)) for _ in range(n_rows)],
        "avg_duration": [draw(st.floats(min_value=0.0, max_value=1800.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "abandonment_rate": [draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "calls_lag_1h": [draw(st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "calls_lag_2h": [draw(st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "calls_lag_24h": [draw(st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "calls_lag_168h": [draw(st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "hour_of_day": [draw(st.integers(min_value=0, max_value=23)) for _ in range(n_rows)],
        "day_of_week": [draw(st.integers(min_value=0, max_value=6)) for _ in range(n_rows)],
        "is_weekend": [draw(st.booleans()) for _ in range(n_rows)],
        "is_holiday": [draw(st.booleans()) for _ in range(n_rows)],
        "rolling_avg_7d": [draw(st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "avg_duration_lag_1h": [draw(st.floats(min_value=0.0, max_value=1800.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
        "abandonment_rate_lag_1h": [draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)) for _ in range(n_rows)],
    })

    return df


# ---------------------------------------------------------------------------
# Property 5: Hourly aggregation produces one row per hour bucket
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=call_log_dataframe())
def test_property_5_hourly_aggregation_one_row_per_bucket(
    df: pd.DataFrame,
) -> None:
    """
    Property 5: Hourly aggregation produces one row per hour bucket.

    For any set of call log records, aggregate_hourly produces exactly one
    output row per distinct hour bucket and call_count equals the number of
    input records truncating to that hour.

    **Validates: Requirements 3.1**
    """
    result = aggregate_hourly(df)

    # Compute expected hour buckets from input
    expected_buckets = df["started_at"].dt.floor("h")
    expected_counts = expected_buckets.value_counts()

    # One row per distinct hour bucket
    assert len(result) == len(expected_counts), (
        f"Expected {len(expected_counts)} distinct hour buckets, "
        f"got {len(result)} rows"
    )

    # Each hour_bucket appears exactly once
    assert result["hour_bucket"].is_unique, (
        "hour_bucket column contains duplicate values"
    )

    # call_count for each bucket equals the number of input records in that bucket
    for _, row in result.iterrows():
        bucket = row["hour_bucket"]
        expected_count = expected_counts[bucket]
        assert row["call_count"] == expected_count, (
            f"For bucket {bucket}: expected call_count={expected_count}, "
            f"got {row['call_count']}"
        )


# ---------------------------------------------------------------------------
# Property 6: Lag features match prior hour bucket counts
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=hourly_dataframe())
def test_property_6_lag_features_match_prior_counts(
    df: pd.DataFrame,
) -> None:
    """
    Property 6: Lag features match prior hour bucket call counts.

    For any hourly call series with sufficient history, calls_lag_Nh for
    row i equals call_count at offset i - N; when prior row does not exist,
    lag value is 0.

    **Validates: Requirements 3.2, 3.7**
    """
    lag_windows = [1, 2, 24, 168]
    result = compute_lag_features(df, lag_windows=lag_windows)

    for window in lag_windows:
        col_name = f"calls_lag_{window}h"
        assert col_name in result.columns, (
            f"Expected column '{col_name}' not found in result"
        )

        for i in range(len(result)):
            expected_value = (
                result["call_count"].iloc[i - window]
                if i >= window
                else 0
            )
            actual_value = result[col_name].iloc[i]
            assert actual_value == expected_value, (
                f"Row {i}, {col_name}: expected {expected_value}, "
                f"got {actual_value}"
            )


# ---------------------------------------------------------------------------
# Property 7: No null values after fill
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=hourly_dataframe())
def test_property_7_no_null_values_after_fill(
    df: pd.DataFrame,
) -> None:
    """
    Property 7: Feature vector contains no null values.

    For any feature vector dataset produced by the pipeline, every feature
    column contains zero null values after fill logic is applied.

    **Validates: Requirements 3.7, 3.10**
    """
    # Run through the pipeline steps that can introduce NaN values
    lag_windows = [1, 2, 24, 168]
    with_lags = compute_lag_features(df, lag_windows=lag_windows)

    holidays = ["2024-01-01", "2024-12-25"]
    with_calendar = compute_calendar_features(with_lags, holidays=holidays)

    # Apply fill logic
    filled = fill_missing_features(with_calendar)

    # Assert no null values in any column
    null_counts = filled.isnull().sum()
    assert null_counts.sum() == 0, (
        f"Null values remain after fill_missing_features: "
        f"{null_counts[null_counts > 0].to_dict()}"
    )


# ---------------------------------------------------------------------------
# Property 8: Feature column range invariants
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=feature_vector_dataframe())
def test_property_8_feature_column_range_invariants(
    df: pd.DataFrame,
) -> None:
    """
    Property 8: Feature column range invariants.

    For any feature vector dataset, hour_of_day is in [0,23],
    day_of_week is in [0,6], abandonment_rate_lag_1h is in [0.0,1.0].

    **Validates: Requirements 8.2, 8.3, 8.4**
    """
    # validate_feature_ranges should NOT raise for valid data
    result = validate_feature_ranges(df)

    # The function returns the DataFrame unchanged
    assert result is not None
    assert len(result) == len(df)

    # Double-check the ranges hold
    assert (result["hour_of_day"] >= 0).all() and (result["hour_of_day"] <= 23).all()
    assert (result["day_of_week"] >= 0).all() and (result["day_of_week"] <= 6).all()
    assert (result["abandonment_rate_lag_1h"] >= 0.0).all() and (result["abandonment_rate_lag_1h"] <= 1.0).all()


# ---------------------------------------------------------------------------
# Property 9: Calendar features derived from timestamps
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=hourly_dataframe())
def test_property_9_calendar_features_derived_from_timestamps(
    df: pd.DataFrame,
) -> None:
    """
    Property 9: Calendar features are correctly derived from timestamps.

    For any Hour_Bucket timestamp, hour_of_day equals the hour component,
    day_of_week equals ISO weekday minus 1, is_weekend is True iff
    day_of_week in {5,6}, is_holiday is True iff date is in the holidays list.

    **Validates: Requirements 3.3**
    """
    holidays = ["2024-01-01", "2024-01-06", "2024-12-25"]
    holiday_dates = set(pd.to_datetime(holidays).date)

    result = compute_calendar_features(df, holidays=holidays)

    for i in range(len(result)):
        bucket = result["hour_bucket"].iloc[i]

        # hour_of_day equals the hour component
        expected_hour = bucket.hour
        assert result["hour_of_day"].iloc[i] == expected_hour, (
            f"Row {i}: expected hour_of_day={expected_hour}, "
            f"got {result['hour_of_day'].iloc[i]}"
        )

        # day_of_week equals ISO weekday minus 1 (Monday=0, Sunday=6)
        expected_dow = bucket.dayofweek  # pandas: Monday=0, Sunday=6
        assert result["day_of_week"].iloc[i] == expected_dow, (
            f"Row {i}: expected day_of_week={expected_dow}, "
            f"got {result['day_of_week'].iloc[i]}"
        )

        # is_weekend is True iff day_of_week in {5, 6}
        expected_weekend = expected_dow in {5, 6}
        assert result["is_weekend"].iloc[i] == expected_weekend, (
            f"Row {i}: expected is_weekend={expected_weekend}, "
            f"got {result['is_weekend'].iloc[i]}"
        )

        # is_holiday is True iff date is in the holidays list
        expected_holiday = bucket.date() in holiday_dates
        assert result["is_holiday"].iloc[i] == expected_holiday, (
            f"Row {i}: expected is_holiday={expected_holiday}, "
            f"got {result['is_holiday'].iloc[i]}"
        )


# ---------------------------------------------------------------------------
# Property 10: Parquet round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=feature_vector_dataframe())
def test_property_10_parquet_round_trip(
    df: pd.DataFrame,
) -> None:
    """
    Property 10: Feature vector Parquet round-trip.

    For any feature vector DataFrame, writing to Parquet with PyArrow and
    reading back produces a DataFrame with identical column names, dtypes,
    row count, and cell values.

    **Validates: Requirements 3.9**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        parquet_path = Path(tmp_dir) / "features.parquet"

        # Write to Parquet with PyArrow
        df.to_parquet(parquet_path, engine="pyarrow", index=False)

        # Read back
        loaded = pd.read_parquet(parquet_path, engine="pyarrow")

    # Identical column names
    assert list(loaded.columns) == list(df.columns), (
        f"Column names differ: {list(loaded.columns)} != {list(df.columns)}"
    )

    # Identical row count
    assert len(loaded) == len(df), (
        f"Row count differs: {len(loaded)} != {len(df)}"
    )

    # Identical dtypes
    for col in df.columns:
        assert loaded[col].dtype == df[col].dtype, (
            f"Column '{col}' dtype differs: {loaded[col].dtype} != {df[col].dtype}"
        )

    # Identical cell values
    pd.testing.assert_frame_equal(loaded, df)
