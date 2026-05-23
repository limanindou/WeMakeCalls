# Implementation Plan: ML Service

## Overview

This plan implements the full ML Service for WeMakeCalls — a Python 3.12 + Kedro 1.1+ + FastAPI 0.110+ MLOps service. Tasks are ordered to respect dependencies: scaffolding and configuration first, then pipeline implementations in data-flow order (ingestion → feature engineering → training → inference), then the API and infrastructure, and finally the test suite (unit → property-based → integration).

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1"],
      "description": "Project scaffolding — must complete before anything else"
    },
    {
      "wave": 2,
      "tasks": ["2", "9", "11"],
      "description": "Kedro config, startup check, and Dockerfile — all depend only on scaffolding"
    },
    {
      "wave": 3,
      "tasks": ["3", "10"],
      "description": "CSV generator and shared logging utility — independent of each other"
    },
    {
      "wave": 4,
      "tasks": ["4"],
      "description": "Ingestion pipeline — depends on catalog (2), logging (10)"
    },
    {
      "wave": 5,
      "tasks": ["5"],
      "description": "Feature engineering pipeline — depends on ingestion (4)"
    },
    {
      "wave": 6,
      "tasks": ["6"],
      "description": "Training pipeline — depends on feature engineering (5)"
    },
    {
      "wave": 7,
      "tasks": ["7", "8"],
      "description": "Inference pipeline and FastAPI app — both depend on training (6)"
    },
    {
      "wave": 8,
      "tasks": ["12", "13"],
      "description": "Unit tests and property-based tests — depend on all pipeline implementations"
    },
    {
      "wave": 9,
      "tasks": ["14"],
      "description": "Integration tests — depend on all pipelines and the API being complete"
    }
  ]
}
```

## Tasks

- [x] 1. Project scaffolding and configuration
  - [x] 1.1 Create `pyproject.toml` with all exact-version dependencies (Python 3.12, Kedro 1.1+, FastAPI 0.110+, Uvicorn, CatBoost, XGBoost, LightGBM, scikit-learn, pandas, NumPy, PyArrow, SQLAlchemy, psycopg2, joblib, hypothesis, pytest, ruff)
  - [x] 1.2 Create Kedro project entry point: `src/wemakecalls/__init__.py` and `src/wemakecalls/pipeline_registry.py` (stub — registers four pipelines by name: `ingestion`, `feature_engineering`, `training`, `inference`)
  - [x] 1.3 Create all `__init__.py` files for sub-packages: `src/wemakecalls/pipelines/`, `src/wemakecalls/pipelines/ingestion/`, `src/wemakecalls/pipelines/feature_engineering/`, `src/wemakecalls/pipelines/training/`, `src/wemakecalls/pipelines/inference/`
  - [x] 1.4 Create directory skeleton: `conf/base/`, `data/01_raw/`, `data/03_primary/`, `data/06_models/`, `data/07_model_output/`, `entrypoints/`, `logs/`, `tests/unit/`, `tests/property/`, `tests/integration/`
  - [x] 1.5 Create `.gitkeep` files in each empty `data/` subdirectory so they are tracked by git

- [x] 2. Kedro catalog and parameters configuration
  - [x] 2.1 Create `conf/base/catalog.yml` defining named datasets: `raw_call_logs` (pandas.CSVDataset, `data/01_raw/call_history_${year}.csv`), `feature_vectors` (pandas.ParquetDataset with PyArrow engine, `data/03_primary/features.parquet`), `model_artifact` (pickle.PickleDataset with joblib backend, `data/06_models/model.pkl`), `prediction_output` (pandas.ParquetDataset, `data/07_model_output/predictions.parquet`)
  - [x] 2.2 Create `conf/base/parameters.yml` with keys: `model_type: catboost`, `lag_windows: [1, 2, 24, 168]`, `train_test_split_ratio: 0.8`, `inference_interval_minutes: 60`, and `holidays` list containing at least `2024-01-01` and `2024-12-25`

- [x] 3. CSV Generator implementation
  - [x] 3.1 Implement `src/wemakecalls/pipelines/csv_generator.py` with `generate_call_logs(start_date, end_date, row_count, output_dir)` function that: produces exactly the 8 required columns in order (`call_id`, `datetime`, `duration_seconds`, `queue_name`, `agent_id`, `wait_time_seconds`, `abandoned`, `hangup_reason`), uses a weighted hourly distribution (higher weights 08:00–18:00), draws `duration_seconds` from a log-normal distribution clipped to [30, 1800] for non-abandoned calls, sets `duration_seconds=0` and `hangup_reason="Call Dropped"` for abandoned rows, assigns `queue_name` from `{billing, support, sales, technical}`, assigns `agent_id` from `A01`–`A20`, assigns `hangup_reason` from the 5-value fixed set, writes to `data/01_raw/call_history_YYYY.csv`, emits a WARNING-level log if the output file already exists, and writes valid UTF-8 CSV with a header row
  - [x] 3.2 Create `entrypoints/generate_csv.py` as a CLI entry point that parses `--start-date`, `--end-date`, and `--row-count` arguments and calls `generate_call_logs`

- [x] 4. Ingestion pipeline
  - [x] 4.1 Implement `src/wemakecalls/pipelines/ingestion/nodes.py` with four pure functions:
    - `validate_columns(df)` — raises `ValueError` naming every missing column from the 8 required; returns `df` unchanged if all present
    - `parse_and_clean(df)` — parses `datetime` column (naive → UTC, aware → UTC), drops rows with null `call_id` or unparseable `datetime`, logs counts of dropped rows at INFO/WARNING level
    - `deduplicate(df, engine)` — queries `call_logs` for existing `call_id` values, removes matching rows, increments and logs a duplicate counter
    - `insert_to_postgres(df, engine)` — batch-inserts surviving rows with `source='csv_import'`, rolls back entire batch on DB error, retries connection up to 3 times with 5-second delay, logs summary (rows read, inserted, skipped, dropped)
  - [x] 4.2 Implement `src/wemakecalls/pipelines/ingestion/pipeline.py` defining the Kedro `Pipeline` that chains the four nodes and registers it under the name `ingestion` in `pipeline_registry.py`

- [x] 5. Feature engineering pipeline
  - [x] 5.1 Implement `src/wemakecalls/pipelines/feature_engineering/nodes.py` with six pure functions:
    - `aggregate_hourly(call_logs)` — truncates `started_at` to the hour, groups by hour bucket, computes `call_count`, `avg_duration`, and `abandonment_rate` per bucket; produces one row per distinct hour bucket
    - `compute_lag_features(hourly, lag_windows)` — adds `calls_lag_Nh` columns for each window in `lag_windows` ([1, 2, 24, 168]); fills missing history with 0
    - `compute_calendar_features(hourly, holidays)` — adds `hour_of_day` (0–23), `day_of_week` (0 Mon – 6 Sun), `is_weekend` (True when day_of_week in {5,6}), `is_holiday` (True when date in holidays list)
    - `compute_rolling_avg(hourly)` — adds `rolling_avg_7d` as mean `call_count` across the 7 same-hour rows in the 7 prior calendar days
    - `fill_missing_features(features)` — fills all NaN values with 0; asserts no nulls remain
    - `validate_feature_ranges(features)` — asserts `hour_of_day` in [0,23], `day_of_week` in [0,6], `abandonment_rate_lag_1h` in [0.0,1.0]; raises descriptive errors on violation
  - [x] 5.2 Implement `src/wemakecalls/pipelines/feature_engineering/pipeline.py` defining the Kedro `Pipeline` that chains the six nodes, writes output to `data/03_primary/features.parquet` via the catalog, and registers it under the name `feature_engineering` in `pipeline_registry.py`

- [x] 6. Training pipeline
  - [x] 6.1 Implement `src/wemakecalls/pipelines/training/model_factory.py` with `SUPPORTED_MODELS` dict mapping `catboost`, `xgboost`, `lightgbm`, `random_forest`, `linear_regression` to their respective classes, and `get_model(model_type, params)` that logs a WARNING and falls back to `catboost` for unsupported types
  - [x] 6.2 Implement `src/wemakecalls/pipelines/training/nodes.py` with five pure functions:
    - `create_target(features)` — shifts `call_count` by -1 to create `next_hour_calls`; drops the last row; raises `ValueError` if fewer than 168 rows remain
    - `temporal_split(features, ratio)` — splits into train (first `floor(N*ratio)` rows) and test (remaining rows) preserving temporal order; no shuffling
    - `train_model(X_train, y_train, model_type, params)` — instantiates model via `get_model`, fits it, returns fitted model
    - `evaluate_model(model, X_test, y_test)` — computes MAE, RMSE, MAPE; returns metrics dict; all values must be non-negative
    - `save_model_artifact(model, model_type, trained_at)` — serialises model to `data/06_models/<model_type>_<YYYYMMDD_HHMMSS>.pkl` (or `.cbm` for CatBoost); returns artifact path
  - [x] 6.3 Implement `src/wemakecalls/pipelines/training/pipeline.py` defining the Kedro `Pipeline` that chains the five nodes, inserts a training-run row into the `predictions` table (with `predicted_calls` and `target_hour` as NULL), logs training start time, model type, set sizes, and metrics, and registers it under the name `training` in `pipeline_registry.py`

- [x] 7. Inference pipeline
  - [x] 7.1 Implement `src/wemakecalls/pipelines/inference/nodes.py` with four pure functions:
    - `load_latest_model(models_dir)` — finds the most recently modified file in `data/06_models/` by filesystem mtime; raises `FileNotFoundError` with remediation message if directory is empty; performs a test prediction with an all-zero synthetic feature vector and raises `RuntimeError` identifying the artifact as corrupted if the test prediction fails; returns `(model, model_type_str)`
    - `build_prediction_batch(features)` — selects the single most recent row by `hour_bucket` timestamp from the feature vector DataFrame; raises `FileNotFoundError` with remediation message if DataFrame is empty; fills null values with 0; returns single-row DataFrame
    - `run_inference(model, batch)` — calls `model.predict(batch)`, clips result to non-negative, returns integer predicted call count
    - `persist_prediction(prediction, model_type, engine)` — inserts a row into `predictions` with `predicted_at` (current UTC), `target_hour` (next hour bucket start, UTC ISO 8601), `predicted_calls`, and `model_type`; logs and re-raises on DB insert failure
  - [x] 7.2 Implement `src/wemakecalls/pipelines/inference/pipeline.py` defining the Kedro `Pipeline` that chains the four nodes, logs target hour, predicted call count, and model type on success, and registers it under the name `inference` in `pipeline_registry.py`

- [x] 8. FastAPI application
  - [x] 8.1 Define Pydantic v2 models in `entrypoints/api.py`: `FeatureVector` (11 required fields: `calls_lag_1h`, `calls_lag_2h`, `calls_lag_24h`, `calls_lag_168h`, `hour_of_day`, `day_of_week`, `is_weekend`, `is_holiday`, `rolling_avg_7d`, `avg_duration_lag_1h`, `abandonment_rate_lag_1h`), `PredictionResponse` (`predicted_calls: int`, `target_hour: str`, `model_type: str`), `ModelInfoResponse` (`model_type: str`, `trained_at: str`, `mae: float`, `rmse: float`, `mape: float`)
  - [x] 8.2 Implement a module-level `ModelState` object in `entrypoints/api.py` that loads the latest model artifact at application startup and caches model metadata (type, trained_at, MAE, RMSE, MAPE)
  - [x] 8.3 Implement `POST /predict` endpoint: validates request body via Pydantic (returns 422 with field names on validation failure), returns 503 with descriptive message if no model is loaded, otherwise runs inference and returns `PredictionResponse` with HTTP 200; response must be sent within 2 seconds under normal conditions
  - [x] 8.4 Implement `GET /health` endpoint: returns HTTP 200 with `{"status": "ok"}`
  - [x] 8.5 Implement `GET /model/info` endpoint: returns HTTP 200 with `ModelInfoResponse` if model is loaded, or HTTP 503 with descriptive message if no model is loaded
  - [x] 8.6 Configure Uvicorn to listen on `0.0.0.0:8000` so the service is reachable by other containers via the `ml-service` hostname

- [x] 9. Startup check
  - [x] 9.1 Implement `entrypoints/startup_check.py` that reads `DATABASE_URL` from the environment at container startup; if the variable is absent or empty, prints a descriptive error to `stderr` and calls `sys.exit(1)` before the FastAPI server or any pipeline is started; if present, returns normally so the caller can proceed

- [x] 10. Structured JSON logging
  - [x] 10.1 Configure a shared logging utility (`src/wemakecalls/logging_config.py`) that writes all pipeline errors to `logs/pipeline.log` as structured JSON entries with fields: `timestamp` (ISO 8601 UTC), `pipeline` (pipeline name string), `level` (`ERROR`), and `message` (error description string); integrate this logger into all four pipeline node modules and the FastAPI application

- [x] 11. Dockerfile and Docker configuration
  - [x] 11.1 Create `Dockerfile` using `python:3.12-slim` as base image; install `uv`; copy `pyproject.toml` and install all dependencies with exact versions via `uv sync`; copy source code; declare `EXPOSE 8000`; set `ENTRYPOINT` to run `entrypoints/startup_check.py` then start Uvicorn on `0.0.0.0:8000`
  - [x] 11.2 Add Docker `HEALTHCHECK` instruction: `CMD curl -f http://localhost:8000/health`, `--interval=30s`, `--timeout=10s`, `--retries=3`, `--start-period=30s`
  - [x] 11.3 Ensure the Dockerfile does NOT set a default value for `DATABASE_URL` — the variable must be injected at runtime via Docker Compose or `docker run -e`

