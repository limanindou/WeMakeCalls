# Requirements Document

## Introduction

The ML Service is the machine learning backbone of WeMakeCalls — a full-stack MLOps call center application. It is responsible for generating synthetic historical call data, ingesting CSV files into PostgreSQL, engineering time-series features, training forecasting models, running hourly inference, and exposing predictions via a FastAPI REST API. The service is built with Python 3.12, Kedro 1.1+, FastAPI 0.110+, and supports CatBoost (default), XGBoost, LightGBM, Random Forest, and Linear Regression models.

---

## Glossary

- **ML_Service**: The Python/Kedro/FastAPI application responsible for all machine learning operations in WeMakeCalls.
- **CSV_Generator**: The component that produces synthetic historical call log CSV files.
- **Ingestion_Pipeline**: The Kedro pipeline that reads CSV files, validates them, and inserts records into PostgreSQL.
- **Feature_Engineering_Pipeline**: The Kedro pipeline that transforms raw call log data into ML-ready feature vectors.
- **Training_Pipeline**: The Kedro pipeline that trains a forecasting model and saves it to disk.
- **Inference_Pipeline**: The Kedro pipeline that loads a trained model and produces next-hour call volume predictions.
- **API_Server**: The FastAPI application that exposes ML predictions and model metadata via HTTP endpoints.
- **call_logs**: The PostgreSQL table storing all historical and simulator-sourced call records.
- **predictions**: The PostgreSQL table storing all model predictions alongside actuals and evaluation metrics.
- **Feature_Vector**: A single row of engineered features used as input to the model for training or inference.
- **Hour_Bucket**: A one-hour time window used to aggregate call counts for feature engineering.
- **Lag_Feature**: A feature derived from call volume at a prior Hour_Bucket (e.g., 1h, 2h, 24h, 168h ago).
- **Rolling_Average**: A feature computed as the mean call volume across a sliding window of past Hour_Buckets.
- **Model_Artifact**: A serialised trained model file saved to `data/06_models/`.
- **Prediction_Batch**: A DataFrame of Feature_Vectors prepared for a single inference run.
- **Catalog**: The Kedro `catalog.yml` file that defines all dataset paths and types.
- **Parameters**: The Kedro `parameters.yml` file that controls model type, lag windows, and inference settings.

---

## Requirements

### Requirement 1: Synthetic CSV Data Generation

**User Story:** As a data engineer, I want to generate synthetic historical call log CSV files, so that the ML pipeline has realistic training data before live simulator data is available.

#### Acceptance Criteria

1. THE CSV_Generator SHALL produce CSV files with exactly the following columns in this order: `call_id`, `datetime`, `duration_seconds`, `queue_name`, `agent_id`, `wait_time_seconds`, `abandoned`, `hangup_reason`.
2. WHEN the CSV_Generator is invoked with a start date, end date, and row count (minimum 1, maximum 10,000,000), THE CSV_Generator SHALL produce a file containing exactly the specified number of rows with `datetime` values falling within the inclusive date range.
3. THE CSV_Generator SHALL generate `datetime` values using a weighted hourly distribution that produces higher call volumes during business hours (08:00–18:00) and lower volumes outside those hours, covering all 24 hours of each day.
4. THE CSV_Generator SHALL generate `duration_seconds` values as positive integers drawn from a log-normal distribution with a minimum of 30 seconds and a maximum of 1800 seconds for non-abandoned calls.
5. THE CSV_Generator SHALL generate `abandoned` as a boolean with an abandonment rate between 5% and 20% of total rows, sampled uniformly at random.
6. WHEN `abandoned` is `true`, THE CSV_Generator SHALL set `duration_seconds` to 0 for that row, overriding any value that would otherwise be assigned by the duration distribution.
7. THE CSV_Generator SHALL assign `queue_name` values uniformly at random from the fixed set: `billing`, `support`, `sales`, `technical`.
8. THE CSV_Generator SHALL assign `agent_id` values from a pool of 20 synthetic agent identifiers in the format `A01`–`A20`, distributed uniformly at random.
9. THE CSV_Generator SHALL assign `hangup_reason` values from the fixed set: `Issue Resolved`, `Wrong Department`, `Long Wait Time`, `Call Dropped`, `Other`. WHEN `abandoned` is `true`, THE CSV_Generator SHALL set `hangup_reason` to `Call Dropped`.
10. THE CSV_Generator SHALL write output files to `data/01_raw/` in the format `call_history_YYYY.csv`, where `YYYY` is the year of the start date parameter.
11. IF the output file path already exists, THEN THE CSV_Generator SHALL overwrite the existing file and emit a WARNING-level log message identifying the overwritten path. THE CSV_Generator SHALL NOT emit this warning when creating a new file.
12. THE CSV_Generator SHALL produce valid UTF-8 encoded CSV files with a header row as the first line.

