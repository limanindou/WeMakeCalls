"""Ingestion pipeline node functions.

Pure functions for validating, cleaning, deduplicating, and inserting
CSV call log data into the PostgreSQL `call_logs` table.
"""

import logging
import time

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "call_id",
    "datetime",
    "duration_seconds",
    "queue_name",
    "agent_id",
    "wait_time_seconds",
    "abandoned",
    "hangup_reason",
]


def validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Validate that all required columns are present in the DataFrame.

    Raises ValueError naming every missing column if any are absent.
    Returns the DataFrame unchanged if all required columns are present.

    Args:
        df: Input DataFrame read from a CSV file.

    Returns:
        The same DataFrame, unmodified.

    Raises:
        ValueError: If one or more required columns are missing.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}"
        )
    return df


def parse_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Parse datetime column and drop rows with null call_id or unparseable datetime.

    - Naive timestamps are treated as UTC.
    - Timezone-aware timestamps are converted to UTC.
    - Rows with null `call_id` are dropped (logged at INFO level).
    - Rows with unparseable `datetime` are dropped (logged at WARNING level).

    Args:
        df: DataFrame that has passed column validation.

    Returns:
        Cleaned DataFrame with valid `call_id` and parsed UTC `datetime` values.
    """
    initial_count = len(df)

    # Drop rows with null call_id
    null_call_id_mask = df["call_id"].isna()
    null_call_id_count = null_call_id_mask.sum()
    if null_call_id_count > 0:
        logger.info(f"Dropped {null_call_id_count} rows with null call_id")
    df = df[~null_call_id_mask].copy()

    # Parse datetime column — coerce errors to NaT
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)

    # Drop rows where datetime parsing failed (NaT)
    unparseable_mask = df["datetime"].isna()
    unparseable_count = unparseable_mask.sum()
    if unparseable_count > 0:
        logger.warning(f"Dropped {unparseable_count} rows with unparseable datetime values")
    df = df[~unparseable_mask].copy()

    total_dropped = initial_count - len(df)
    if total_dropped > 0:
        logger.info(
            f"parse_and_clean: {total_dropped} total rows dropped "
            f"({null_call_id_count} null call_id, {unparseable_count} unparseable datetime)"
        )

    return df


def deduplicate(df: pd.DataFrame, engine: Engine) -> pd.DataFrame:
    """Remove rows whose call_id already exists in the call_logs table.

    Queries the database for existing call_id values that match those in the
    DataFrame, removes matching rows, and logs the duplicate count.

    Args:
        df: DataFrame that has passed validation and cleaning.
        engine: SQLAlchemy engine connected to the PostgreSQL database.

    Returns:
        DataFrame with duplicate rows removed.
    """
    if df.empty:
        return df

    call_ids = df["call_id"].tolist()

    # Query existing call_ids from the database
    with engine.connect() as conn:
        # Use batched IN queries to avoid overly large SQL statements
        existing_ids = set()
        batch_size = 1000
        for i in range(0, len(call_ids), batch_size):
            batch = call_ids[i : i + batch_size]
            result = conn.execute(
                text("SELECT call_id FROM call_logs WHERE call_id = ANY(:ids)"),
                {"ids": batch},
            )
            existing_ids.update(row[0] for row in result)

    # Filter out duplicates
    duplicate_mask = df["call_id"].isin(existing_ids)
    duplicate_count = duplicate_mask.sum()

    if duplicate_count > 0:
        logger.info(f"Skipped {duplicate_count} duplicate rows (call_id already in call_logs)")

    return df[~duplicate_mask].copy()


def insert_to_postgres(df: pd.DataFrame, engine: Engine) -> dict:
    """Batch-insert surviving rows into the call_logs table.

    Inserts all rows with `source='csv_import'`. The `datetime` column is
    mapped to `started_at` in the database. Rolls back the entire batch on
    any database error. Retries connection up to 3 times with a 5-second delay.

    Args:
        df: DataFrame of rows to insert (already validated, cleaned, deduplicated).
        engine: SQLAlchemy engine connected to the PostgreSQL database.

    Returns:
        Summary dict with keys: rows_read, rows_inserted, rows_skipped, rows_dropped.

    Raises:
        Exception: If the database insert fails after rollback, or if connection
            cannot be established after 3 retries.
    """
    rows_to_insert = len(df)

    if df.empty:
        summary = {
            "rows_read": 0,
            "rows_inserted": 0,
            "rows_skipped": 0,
            "rows_dropped": 0,
        }
        logger.info(
            f"Ingestion summary: rows_read={summary['rows_read']}, "
            f"rows_inserted={summary['rows_inserted']}, "
            f"rows_skipped={summary['rows_skipped']}, "
            f"rows_dropped={summary['rows_dropped']}"
        )
        return summary

    # Prepare the insert DataFrame — rename datetime to started_at, add source
    insert_df = df.copy()
    insert_df = insert_df.rename(columns={"datetime": "started_at"})
    insert_df["source"] = "csv_import"

    # Retry connection up to 3 times with 5-second delay
    max_retries = 3
    retry_delay = 5

    for attempt in range(1, max_retries + 1):
        try:
            with engine.begin() as conn:
                insert_df.to_sql(
                    "call_logs",
                    con=conn,
                    if_exists="append",
                    index=False,
                    method="multi",
                )
            # Success — break out of retry loop
            break
        except Exception as e:
            # Check if this is a connection error vs a data/insert error
            error_str = str(e).lower()
            is_connection_error = any(
                keyword in error_str
                for keyword in ["connection", "timeout", "refused", "reset", "broken pipe"]
            )

            if is_connection_error and attempt < max_retries:
                logger.warning(
                    f"Database connection error on attempt {attempt}/{max_retries}: {e}. "
                    f"Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
            else:
                # Non-connection error or final retry exhausted — rollback is
                # handled by the context manager (engine.begin()), so just raise
                logger.error(f"Database error during batch insert: {e}")
                raise

    summary = {
        "rows_read": rows_to_insert,
        "rows_inserted": rows_to_insert,
        "rows_skipped": 0,
        "rows_dropped": 0,
    }
    logger.info(
        f"Ingestion summary: rows_read={summary['rows_read']}, "
        f"rows_inserted={summary['rows_inserted']}, "
        f"rows_skipped={summary['rows_skipped']}, "
        f"rows_dropped={summary['rows_dropped']}"
    )
    return summary
