"""Unit tests for training pipeline nodes and model factory."""

import logging
import re
from datetime import datetime, timezone

import pandas as pd
import pytest
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from wemakecalls.pipelines.training.model_factory import get_model
from wemakecalls.pipelines.training.nodes import (
    create_target,
    evaluate_model,
    save_model_artifact,
)


class TestGetModel:
    """Tests for model_factory.get_model instantiation."""

    def test_catboost_instantiation(self):
        """get_model('catboost') returns a CatBoostRegressor instance."""
        model = get_model("catboost")
        assert isinstance(model, CatBoostRegressor)

    def test_xgboost_instantiation(self):
        """get_model('xgboost') returns an XGBRegressor instance."""
        model = get_model("xgboost")
        assert isinstance(model, XGBRegressor)

    def test_lightgbm_instantiation(self):
        """get_model('lightgbm') returns an LGBMRegressor instance."""
        model = get_model("lightgbm")
        assert isinstance(model, LGBMRegressor)

    def test_random_forest_instantiation(self):
        """get_model('random_forest') returns a RandomForestRegressor instance."""
        model = get_model("random_forest")
        assert isinstance(model, RandomForestRegressor)

    def test_linear_regression_instantiation(self):
        """get_model('linear_regression') returns a LinearRegression instance."""
        model = get_model("linear_regression")
        assert isinstance(model, LinearRegression)

    def test_unsupported_model_type_logs_warning_and_falls_back_to_catboost(self, caplog):
        """Unsupported model_type logs WARNING and falls back to CatBoost."""
        with caplog.at_level(logging.WARNING):
            model = get_model("unsupported_model")

        assert isinstance(model, CatBoostRegressor)
        assert any("Unsupported model_type" in record.message for record in caplog.records)
        assert any("unsupported_model" in record.message for record in caplog.records)


class TestCreateTarget:
    """Tests for create_target node."""

    def test_raises_valueerror_when_fewer_than_168_rows_remain(self):
        """create_target raises ValueError when fewer than 168 rows remain after target creation."""
        # Create a DataFrame with exactly 168 rows — after dropping the last row,
        # only 167 remain, which is below the 168 minimum.
        features = pd.DataFrame(
            {
                "call_count": list(range(168)),
                "hour_bucket": pd.date_range("2024-01-01", periods=168, freq="h"),
            }
        )

        with pytest.raises(ValueError, match="168"):
            create_target(features)

    def test_does_not_raise_when_exactly_168_rows_remain(self):
        """create_target does not raise when exactly 168 rows remain after target creation."""
        # 169 rows → after dropping last row, 168 remain (exactly the minimum)
        features = pd.DataFrame(
            {
                "call_count": list(range(169)),
                "hour_bucket": pd.date_range("2024-01-01", periods=169, freq="h"),
            }
        )

        result = create_target(features)
        assert len(result) == 168


class TestSaveModelArtifact:
    """Tests for save_model_artifact node."""

    def test_artifact_filename_matches_expected_format_pkl(self, tmp_path, monkeypatch):
        """Artifact filename matches <model_type>_<YYYYMMDD_HHMMSS>.pkl format for non-CatBoost."""
        # Monkeypatch the models directory to use tmp_path
        monkeypatch.chdir(tmp_path)

        model = LinearRegression()
        trained_at = datetime(2024, 3, 15, 14, 30, 45, tzinfo=timezone.utc)

        artifact_path = save_model_artifact(model, "linear_regression", trained_at)

        # Verify filename format
        expected_pattern = r"^linear_regression_20240315_143045\.pkl$"
        assert re.match(expected_pattern, artifact_path.name)

    def test_artifact_filename_matches_expected_format_cbm(self, tmp_path, monkeypatch):
        """Artifact filename matches <model_type>_<YYYYMMDD_HHMMSS>.cbm format for CatBoost."""
        monkeypatch.chdir(tmp_path)

        model = CatBoostRegressor(verbose=0, iterations=1)
        # CatBoost needs to be fitted before saving
        X_train = pd.DataFrame({"feature1": [1, 2, 3], "feature2": [4, 5, 6]})
        y_train = pd.Series([10, 20, 30])
        model.fit(X_train, y_train)

        trained_at = datetime(2024, 6, 20, 9, 15, 0, tzinfo=timezone.utc)

        artifact_path = save_model_artifact(model, "catboost", trained_at)

        expected_pattern = r"^catboost_20240620_091500\.cbm$"
        assert re.match(expected_pattern, artifact_path.name)


class TestEvaluateModel:
    """Tests for evaluate_model node."""

    def test_training_metrics_logged_after_evaluation(self, caplog):
        """Training metrics (MAE, RMSE, MAPE) are logged after training completes."""
        # Train a simple model
        X_train = pd.DataFrame(
            {"feature1": list(range(50)), "feature2": list(range(50, 100))}
        )
        y_train = pd.Series(list(range(50)))

        model = LinearRegression()
        model.fit(X_train, y_train)

        X_test = pd.DataFrame(
            {"feature1": list(range(50, 60)), "feature2": list(range(100, 110))}
        )
        y_test = pd.Series(list(range(50, 60)))

        with caplog.at_level(logging.INFO):
            metrics = evaluate_model(model, X_test, y_test)

        # Verify metrics dict contains expected keys
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics

        # Verify all metrics are non-negative
        assert metrics["mae"] >= 0.0
        assert metrics["rmse"] >= 0.0
        assert metrics["mape"] >= 0.0

        # Verify metrics are logged
        assert any("MAE=" in record.message for record in caplog.records)
        assert any("RMSE=" in record.message for record in caplog.records)
        assert any("MAPE=" in record.message for record in caplog.records)