---

### Requirement 2: CSV Ingestion into PostgreSQL

**User Story:** As a data engineer, I want to ingest CSV call log files into the PostgreSQL `call_logs` table, so that the ML training pipeline has a consistent, queryable data source.

#### Acceptance Criteria

1. WHEN a CSV file is provided to the Ingestion_Pipeline, THE Ingestion_Pipeline SHALL validate that all required columns (`call_id`, `datetime`, `duration_seconds`, `queue_name`, `agent_id`, `wait_time_seconds`, `abandoned`, `hangup_reason`) are present before any row-level processing begins.
2. IF a required column is missing from the CSV file, THEN THE Ingestion_Pipeline SHALL raise a descriptive error that names the missing column(s) and halt ingestion without inserting any rows.
3. WHEN a CSV file passes column validation, THE Ingestion_Pipeline SHALL attempt to parse each `datetime` value as a timestamp. Naive timestamps SHALL be treated as UTC. Timezone-aware timestamps SHALL be converted to UTC. Rows with unparseable `datetime` values SHALL be dropped, and THE Ingestion_Pipeline SHALL log the count of dropped unparseable rows after processing completes.
4. IF a row has a null `call_id` or a null (or unparseable) `datetime`, THEN THE Ingestion_Pipeline SHALL drop that row and not insert it into `call_logs`.
5. THE Ingestion_Pipeline SHALL insert all rows that survive null-drop, datetime-parse, and duplicate checks into the `call_logs` table with `source` set to `'csv_import'`.
6. WHEN a `call_id` value in the CSV already exists in `call_logs`, THE Ingestion_Pipeline SHALL skip that row and increment a duplicate counter. The duplicate counter SHALL only be incremented for rows that have already passed column validation and null-drop checks.
7. WHEN ingestion completes, THE Ingestion_Pipeline SHALL log the total rows read from the CSV, total rows inserted, total rows skipped as duplicates, and total rows dropped due to null or unparseable values.
8. THE Ingestion_Pipeline SHALL complete ingestion of a 100,000-row CSV file within 60 seconds on a machine with at least a 4-core CPU and 8 GB RAM.
9. IF a database connection error occurs during ingestion, THEN THE Ingestion_Pipeline SHALL retry the connection up to 3 times with a 5-second delay between attempts before raising a fatal error.
10. WHEN a database error occurs during batch insertion, THE Ingestion_Pipeline SHALL roll back the entire batch so that no partial rows are committed, and SHALL raise the error after rollback.

---

### Requirement 3: Feature Engineering

**User Story:** As a machine learning engineer, I want to transform raw call log data into time-series feature vectors, so that the model has meaningful predictors for forecasting call volume.

#### Acceptance Criteria

