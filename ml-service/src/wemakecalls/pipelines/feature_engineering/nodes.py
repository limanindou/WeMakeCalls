"""Feature engineering pipeline node functions.

Pure functions for transforming raw call log data into time-series
feature vectors suitable for model training and inference.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def aggregate_hourly(call_logs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate call log records into hourly buckets.

    Truncates `started_at` to the hour, groups by the resulting hour bucket,
    and computes per-bucket metrics: call_count, avg_duration, and
    abandonment_rate.

    Args:
        call_logs: DataFrame with at least `started_at` (datetime, UTC),
            `duration_seconds` (numeric), and `abandoned` (boolean) columns.

    Returns:
        DataFrame with one row per distinct hour bucket, containing columns:
        `hour_bucket`, `call_count`, `avg_duration`, `abandonment_rate`.
        Sorted by `hour_bucket` ascending.
    """
    df = call_logs.copy()

    # Truncate started_at to the hour
    df["hour_bucket"] = df["started_at"].dt.floor("h")

    # Group by hour bucket and compute aggregates
    grouped = df.groupby("hour_bucket").agg(
        call_count=("started_at", "count"),
        avg_duration=("duration_seconds", "mean"),
        abandonment_rate=("abandoned", "mean"),
    ).reset_index()

    # Sort by hour_bucket ascending
    grouped = grouped.sort_values("hour_bucket").reset_index(drop=True)

    logger.info(
        f"aggregate_hourly: produced {len(grouped)} hourly buckets "
        f"from {len(call_logs)} call log records"
    )

    return grouped


def compute_lag_features(
    hourly: pd.DataFrame, lag_windows: list[int]
) -> pd.DataFrame:
    """Add lag feature columns for call_count, avg_duration, and abandonment_rate.

    For each window N in `lag_windows`, adds a `calls_lag_Nh` column containing
    the `call_count` value from N rows prior. Also adds `avg_duration_lag_1h`
    and `abandonment_rate_lag_1h` columns. Missing history is filled with 0.

    Args:
        hourly: DataFrame produced by `aggregate_hourly`, sorted by `hour_bucket`.
            Must contain `hour_bucket`, `call_count`, `avg_duration`, and
            `abandonment_rate` columns.
        lag_windows: List of lag offsets in hours, e.g. [1, 2, 24, 168].

    Returns:
        DataFrame with additional lag feature columns appended.
    """
    df = hourly.copy()

    # Ensure sorted by hour_bucket
    df = df.sort_values("hour_bucket").reset_index(drop=True)

    # Add calls_lag_Nh columns for each window
    for window in lag_windows:
        df[f"calls_lag_{window}h"] = df["call_count"].shift(window).fillna(0)

    # Add avg_duration_lag_1h and abandonment_rate_lag_1h
    df["avg_duration_lag_1h"] = df["avg_duration"].shift(1).fillna(0)
    df["abandonment_rate_lag_1h"] = df["abandonment_rate"].shift(1).fillna(0)

    logger.info(
        f"compute_lag_features: added lag columns for windows {lag_windows}, "
        f"plus avg_duration_lag_1h and abandonment_rate_lag_1h"
    )

    return df


def compute_calendar_features(
    hourly: pd.DataFrame, holidays: list[str]
) -> pd.DataFrame:
    """Add calendar-based feature columns derived from the hour_bucket timestamp.

    Adds `hour_of_day` (0–23), `day_of_week` (0 Mon – 6 Sun), `is_weekend`
    (True when day_of_week in {5, 6}), and `is_holiday` (True when the date
    component of hour_bucket appears in the holidays list).

    Args:
        hourly: DataFrame with a `hour_bucket` datetime column.
        holidays: List of date strings in "YYYY-MM-DD" format, e.g.
            ["2024-01-01", "2024-12-25"].

    Returns:
        DataFrame with additional calendar feature columns appended.
    """
    df = hourly.copy()

    # Parse holidays into a set of date objects for fast lookup
    holiday_dates = set(pd.to_datetime(holidays).date)

    # Extract calendar features from hour_bucket
    df["hour_of_day"] = df["hour_bucket"].dt.hour
    df["day_of_week"] = df["hour_bucket"].dt.dayofweek  # Monday=0, Sunday=6
    df["is_weekend"] = df["day_of_week"].isin({5, 6})
    df["is_holiday"] = df["hour_bucket"].dt.date.isin(holiday_dates)

    logger.info(
        f"compute_calendar_features: added hour_of_day, day_of_week, "
        f"is_weekend, is_holiday (using {len(holiday_dates)} holiday dates)"
    )

    return df


