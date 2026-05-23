"""
Property-based tests for the Inference Pipeline.

Tests Properties 15 and 16 from the design document using Hypothesis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sklearn.linear_model import LinearRegression

from wemakecalls.pipelines.inference.nodes import (
    FEATURE_COLUMNS,
    build_prediction_batch,
    run_inference,
)

# ---------------------------------------------------------------------------
# Module-level trained model fixture (train once, reuse across all examples)
# ---------------------------------------------------------------------------

_TRAINED_MODEL: LinearRegression | None = None


def _get_trained_model() -> LinearRegression:
    """Return a pre-trained LinearRegression model (trained once at module level)."""
    global _TRAINED_MODEL
    if _TRAINED_MODEL is None:
        rng = np.random.default_rng(42)
        # Generate synthetic training data with 11 features
        X_train = rng.uniform(0.0, 100.0, size=(200, len(FEATURE_COLUMNS)))
        y_train = rng.integers(0, 200, size=200).astype(float)
        model = LinearRegression()
        model.fit(X_train, y_train)
        _TRAINED_MODEL = model
    return _TRAINED_MODEL


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def valid_feature_row(draw: st.DrawFn) -> pd.DataFrame:
    """Generate a single-row DataFrame with all 11 feature columns, non-null."""
    data = {}
    for col in FEATURE_COLUMNS:
        if col in ("hour_of_day",):
            data[col] = [draw(st.integers(min_value=0, max_value=23))]
        elif col in ("day_of_week",):
            data[col] = [draw(st.integers(min_value=0, max_value=6))]
        elif col in ("is_weekend", "is_holiday"):
            data[col] = [draw(st.booleans())]
        elif col == "abandonment_rate_lag_1h":
            data[col] = [draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))]
        else:
            data[col] = [draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))]

    return pd.DataFrame(data, columns=FEATURE_COLUMNS)


@st.composite
def feature_df_with_nulls(draw: st.DrawFn) -> pd.DataFrame:
    """Generate a DataFrame with hour_bucket and 11 feature columns, some with NaN values.

    Produces 1-5 rows where at least one numeric feature column has a NaN value.
    Boolean columns (is_weekend, is_holiday) are excluded from null injection
    because pandas cannot store NaN in bool dtype columns.
    """
    n_rows = draw(st.integers(min_value=1, max_value=5))

    # Generate hour_bucket timestamps (consecutive hours)
    base_time = pd.Timestamp("2024-06-15 10:00:00")
    hour_buckets = [base_time + pd.Timedelta(hours=i) for i in range(n_rows)]

    data: dict[str, list] = {"hour_bucket": hour_buckets}

    # Numeric feature columns that can hold NaN
    numeric_feature_cols = [
        col for col in FEATURE_COLUMNS if col not in ("is_weekend", "is_holiday")
    ]

    for col in FEATURE_COLUMNS:
        col_values = []
        for _ in range(n_rows):
            if col in ("hour_of_day",):
                val = float(draw(st.integers(min_value=0, max_value=23)))
            elif col in ("day_of_week",):
                val = float(draw(st.integers(min_value=0, max_value=6)))
            elif col in ("is_weekend", "is_holiday"):
                val = draw(st.booleans())
            elif col == "abandonment_rate_lag_1h":
                val = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
            else:
                val = draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False))
            col_values.append(val)
        data[col] = col_values

    df = pd.DataFrame(data)

    # Introduce at least one NaN in a numeric feature column for a random row
    null_col = draw(st.sampled_from(numeric_feature_cols))
    null_row = draw(st.integers(min_value=0, max_value=n_rows - 1))
    df.loc[null_row, null_col] = np.nan

    # Optionally introduce more NaN values in numeric columns
    extra_nulls = draw(st.integers(min_value=0, max_value=min(3, n_rows * len(numeric_feature_cols) - 1)))
    for _ in range(extra_nulls):
        r = draw(st.integers(min_value=0, max_value=n_rows - 1))
        c = draw(st.sampled_from(numeric_feature_cols))
        df.loc[r, c] = np.nan

    return df


# ---------------------------------------------------------------------------
# Property 15: Inference returns non-negative integer
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(batch=valid_feature_row())
def test_property_15_inference_returns_non_negative_integer(batch: pd.DataFrame) -> None:
    """
    Property 15: Inference returns non-negative integer.

    For any valid feature vector row with all 11 feature columns present and
    non-null, run_inference returns a single non-negative integer.

    **Validates: Requirements 5.4**
    """
    model = _get_trained_model()

    result = run_inference(model, batch)

    # Result is an integer
    assert isinstance(result, int), (
        f"Expected int, got {type(result).__name__}: {result}"
    )

    # Result is non-negative
    assert result >= 0, (
        f"Expected non-negative integer, got {result}"
    )


# ---------------------------------------------------------------------------
# Property 16: Null-fill before prediction
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(df=feature_df_with_nulls())
def test_property_16_null_fill_before_prediction(df: pd.DataFrame) -> None:
    """
    Property 16: Inference null-fill before prediction.

    For any Prediction Batch containing null values in one or more feature
    columns, build_prediction_batch replaces all nulls with 0 before calling
    model.predict(); the model never receives a batch containing null values.

    **Validates: Requirements 5.6**
    """
    # Confirm the input has at least one null
    assert df[FEATURE_COLUMNS].isnull().any().any(), (
        "Test precondition failed: input DataFrame should contain at least one null"
    )

    # build_prediction_batch selects the most recent row and fills nulls
    result = build_prediction_batch(df)

    # The output should have no null values in any feature column
    assert not result.isnull().any().any(), (
        f"build_prediction_batch output still contains nulls:\n"
        f"{result.isnull().sum()[result.isnull().sum() > 0].to_dict()}"
    )

    # The output should contain only the 11 feature columns
    assert list(result.columns) == FEATURE_COLUMNS, (
        f"Expected columns {FEATURE_COLUMNS}, got {list(result.columns)}"
    )

    # The output should be a single row
    assert len(result) == 1, (
        f"Expected 1 row, got {len(result)}"
    )