1. WHEN the Feature_Engineering_Pipeline runs, THE Feature_Engineering_Pipeline SHALL aggregate `call_logs` records into Hour_Buckets by truncating `started_at` to the hour, producing one row per Hour_Bucket with a `call_count` column equal to the number of calls in that bucket.
2. THE Feature_Engineering_Pipeline SHALL compute the following Lag_Features for each Hour_Bucket: `calls_lag_1h` (call_count 1 hour prior), `calls_lag_2h` (2 hours prior), `calls_lag_24h` (24 hours prior), `calls_lag_168h` (168 hours prior).
3. THE Feature_Engineering_Pipeline SHALL compute the following calendar features for each Hour_Bucket: `hour_of_day` (integer 0–23), `day_of_week` (integer 0 for Monday through 6 for Sunday), `is_weekend` (true when `day_of_week` is 5 or 6, false otherwise), `is_holiday` (true when the Hour_Bucket date matches a date in the holiday list defined in `parameters.yml`, false otherwise).
4. THE Feature_Engineering_Pipeline SHALL compute `rolling_avg_7d` as the mean `call_count` across the 7 Hour_Buckets that share the same `hour_of_day` in the 7 calendar days immediately preceding the current Hour_Bucket's date.
5. THE Feature_Engineering_Pipeline SHALL compute `avg_duration_lag_1h` as the mean `duration_seconds` of all calls in the Hour_Bucket 1 hour prior. WHEN the prior Hour_Bucket contains zero calls, THE Feature_Engineering_Pipeline SHALL set `avg_duration_lag_1h` to 0.
6. THE Feature_Engineering_Pipeline SHALL compute `abandonment_rate_lag_1h` as the ratio of abandoned calls to total calls in the Hour_Bucket 1 hour prior. WHEN the prior Hour_Bucket contains zero calls, THE Feature_Engineering_Pipeline SHALL set `abandonment_rate_lag_1h` to 0.
7. WHEN any derived feature (`calls_lag_1h`, `calls_lag_2h`, `calls_lag_24h`, `calls_lag_168h`, `rolling_avg_7d`, `avg_duration_lag_1h`, `abandonment_rate_lag_1h`) cannot be computed due to insufficient history, THE Feature_Engineering_Pipeline SHALL fill the missing value with 0.
8. THE Feature_Engineering_Pipeline SHALL output the engineered Feature_Vector dataset to `data/03_primary/features.parquet` as a Parquet file using PyArrow.
9. WHEN a valid Feature_Vector Parquet file is written to `data/03_primary/` and then read back, THE resulting DataFrame SHALL have identical schema (column names and dtypes), identical row count, and identical values in every cell as the DataFrame that was written (round-trip property).
10. THE Feature_Engineering_Pipeline SHALL produce a Feature_Vector dataset where every feature column contains no null values after fill logic is applied.

---

### Requirement 4: Model Training

**User Story:** As a machine learning engineer, I want to train a call volume forecasting model on engineered features, so that the system can predict next-hour call counts with measurable accuracy.

#### Acceptance Criteria

1. WHEN the Training_Pipeline runs, THE Training_Pipeline SHALL create a target column `next_hour_calls` by shifting the `call_count` column forward by one Hour_Bucket (i.e., the target for row N is the `call_count` of row N+1), and SHALL drop the last row which has no target value.
2. THE Training_Pipeline SHALL split the Feature_Vector dataset into a training set (first 80% of rows) and a test set (last 20% of rows), preserving temporal order with no shuffling.
3. THE Training_Pipeline SHALL train the model type specified by the `model_type` key in `parameters.yml`, defaulting to `catboost` when the key is absent.
4. THE Training_Pipeline SHALL support the following model types: `catboost`, `xgboost`, `lightgbm`, `random_forest`, `linear_regression`.
5. IF an unsupported model type is specified in `parameters.yml`, THEN THE Training_Pipeline SHALL log a WARNING identifying the unsupported value and the supported model types, and SHALL proceed using `catboost` as the fallback model.
6. WHEN training completes, THE Training_Pipeline SHALL evaluate the trained model on the test set and compute MAE, RMSE, and MAPE.
7. THE Training_Pipeline SHALL save the trained Model_Artifact to `data/06_models/` with a filename in the format `<model_type>_<YYYYMMDD_HHMMSS>.pkl` (or `.cbm` for CatBoost), where the timestamp is the UTC training start time.
8. THE Training_Pipeline SHALL insert a row into the `predictions` table in PostgreSQL containing: `model_type`, training timestamp (`predicted_at`), MAE, RMSE, and MAPE. The `predicted_calls` and `target_hour` columns SHALL be set to NULL for training-run rows.
9. WHEN the Training_Pipeline is run twice with the same Feature_Vector dataset and the same `parameters.yml` on a deterministic model type (`linear_regression`, `random_forest` with fixed `random_state`), THE two resulting Model_Artifacts SHALL produce MAE values on the same test set that differ by no more than 1% in relative terms.
10. WHEN the Training_Pipeline completes, THE Training_Pipeline SHALL log: training start time (UTC ISO 8601), model type used, training set size (rows), test set size (rows), MAE, RMSE, and MAPE.

---

### Requirement 5: Inference

**User Story:** As a machine learning engineer, I want to run inference on the latest feature batch to predict next-hour call volume, so that the system can provide actionable forecasts to call center managers.

#### Acceptance Criteria

