"""Feature engineering pipeline definition.

Chains the six feature engineering nodes into a Kedro Pipeline:
    aggregate_hourly → compute_lag_features → compute_calendar_features →
    compute_rolling_avg → fill_missing_features → validate_feature_ranges

The final output is written to the ``feature_vectors`` catalog entry
(data/03_primary/features.parquet).
"""

from kedro.pipeline import Pipeline, node

from .nodes import (
    aggregate_hourly,
    compute_calendar_features,
    compute_lag_features,
    compute_rolling_avg,
    fill_missing_features,
    validate_feature_ranges,
)


def create_pipeline(**kwargs) -> Pipeline:
    """Create the feature engineering pipeline.

    The pipeline reads call log data, aggregates it into hourly buckets,
    computes lag features, calendar features, and rolling averages, fills
    missing values, validates feature ranges, and writes the result to
    ``feature_vectors`` (data/03_primary/features.parquet via the catalog).

    Parameters ``lag_windows`` and ``holidays`` are sourced from
    ``conf/base/parameters.yml``.
    """
    return Pipeline(
        [
            node(
                func=aggregate_hourly,
                inputs="call_logs",
                outputs="hourly_aggregated",
                name="aggregate_hourly",
            ),
            node(
                func=compute_lag_features,
                inputs=["hourly_aggregated", "params:lag_windows"],
                outputs="hourly_with_lags",
                name="compute_lag_features",
            ),
            node(
                func=compute_calendar_features,
                inputs=["hourly_with_lags", "params:holidays"],
                outputs="hourly_with_calendar",
                name="compute_calendar_features",
            ),
            node(
                func=compute_rolling_avg,
                inputs="hourly_with_calendar",
                outputs="hourly_with_rolling",
                name="compute_rolling_avg",
            ),
            node(
                func=fill_missing_features,
                inputs="hourly_with_rolling",
                outputs="features_filled",
                name="fill_missing_features",
            ),
            node(
                func=validate_feature_ranges,
                inputs="features_filled",
                outputs="feature_vectors",
                name="validate_feature_ranges",
            ),
        ]
    )