- [x] 12. Unit tests
  - [x] 12.1 Create `tests/unit/test_csv_generator.py` covering: correct column order in output, correct file naming (`call_history_YYYY.csv`), overwrite WARNING log emitted when file exists (no warning when creating new), valid UTF-8 encoding, abandoned rows have `duration_seconds=0` and `hangup_reason="Call Dropped"`, non-abandoned rows have `duration_seconds` in [30, 1800]
  - [x] 12.2 Create `tests/unit/test_ingestion_nodes.py` covering: `validate_columns` raises `ValueError` naming each missing column, `parse_and_clean` drops rows with null `call_id`, `parse_and_clean` drops rows with unparseable `datetime` and logs count, `insert_to_postgres` rolls back entire batch on DB error, `insert_to_postgres` retries connection 3 times with 5-second delay, summary log contains rows read/inserted/skipped/dropped counts
  - [x] 12.3 Create `tests/unit/test_feature_engineering_nodes.py` covering: `aggregate_hourly` produces one row per distinct hour bucket, `compute_rolling_avg` returns 0 when fewer than 7 prior same-hour rows exist, `validate_feature_ranges` raises descriptive error for `hour_of_day` outside [0,23], `validate_feature_ranges` raises descriptive error for `day_of_week` outside [0,6], `validate_feature_ranges` raises descriptive error for `abandonment_rate_lag_1h` outside [0.0,1.0], Parquet output is written to `data/03_primary/features.parquet`
  - [x] 12.4 Create `tests/unit/test_training_nodes.py` covering: each of the 5 model types is instantiated correctly by `get_model`, unsupported `model_type` logs WARNING and falls back to CatBoost, `create_target` raises `ValueError` when fewer than 168 rows remain after target creation, artifact filename matches `<model_type>_<YYYYMMDD_HHMMSS>` format, training metrics (MAE, RMSE, MAPE) are logged after training completes
  - [x] 12.5 Create `tests/unit/test_inference_nodes.py` covering: `load_latest_model` selects the most recently modified file by mtime, `load_latest_model` raises `FileNotFoundError` when `data/06_models/` is empty, `build_prediction_batch` raises `FileNotFoundError` when features DataFrame is empty, `load_latest_model` raises `RuntimeError` when model artifact is corrupted (test prediction fails), `run_inference` returns a non-negative integer
  - [x] 12.6 Create `tests/unit/test_api.py` covering: `GET /health` returns HTTP 200 with `{"status": "ok"}`, `POST /predict` returns HTTP 503 when no model is loaded, `GET /model/info` returns HTTP 503 when no model is loaded, `POST /predict` returns HTTP 422 when required fields are missing