1. WHEN the Inference_Pipeline runs, THE Inference_Pipeline SHALL identify the most recently modified file in `data/06_models/` by filesystem modification time and load it as the active Model_Artifact.
2. WHEN the Model_Artifact has been successfully loaded, THE Inference_Pipeline SHALL construct a Prediction_Batch by selecting the single most recent row (by Hour_Bucket timestamp) from the Feature_Vector dataset in `data/03_primary/features.parquet`.
3. IF `data/03_primary/features.parquet` does not exist or contains zero rows, THEN THE Inference_Pipeline SHALL raise a descriptive error instructing the user to run the Feature_Engineering_Pipeline first, and SHALL NOT proceed to prediction.
4. WHEN a Prediction_Batch is prepared, THE Inference_Pipeline SHALL produce a single non-negative integer predicted call count for the next Hour_Bucket.
5. IF no file exists in `data/06_models/`, THEN THE Inference_Pipeline SHALL raise a descriptive error instructing the user to run the Training_Pipeline first, and SHALL NOT proceed to batch construction.
6. IF the Prediction_Batch contains null values in any feature column, THEN THE Inference_Pipeline SHALL fill those null values with 0 before running inference.
7. WHEN the prediction is produced, THE Inference_Pipeline SHALL insert a row into the `predictions` table with: `predicted_at` (current UTC timestamp), `target_hour` (next Hour_Bucket start, UTC ISO 8601), `predicted_calls` (the predicted integer), `model_type` (name of the loaded model type). IF the database insert fails, THEN THE Inference_Pipeline SHALL log the error and raise it after logging.
8. THE Inference_Pipeline SHALL complete a single inference run within 5 seconds on a machine with at least a 4-core CPU and 8 GB RAM, excluding database write time.
9. WHEN the Inference_Pipeline runs successfully, THE Inference_Pipeline SHALL log: target hour (UTC ISO 8601), predicted call count, and model type used.

---

### Requirement 6: FastAPI REST Endpoints

**User Story:** As a backend engineer, I want the ML Service to expose REST endpoints, so that the Java backend can trigger inference and retrieve predictions programmatically.

#### Acceptance Criteria

1. THE API_Server SHALL expose a `POST /predict` endpoint that accepts a JSON body containing a Feature_Vector with the following 11 required fields: `calls_lag_1h`, `calls_lag_2h`, `calls_lag_24h`, `calls_lag_168h`, `hour_of_day`, `day_of_week`, `is_weekend`, `is_holiday`, `rolling_avg_7d`, `avg_duration_lag_1h`, `abandonment_rate_lag_1h`.
2. WHEN a valid Feature_Vector is submitted to `POST /predict`, THE API_Server SHALL return HTTP 200 with a JSON response body containing: `predicted_calls` (integer), `target_hour` (ISO 8601 UTC string), and `model_type` (string).
3. IF the request body submitted to `POST /predict` is missing one or more required feature fields, THEN THE API_Server SHALL return HTTP 422 with a JSON body that names each missing field.
4. IF `POST /predict` is called and no Model_Artifact has been loaded, THEN THE API_Server SHALL return HTTP 503 with a JSON body containing a message indicating the model is not available and instructing the caller to wait for training to complete.
5. WHEN the `GET /health` endpoint is called and the service is running, THE API_Server SHALL return HTTP 200 with the JSON body `{"status": "ok"}`.
6. THE API_Server SHALL expose a `GET /model/info` endpoint that returns HTTP 200 with a JSON body containing: `model_type` (string), `trained_at` (ISO 8601 UTC string), `mae` (float), `rmse` (float), `mape` (float).
7. IF no Model_Artifact has been loaded when `GET /model/info` is called, THEN THE API_Server SHALL return HTTP 503 with a JSON body containing a message indicating the model is not yet available.
8. THE API_Server SHALL listen on `0.0.0.0:8000` so that it is reachable from other containers in the Docker Compose network by the service name `ml-service` on port 8000.
9. WHEN the API_Server receives any request under normal operating conditions (model loaded, no database contention), THE API_Server SHALL send the complete response within 2 seconds, excluding network transit time.
10. THE API_Server SHALL validate all incoming request bodies using Pydantic v2 models and SHALL NOT pass unvalidated data to the Inference_Pipeline.

---

### Requirement 7: Kedro Pipeline Configuration

**User Story:** As a machine learning engineer, I want all pipelines to be configured via Kedro catalog and parameters files, so that datasets, model settings, and pipeline behaviour can be changed without modifying source code.

#### Acceptance Criteria