def compute_rolling_avg(hourly: pd.DataFrame) -> pd.DataFrame:
    """Add rolling_avg_7d column as the mean call_count over 7 prior same-hour rows.

    For each row, computes the mean `call_count` across the 7 rows that share
    the same `hour_of_day` in the 7 calendar days immediately preceding the
    current row's date. Uses a rolling window of size 7 within each hour-of-day
    group, shifted by 1 to exclude the current row.

    Args:
        hourly: DataFrame with `hour_bucket`, `call_count`, and `hour_of_day`
            columns, sorted by `hour_bucket`.

    Returns:
        DataFrame with `rolling_avg_7d` column appended. Missing values
        (insufficient history) are left as NaN for later fill.
    """
    df = hourly.copy()

    # Ensure sorted by hour_bucket
    df = df.sort_values("hour_bucket").reset_index(drop=True)

    # Group by hour_of_day and compute rolling mean of the 7 prior same-hour rows
    # shift(1) ensures we only look at prior rows, not the current one
    df["rolling_avg_7d"] = (
        df.groupby("hour_of_day")["call_count"]
        .transform(lambda x: x.shift(1).rolling(window=7, min_periods=1).mean())
    )

    logger.info("compute_rolling_avg: added rolling_avg_7d column")

    return df


def fill_missing_features(features: pd.DataFrame) -> pd.DataFrame:
    """Fill all NaN values with 0 and assert no nulls remain.

    Args:
        features: DataFrame that may contain NaN values from lag/rolling
            computations where insufficient history exists.

    Returns:
        DataFrame with all NaN values replaced by 0.

    Raises:
        AssertionError: If any null values remain after filling (should not
            happen, but serves as a safety check).
    """
    df = features.fillna(0)

    # Safety assertion — no nulls should remain
    null_counts = df.isnull().sum()
    assert null_counts.sum() == 0, (
        f"Null values remain after fill_missing_features: "
        f"{null_counts[null_counts > 0].to_dict()}"
    )

    logger.info("fill_missing_features: filled all NaN values with 0")

    return df


def validate_feature_ranges(features: pd.DataFrame) -> pd.DataFrame:
    """Validate that feature columns are within expected ranges.

    Asserts:
    - `hour_of_day` values are integers in [0, 23]
    - `day_of_week` values are integers in [0, 6]
    - `abandonment_rate_lag_1h` values are floats in [0.0, 1.0]

    Args:
        features: DataFrame with feature columns to validate.

    Returns:
        The same DataFrame, unmodified, if all validations pass.

    Raises:
        ValueError: If any feature value falls outside its expected range,
            with a descriptive error message identifying the column and
            the offending values.
    """
    # Validate hour_of_day in [0, 23]
    if "hour_of_day" in features.columns:
        invalid_hours = features[
            (features["hour_of_day"] < 0) | (features["hour_of_day"] > 23)
        ]
        if not invalid_hours.empty:
            bad_values = invalid_hours["hour_of_day"].unique().tolist()
            raise ValueError(
                f"hour_of_day contains values outside [0, 23]: {bad_values}"
            )

    # Validate day_of_week in [0, 6]
    if "day_of_week" in features.columns:
        invalid_days = features[
            (features["day_of_week"] < 0) | (features["day_of_week"] > 6)
        ]
        if not invalid_days.empty:
            bad_values = invalid_days["day_of_week"].unique().tolist()
            raise ValueError(
                f"day_of_week contains values outside [0, 6]: {bad_values}"
            )

    # Validate abandonment_rate_lag_1h in [0.0, 1.0]
    if "abandonment_rate_lag_1h" in features.columns:
        invalid_rates = features[
            (features["abandonment_rate_lag_1h"] < 0.0)
            | (features["abandonment_rate_lag_1h"] > 1.0)
        ]
        if not invalid_rates.empty:
            bad_values = invalid_rates["abandonment_rate_lag_1h"].unique().tolist()
            raise ValueError(
                f"abandonment_rate_lag_1h contains values outside [0.0, 1.0]: "
                f"{bad_values}"
            )

    logger.info("validate_feature_ranges: all feature values within expected ranges")

    return features