- [x] 13. Property-based tests
  - [x] 13.1 Create `tests/property/test_csv_generator_props.py` with:
    - [x] 13.1.1 Write property test for Property 1 (row count and datetime bounds): for any valid `start_date`, `end_date`, `row_count` in [1, 10,000,000], the generated CSV contains exactly `row_count` data rows and every `datetime` falls within the inclusive date range. **Validates: Requirements 1.2**
    - [x] 13.1.2 Write property test for Property 2 (field domain constraints): for any generated CSV, every row satisfies `queue_name` in `{billing, support, sales, technical}`, `agent_id` in `{A01..A20}`, `hangup_reason` in the 5-value set, abandoned rows have `duration_seconds=0` and `hangup_reason="Call Dropped"`, non-abandoned rows have `duration_seconds` in [30, 1800]. **Validates: Requirements 1.4, 1.6, 1.7, 1.8, 1.9**
  - [x] 13.2 Create `tests/property/test_ingestion_props.py` with:
    - [x] 13.2.1 Write property test for Property 3 (column validation names missing columns): for any subset of the 8 required columns that is absent, `validate_columns` raises an error whose message contains every missing column name. **Validates: Requirements 2.1, 2.2**
    - [x] 13.2.2 Write property test for Property 4 (null-drop and source tagging): for any CSV that passes column validation, every inserted row has non-null `call_id`, parseable `datetime`, and `source="csv_import"`; rows with null `call_id` or unparseable `datetime` are not inserted. **Validates: Requirements 2.4, 2.5**
  - [x] 13.3 Create `tests/property/test_feature_engineering_props.py` with:
    - [x] 13.3.1 Write property test for Property 5 (hourly aggregation one row per bucket): for any set of call log records, `aggregate_hourly` produces exactly one output row per distinct hour bucket and `call_count` equals the number of input records truncating to that hour. **Validates: Requirements 3.1**
    - [x] 13.3.2 Write property test for Property 6 (lag features match prior hour bucket counts): for any hourly call series with sufficient history, `calls_lag_Nh` for row `i` equals `call_count` at offset `i - N`; when prior row does not exist, lag value is 0. **Validates: Requirements 3.2, 3.7**
    - [x] 13.3.3 Write property test for Property 7 (no null values after fill): for any feature vector dataset produced by the pipeline, every feature column contains zero null values after fill logic is applied. **Validates: Requirements 3.7, 3.10**
    - [x] 13.3.4 Write property test for Property 8 (feature column range invariants): for any feature vector dataset, `hour_of_day` is in [0,23], `day_of_week` is in [0,6], `abandonment_rate_lag_1h` is in [0.0,1.0]. **Validates: Requirements 8.2, 8.3, 8.4**
    - [x] 13.3.5 Write property test for Property 9 (calendar features derived from timestamps): for any Hour_Bucket timestamp, `hour_of_day` equals the hour component, `day_of_week` equals ISO weekday minus 1, `is_weekend` is True iff `day_of_week` in {5,6}, `is_holiday` is True iff date is in the holidays list. **Validates: Requirements 3.3**
    - [x] 13.3.6 Write property test for Property 10 (Parquet round-trip): for any feature vector DataFrame, writing to Parquet with PyArrow and reading back produces a DataFrame with identical column names, dtypes, row count, and cell values. **Validates: Requirements 3.9**
  - [x] 13.4 Create `tests/property/test_training_props.py` with:
    - [x] 13.4.1 Write property test for Property 11 (training target creation): for any hourly call series of length N >= 2, `next_hour_calls` for row `i` equals `call_count` of row `i+1`, and the output has exactly N-1 rows. **Validates: Requirements 4.1**
    - [x] 13.4.2 Write property test for Property 12 (temporal train/test split): for any feature vector dataset of length N and split ratio `r` in (0.0, 1.0), the training set is the first `floor(N*r)` rows and the test set is the remaining rows, with no overlap and temporal order preserved. **Validates: Requirements 4.2**
    - [x] 13.4.3 Write property test for Property 13 (evaluation metrics non-negative): for any trained model and test set, MAE, RMSE, and MAPE are all non-negative floats. **Validates: Requirements 4.6**
    - [x] 13.4.4 Write property test for Property 14 (deterministic model reproducibility): for any fixed feature vector dataset and a deterministic model type (`linear_regression` or `random_forest` with fixed `random_state`), running training twice produces two artifacts whose MAE values differ by no more than 1% in relative terms. **Validates: Requirements 4.9**
  - [x] 13.5 Create `tests/property/test_inference_props.py` with:
    - [x] 13.5.1 Write property test for Property 15 (inference returns non-negative integer): for any valid feature vector row with all feature columns present and non-null, `run_inference` returns a single non-negative integer. **Validates: Requirements 5.4**
    - [x] 13.5.2 Write property test for Property 16 (null-fill before prediction): for any Prediction Batch containing null values in one or more feature columns, `build_prediction_batch` replaces all nulls with 0 before calling `model.predict()`; the model never receives a batch containing null values. **Validates: Requirements 5.6**
  - [x] 13.6 Create `tests/property/test_api_props.py` with:
    - [x] 13.6.1 Write property test for Property 17 (POST /predict response contract): for any valid `FeatureVector` submitted to `POST /predict` with a model loaded, the API returns HTTP 200 with `predicted_calls` (non-negative integer), `target_hour` (valid ISO 8601 UTC string), and `model_type` (non-empty string). **Validates: Requirements 6.2**
    - [x] 13.6.2 Write property test for Property 18 (POST /predict rejects incomplete requests): for any request body missing one or more of the 11 required feature fields, the API returns HTTP 422 and the response body names every missing field. **Validates: Requirements 6.3, 6.10**
    - [x] 13.6.3 Write property test for Property 19 (GET /model/info response contract): for any loaded Model Artifact, `GET /model/info` returns HTTP 200 with all five required fields: `model_type`, `trained_at`, `mae`, `rmse`, `mape`. **Validates: Requirements 6.6**
  - [x] 13.7 Create `tests/property/test_model_factory_props.py` with:
    - [x] 13.7.1 Write property test for Property 20 (model_type parameter drives model selection): for any supported `model_type` value (`catboost`, `xgboost`, `lightgbm`, `random_forest`, `linear_regression`), `get_model` instantiates a model of exactly that type without requiring source code changes. **Validates: Requirements 7.3**

