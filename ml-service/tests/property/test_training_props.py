"""
Property-based tests for the Training Pipeline.

Tests Properties 11, 12, 13, and 14 from the design document using Hypothesis.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from wemakecalls.pipelines.training.nodes import (
    create_target,
    evaluate_model,
    temporal_split,
    train_model,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def hourly_call_series(draw: st.DrawFn, min_rows: int = 169, max_rows: int = 300) -> pd.DataFrame:
    """Generate a DataFrame with call_count and hour_bucket columns.

    Produces N rows (N >= min_rows) with consecutive hourly timestamps and
    positive integer call counts. The minimum of 169 ensures that after
    dropping the last row (N-1 = 168), the create_target minimum check passes.
    """
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))

    base_time = pd.Timestamp("2024-01-01 00:00:00")
    hour_buckets = [base_time + pd.Timedelta(hours=i) for i in range(n_rows)]

    call_counts = [
        draw(st.integers(min_value=1, max_value=200))
        for _ in range(n_rows)
    ]

    df = pd.DataFrame({
        "hour_bucket": hour_buckets,
        "call_count": call_counts,
    })

    return df


@st.composite
def feature_dataset_with_target(
    draw: st.DrawFn, min_rows: int = 170, max_rows: int = 300
) -> pd.DataFrame:
    """Generate a feature vector dataset with next_hour_calls target column.

    Produces N rows with feature columns and a target column suitable for
    temporal_split. Uses a single random seed to generate bulk data efficiently.
    """
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    rng = np.random.default_rng(seed)

    base_time = pd.Timestamp("2024-01-01 00:00:00")
    hour_buckets = pd.date_range(start=base_time, periods=n_rows, freq="h")

    df = pd.DataFrame({
        "hour_bucket": hour_buckets,
        "call_count": rng.integers(1, 201, size=n_rows),
        "next_hour_calls": rng.integers(1, 201, size=n_rows),
        "calls_lag_1h": rng.uniform(0.0, 200.0, size=n_rows),
        "calls_lag_2h": rng.uniform(0.0, 200.0, size=n_rows),
        "calls_lag_24h": rng.uniform(0.0, 200.0, size=n_rows),
        "calls_lag_168h": rng.uniform(0.0, 200.0, size=n_rows),
        "hour_of_day": rng.integers(0, 24, size=n_rows),
        "day_of_week": rng.integers(0, 7, size=n_rows),
        "is_weekend": rng.choice([True, False], size=n_rows),
        "is_holiday": rng.choice([True, False], size=n_rows),
        "rolling_avg_7d": rng.uniform(0.0, 200.0, size=n_rows),
        "avg_duration_lag_1h": rng.uniform(0.0, 1800.0, size=n_rows),
        "abandonment_rate_lag_1h": rng.uniform(0.0, 1.0, size=n_rows),
    })

    return df


# ---------------------------------------------------------------------------
# Property 11: Training target creation
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(df=hourly_call_series())
def test_property_11_training_target_creation(df: pd.DataFrame) -> None:
    """
    Property 11: Training target creation.

    For any hourly call series of length N >= 2, next_hour_calls for row i
    equals call_count of row i+1, and the output has exactly N-1 rows.

    **Validates: Requirements 4.1**
    """
    n = len(df)

    result = create_target(df)

    # Output has exactly N-1 rows
    assert len(result) == n - 1, (
        f"Expected {n - 1} rows after target creation, got {len(result)}"
    )

    # next_hour_calls for row i equals call_count of row i+1 in the original
    for i in range(len(result)):
        expected_target = df["call_count"].iloc[i + 1]
        actual_target = result["next_hour_calls"].iloc[i]
        assert actual_target == expected_target, (
            f"Row {i}: expected next_hour_calls={expected_target}, "
            f"got {actual_target}"
        )


# ---------------------------------------------------------------------------
# Property 12: Temporal train/test split preserves order
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
@given(
    df=feature_dataset_with_target(),
    ratio=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
)
def test_property_12_temporal_train_test_split(
    df: pd.DataFrame, ratio: float
) -> None:
    """
    Property 12: Temporal train/test split preserves order.

    For any feature vector dataset of length N and split ratio r in (0.0, 1.0),
    the training set is the first floor(N*r) rows and the test set is the
    remaining rows, with no overlap and temporal order preserved.

    **Validates: Requirements 4.2**
    """
    n = len(df)
    expected_train_size = math.floor(n * ratio)
    expected_test_size = n - expected_train_size

    X_train, X_test, y_train, y_test = temporal_split(df, ratio)

    # Training set has floor(N*r) rows
    assert len(X_train) == expected_train_size, (
        f"Expected train size={expected_train_size}, got {len(X_train)}"
    )

    # Test set has remaining rows
    assert len(X_test) == expected_test_size, (
        f"Expected test size={expected_test_size}, got {len(X_test)}"
    )

    # No overlap: total rows equals N
    assert len(X_train) + len(X_test) == n, (
        f"Train ({len(X_train)}) + Test ({len(X_test)}) != N ({n})"
    )

    # Target arrays match sizes
    assert len(y_train) == expected_train_size
    assert len(y_test) == expected_test_size

    # Temporal order preserved: train targets come from first portion,
    # test targets come from second portion of the original target column
    original_target = df["next_hour_calls"].reset_index(drop=True)
    pd.testing.assert_series_equal(
        y_train, original_target.iloc[:expected_train_size].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        y_test, original_target.iloc[expected_train_size:].reset_index(drop=True),
        check_names=False,
    )


# ---------------------------------------------------------------------------
# Property 13: Evaluation metrics are non-negative
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
@given(df=feature_dataset_with_target(min_rows=170, max_rows=300))
def test_property_13_evaluation_metrics_non_negative(df: pd.DataFrame) -> None:
    """
    Property 13: Evaluation metrics are non-negative.

    For any trained model and test set, MAE, RMSE, and MAPE are all
    non-negative floats.

    **Validates: Requirements 4.6**
    """
    # Split the data
    X_train, X_test, y_train, y_test = temporal_split(df, ratio=0.8)

    # Train a lightweight linear_regression model (fast and deterministic)
    model = train_model(X_train, y_train, model_type="linear_regression", params={})

    # Evaluate
    metrics = evaluate_model(model, X_test, y_test)

    # All metrics are non-negative floats
    assert isinstance(metrics["mae"], float), f"MAE is not a float: {type(metrics['mae'])}"
    assert isinstance(metrics["rmse"], float), f"RMSE is not a float: {type(metrics['rmse'])}"
    assert isinstance(metrics["mape"], float), f"MAPE is not a float: {type(metrics['mape'])}"

    assert metrics["mae"] >= 0.0, f"MAE is negative: {metrics['mae']}"
    assert metrics["rmse"] >= 0.0, f"RMSE is negative: {metrics['rmse']}"
    assert metrics["mape"] >= 0.0, f"MAPE is negative: {metrics['mape']}"


# ---------------------------------------------------------------------------
# Property 14: Deterministic model reproducibility
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
@given(df=feature_dataset_with_target(min_rows=170, max_rows=300))
def test_property_14_deterministic_model_reproducibility(df: pd.DataFrame) -> None:
    """
    Property 14: Deterministic model reproducibility.

    For any fixed feature vector dataset and a deterministic model type
    (linear_regression), running training twice produces two artifacts
    whose MAE values differ by no more than 1% in relative terms.

    **Validates: Requirements 4.9**
    """
    # Split the data (same split both times since data is fixed)
    X_train, X_test, y_train, y_test = temporal_split(df, ratio=0.8)

    # Train the same deterministic model twice
    model_1 = train_model(X_train, y_train, model_type="linear_regression", params={})
    model_2 = train_model(X_train, y_train, model_type="linear_regression", params={})

    # Evaluate both models on the same test set
    metrics_1 = evaluate_model(model_1, X_test, y_test)
    metrics_2 = evaluate_model(model_2, X_test, y_test)

    mae_1 = metrics_1["mae"]
    mae_2 = metrics_2["mae"]

    # MAE values differ by no more than 1% in relative terms
    if mae_1 == 0.0 and mae_2 == 0.0:
        # Both zero — perfectly reproducible
        pass
    elif mae_1 == 0.0 or mae_2 == 0.0:
        # One is zero, the other is not — check absolute difference is tiny
        assert abs(mae_1 - mae_2) < 1e-10, (
            f"MAE values differ: {mae_1} vs {mae_2}"
        )
    else:
        relative_diff = abs(mae_1 - mae_2) / max(mae_1, mae_2)
        assert relative_diff <= 0.01, (
            f"MAE values differ by more than 1%: "
            f"MAE_1={mae_1}, MAE_2={mae_2}, relative_diff={relative_diff:.4f}"
        )
