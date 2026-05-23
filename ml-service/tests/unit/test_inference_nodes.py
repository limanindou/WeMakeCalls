"""Unit tests for inference pipeline nodes."""

import os
import pickle
import time

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from wemakecalls.pipelines.inference.nodes import (
    build_prediction_batch,
    load_latest_model,
    run_inference,
)


class TestLoadLatestModel:
    """Tests for load_latest_model node."""

    def test_selects_most_recently_modified_file_by_mtime(self, tmp_path):
        """load_latest_model selects the most recently modified file by mtime."""
        # Create multiple model files with different mtimes
        older_model = LinearRegression()
        older_model.fit([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]], [5])
        older_path = tmp_path / "linear_regression_20240101_120000.pkl"
        with open(older_path, "wb") as f:
            pickle.dump(older_model, f)

        # Set older mtime using os.utime
        os.utime(older_path, (1000000, 1000000))

        newer_model = LinearRegression()
        newer_model.fit([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]], [10])
        newer_path = tmp_path / "linear_regression_20240201_120000.pkl"
        with open(newer_path, "wb") as f:
            pickle.dump(newer_model, f)

        # Set newer mtime
        os.utime(newer_path, (2000000, 2000000))

        model, model_type = load_latest_model(tmp_path)

        # The newer model should be loaded (predicts ~10 for the training input)
        assert model_type == "linear_regression"
        # Verify it loaded the newer file by checking prediction
        prediction = model.predict([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]])
        assert abs(prediction[0] - 10.0) < 0.01

    def test_raises_filenotfounderror_when_directory_is_empty(self, tmp_path):
        """load_latest_model raises FileNotFoundError when data/06_models/ is empty."""
        # Create a .gitkeep file (should be ignored)
        (tmp_path / ".gitkeep").touch()

        with pytest.raises(FileNotFoundError, match="No model artifacts found"):
            load_latest_model(tmp_path)

    def test_raises_runtimeerror_when_model_artifact_is_corrupted(self, tmp_path):
        """load_latest_model raises RuntimeError when model artifact is corrupted."""
        # Create a corrupt pickle file that will fail on predict
        corrupt_path = tmp_path / "linear_regression_20240101_120000.pkl"
        with open(corrupt_path, "wb") as f:
            # Write a valid pickle but not a model — it won't have a predict method
            pickle.dump({"not": "a model"}, f)

        with pytest.raises(RuntimeError, match="corrupted"):
            load_latest_model(tmp_path)


class TestBuildPredictionBatch:
    """Tests for build_prediction_batch node."""

    def test_raises_filenotfounderror_when_features_dataframe_is_empty(self):
        """build_prediction_batch raises FileNotFoundError when features DataFrame is empty."""
        empty_df = pd.DataFrame(columns=["hour_bucket", "calls_lag_1h"])

        with pytest.raises(FileNotFoundError, match="empty"):
            build_prediction_batch(empty_df)


class TestRunInference:
    """Tests for run_inference node."""

    def test_returns_non_negative_integer(self):
        """run_inference returns a non-negative integer."""
        # Train a simple LinearRegression model
        X_train = np.random.rand(50, 11)
        y_train = np.random.rand(50) * 100

        model = LinearRegression()
        model.fit(X_train, y_train)

        # Create a single-row batch
        batch = pd.DataFrame(
            [np.random.rand(11)],
            columns=[
                "calls_lag_1h",
                "calls_lag_2h",
                "calls_lag_24h",
                "calls_lag_168h",
                "hour_of_day",
                "day_of_week",
                "is_weekend",
                "is_holiday",
                "rolling_avg_7d",
                "avg_duration_lag_1h",
                "abandonment_rate_lag_1h",
            ],
        )

        result = run_inference(model, batch)

        assert isinstance(result, int)
        assert result >= 0
