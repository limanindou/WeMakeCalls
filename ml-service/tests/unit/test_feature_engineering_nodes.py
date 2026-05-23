"""Unit tests for feature engineering pipeline nodes."""

import pandas as pd
import pytest

from wemakecalls.pipelines.feature_engineering.nodes import (
    aggregate_hourly,
    compute_rolling_avg,
    validate_feature_ranges,
)


class TestAggregateHourly:
    """Tests for aggregate_hourly node."""

    def test_produces_one_row_per_distinct_hour_bucket(self):
        """aggregate_hourly produces one row per distinct hour bucket."""
        # Create call logs spanning 3 distinct hours with multiple records each
        call_logs = pd.DataFrame(
            {
                "started_at": pd.to_datetime(
                    [
                        "2024-01-15 08:05:00",
                        "2024-01-15 08:30:00",
                        "2024-01-15 08:55:00",
                        "2024-01-15 09:10:00",
                        "2024-01-15 09:45:00",
                        "2024-01-15 10:20:00",
                    ]
                ),
                "duration_seconds": [120, 200, 300, 150, 180, 90],
                "abandoned": [False, True, False, False, True, False],
            }
        )

        result = aggregate_hourly(call_logs)

        # Should produce exactly 3 rows (one per hour: 08, 09, 10)
        assert len(result) == 3
        assert list(result["hour_bucket"]) == [
            pd.Timestamp("2024-01-15 08:00:00"),
            pd.Timestamp("2024-01-15 09:00:00"),
            pd.Timestamp("2024-01-15 10:00:00"),
        ]
        # Verify call counts match input records per hour
        assert list(result["call_count"]) == [3, 2, 1]


class TestComputeRollingAvg:
    """Tests for compute_rolling_avg node."""

    def test_returns_zero_when_fewer_than_7_prior_same_hour_rows(self):
        """compute_rolling_avg returns 0 when fewer than 7 prior same-hour rows exist."""
        # Create a DataFrame with only 3 rows for the same hour_of_day
        # After fill_missing_features, NaN becomes 0
        hourly = pd.DataFrame(
            {
                "hour_bucket": pd.to_datetime(
                    [
                        "2024-01-01 10:00:00",
                        "2024-01-02 10:00:00",
                        "2024-01-03 10:00:00",
                    ]
                ),
                "call_count": [10, 20, 30],
                "hour_of_day": [10, 10, 10],
            }
        )

        result = compute_rolling_avg(hourly)

        # The first row has no prior same-hour rows, so rolling_avg_7d should be NaN
        # (which would become 0 after fill_missing_features)
        assert pd.isna(result.loc[0, "rolling_avg_7d"])

        # The second row has only 1 prior same-hour row (fewer than 7),
        # but min_periods=1 means it still computes a value from available data
        # The value should be 10.0 (mean of the single prior row)
        assert result.loc[1, "rolling_avg_7d"] == 10.0

        # The third row has only 2 prior same-hour rows (fewer than 7)
        # The value should be mean of [10, 20] = 15.0
        assert result.loc[2, "rolling_avg_7d"] == 15.0


class TestValidateFeatureRanges:
    """Tests for validate_feature_ranges node."""

    def test_raises_error_for_hour_of_day_outside_0_23(self):
        """validate_feature_ranges raises descriptive error for hour_of_day outside [0,23]."""
        features = pd.DataFrame(
            {
                "hour_of_day": [0, 12, 25],
                "day_of_week": [0, 3, 5],
                "abandonment_rate_lag_1h": [0.1, 0.5, 0.3],
            }
        )

        with pytest.raises(ValueError, match="hour_of_day.*outside.*\\[0, 23\\]"):
            validate_feature_ranges(features)

    def test_raises_error_for_day_of_week_outside_0_6(self):
        """validate_feature_ranges raises descriptive error for day_of_week outside [0,6]."""
        features = pd.DataFrame(
            {
                "hour_of_day": [0, 12, 15],
                "day_of_week": [0, 7, 5],
                "abandonment_rate_lag_1h": [0.1, 0.5, 0.3],
            }
        )

        with pytest.raises(ValueError, match="day_of_week.*outside.*\\[0, 6\\]"):
            validate_feature_ranges(features)

    def test_raises_error_for_abandonment_rate_lag_1h_outside_0_1(self):
        """validate_feature_ranges raises descriptive error for abandonment_rate_lag_1h outside [0.0,1.0]."""
        features = pd.DataFrame(
            {
                "hour_of_day": [0, 12, 15],
                "day_of_week": [0, 3, 5],
                "abandonment_rate_lag_1h": [0.1, 1.5, 0.3],
            }
        )

        with pytest.raises(
            ValueError, match="abandonment_rate_lag_1h.*outside.*\\[0\\.0, 1\\.0\\]"
        ):
            validate_feature_ranges(features)


class TestParquetOutput:
    """Tests for Parquet write/read functionality."""

    def test_parquet_output_written_and_readable(self, tmp_path):
        """A DataFrame can be written/read as Parquet using PyArrow to data/03_primary/features.parquet."""
        # Create a feature DataFrame similar to pipeline output
        features = pd.DataFrame(
            {
                "hour_bucket": pd.to_datetime(
                    ["2024-01-15 08:00:00", "2024-01-15 09:00:00"]
                ),
                "call_count": [50, 60],
                "calls_lag_1h": [45.0, 50.0],
                "hour_of_day": [8, 9],
                "day_of_week": [0, 0],
                "is_weekend": [False, False],
                "is_holiday": [False, False],
                "rolling_avg_7d": [48.0, 52.0],
                "avg_duration_lag_1h": [120.5, 130.2],
                "abandonment_rate_lag_1h": [0.05, 0.08],
            }
        )

        # Write to the expected output path structure under tmp_path
        output_dir = tmp_path / "data" / "03_primary"
        output_dir.mkdir(parents=True)
        output_path = output_dir / "features.parquet"

        features.to_parquet(output_path, engine="pyarrow")

        # Verify the file exists and can be read back
        assert output_path.exists()

        loaded = pd.read_parquet(output_path, engine="pyarrow")
        assert len(loaded) == len(features)
        assert list(loaded.columns) == list(features.columns)
        pd.testing.assert_frame_equal(loaded, features)