1. THE ML_Service SHALL define all dataset paths and types in `conf/base/catalog.yml` using Kedro dataset conventions, with no dataset path hardcoded in pipeline source code.
2. THE ML_Service SHALL define the following configurable parameters in `conf/base/parameters.yml`: `model_type` (string), `lag_windows` (list of integers: [1, 2, 24, 168]), `train_test_split_ratio` (float, exclusive range 0.0–1.0), `inference_interval_minutes` (positive integer, range 1–1440), and `holidays` (list of date strings in `YYYY-MM-DD` format).
3. WHEN `parameters.yml` is updated with a supported `model_type` value and the Training_Pipeline is executed immediately after, THE Training_Pipeline SHALL use the updated model type without requiring any source code changes. IF the updated `model_type` is unsupported, THE Training_Pipeline SHALL log a warning and fall back to `catboost` per Requirement 4 Criterion 5.
4. THE ML_Service SHALL register the following four pipelines in the Kedro pipeline registry under these exact names: `ingestion`, `feature_engineering`, `training`, `inference`. Each pipeline SHALL be executable via `kedro run --pipeline=<name>`.
5. THE Catalog SHALL define named datasets for: raw CSV input files (`data/01_raw/`), primary feature Parquet files (`data/03_primary/`), trained model artifacts (`data/06_models/`), and model output files (`data/07_model_output/`).

---

### Requirement 8: Data Validation and Error Handling

**User Story:** As a data engineer, I want the ML Service to validate data at each pipeline stage and handle errors gracefully, so that bad data does not silently corrupt model training or inference.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a CSV file, THE Ingestion_Pipeline SHALL attempt to parse every value in the `datetime` column as a timestamp, drop rows where parsing fails, and log the total count of dropped unparseable rows at WARNING level after processing completes.
2. WHEN the Feature_Engineering_Pipeline produces a Feature_Vector dataset, THE Feature_Engineering_Pipeline SHALL assert that every value in the `hour_of_day` column is an integer in the closed range [0, 23], and SHALL raise a descriptive error if any value falls outside this range.
3. WHEN the Feature_Engineering_Pipeline produces a Feature_Vector dataset, THE Feature_Engineering_Pipeline SHALL assert that every value in the `day_of_week` column is an integer in the closed range [0, 6], and SHALL raise a descriptive error if any value falls outside this range.
4. WHEN the Feature_Engineering_Pipeline produces a Feature_Vector dataset, THE Feature_Engineering_Pipeline SHALL assert that every value in the `abandonment_rate_lag_1h` column is a float in the closed range [0.0, 1.0], and SHALL raise a descriptive error if any value falls outside this range.
5. IF the Feature_Vector dataset produced by the Feature_Engineering_Pipeline contains fewer than 168 rows, THEN THE Training_Pipeline SHALL raise a descriptive error stating the actual row count and the minimum required row count (168), and SHALL NOT proceed with training.
6. WHEN the Inference_Pipeline loads a Model_Artifact file, THE Inference_Pipeline SHALL perform a test prediction using a synthetic Feature_Vector of all-zero values. IF the test prediction raises an exception, THEN THE Inference_Pipeline SHALL raise a descriptive error identifying the artifact as corrupted and SHALL NOT proceed with real inference.
7. THE ML_Service SHALL write all pipeline errors to `logs/pipeline.log` as structured JSON log entries, where each entry contains: `timestamp` (ISO 8601 UTC), `pipeline` (pipeline name string), `level` (`ERROR`), and `message` (error description string).

---

### Requirement 9: Docker and Environment Configuration

**User Story:** As a DevOps engineer, I want the ML Service to run as a Docker container with environment-based configuration, so that it integrates cleanly into the WeMakeCalls Docker Compose stack.

#### Acceptance Criteria

1. THE ML_Service SHALL be packaged as a Docker image using `python:3.12-slim` as the base image.
2. THE ML_Service SHALL read the PostgreSQL connection string exclusively from the environment variable `DATABASE_URL` at runtime, with no fallback default value.
3. IF `DATABASE_URL` is not set or is set to an empty string at container startup, THEN THE ML_Service SHALL print a descriptive error message to stderr and exit immediately with a non-zero status code, without attempting to start the API_Server or run any pipeline.
4. THE ML_Service Dockerfile SHALL declare `EXPOSE 8000` for the FastAPI API_Server port.
5. THE ML_Service SHALL use `uv` for dependency installation, with all dependencies specified as exact versions (using `==`) in `pyproject.toml`.
6. THE ML_Service Dockerfile SHALL include a Docker HEALTHCHECK instruction that: calls `GET http://localhost:8000/health`, runs every 30 seconds (`--interval=30s`), times out after 10 seconds (`--timeout=10s`), allows 3 retries before marking unhealthy (`--retries=3`), and waits 30 seconds before the first check (`--start-period=30s`).