- [x] 14. Integration tests
  - [x] 14.1 Create `tests/integration/test_ingestion_performance.py`: ingest a 100,000-row CSV file end-to-end against a real (or containerised) PostgreSQL instance and assert completion within 60 seconds (Requirement 2.8)
  - [x] 14.2 Create `tests/integration/test_inference_performance.py`: run a single inference pass end-to-end (load model, build batch, predict) and assert completion within 5 seconds excluding database write time (Requirement 5.8)
  - [x] 14.3 Create `tests/integration/test_api_response_time.py`: send requests to `POST /predict` and `GET /model/info` against a running FastAPI instance and assert each response is received within 2 seconds (Requirement 6.9)
  - [x] 14.4 Create `tests/integration/test_pipeline_registry.py`: verify that all four pipeline names (`ingestion`, `feature_engineering`, `training`, `inference`) are registered in the Kedro pipeline registry and each is executable via `kedro run --pipeline=<name>` (Requirement 7.4)


## Notes

- All dependencies in `pyproject.toml` must use exact versions (`==`) per Requirement 9.5.
- The `DATABASE_URL` environment variable must never have a default value in the Dockerfile or any source file — it is always injected at runtime.
- Pipeline node functions must be pure (no side effects beyond logging) to remain independently testable without Kedro infrastructure.
- Property-based tests use Hypothesis with `@settings(max_examples=100)`. Run with `uv run pytest tests/property/`.
- Integration tests require a live PostgreSQL instance; they are skipped in CI unless `DATABASE_URL` is set.
- CatBoost saves artifacts as `.cbm`; all other model types use `.pkl` via joblib.
- The `pipeline_registry.py` must register all four pipelines before any pipeline-specific code is implemented, so Kedro can discover them via `kedro run --pipeline=<name>`.
