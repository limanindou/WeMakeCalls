"""Unit tests for the Ingestion Pipeline nodes."""

import logging
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd
import pytest

from wemakecalls.pipelines.ingestion.nodes import (
    validate_columns,
    parse_and_clean,
    insert_to_postgres,
    REQUIRED_COLUMNS,
)


class TestValidateColumns:
    """validate_columns raises ValueError naming each missing column."""

    def test_raises_value_error_when_single_column_missing(self):
        df = pd.DataFrame(
            columns=[col for col in REQUIRED_COLUMNS if col != "call_id"]
        )
        with pytest.raises(ValueError, match="call_id"):
            validate_columns(df)

    def test_raises_value_error_naming_all_missing_columns(self):
        missing = ["call_id", "datetime", "queue_name"]
        present = [col for col in REQUIRED_COLUMNS if col not in missing]
        df = pd.DataFrame(columns=present)

        with pytest.raises(ValueError) as exc_info:
            validate_columns(df)

        error_message = str(exc_info.value)
        for col in missing:
            assert col in error_message, f"Missing column '{col}' not named in error"

    def test_raises_value_error_when_all_columns_missing(self):
        df = pd.DataFrame(columns=["unrelated_col"])

        with pytest.raises(ValueError) as exc_info:
            validate_columns(df)

        error_message = str(exc_info.value)
        for col in REQUIRED_COLUMNS:
            assert col in error_message

    def test_returns_df_unchanged_when_all_columns_present(self):
        df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        result = validate_columns(df)
        assert list(result.columns) == REQUIRED_COLUMNS


class TestParseAndCleanNullCallId:
    """parse_and_clean drops rows with null call_id."""

    def test_drops_rows_with_null_call_id(self):
        df = pd.DataFrame({
            "call_id": ["C001", None, "C003", None],
            "datetime": [
                "2024-01-01 10:00:00",
                "2024-01-01 11:00:00",
                "2024-01-01 12:00:00",
                "2024-01-01 13:00:00",
            ],
            "duration_seconds": [60, 120, 90, 45],
            "queue_name": ["billing"] * 4,
            "agent_id": ["A01"] * 4,
            "wait_time_seconds": [10] * 4,
            "abandoned": [False] * 4,
            "hangup_reason": ["Issue Resolved"] * 4,
        })

        result = parse_and_clean(df)
        assert len(result) == 2
        assert result["call_id"].tolist() == ["C001", "C003"]

    def test_drops_all_rows_when_all_call_ids_null(self):
        df = pd.DataFrame({
            "call_id": [None, None],
            "datetime": ["2024-01-01 10:00:00", "2024-01-01 11:00:00"],
            "duration_seconds": [60, 120],
            "queue_name": ["billing", "support"],
            "agent_id": ["A01", "A02"],
            "wait_time_seconds": [10, 20],
            "abandoned": [False, False],
            "hangup_reason": ["Issue Resolved", "Other"],
        })

        result = parse_and_clean(df)
        assert len(result) == 0


class TestParseAndCleanUnparseableDatetime:
    """parse_and_clean drops rows with unparseable datetime and logs count."""

    def test_drops_rows_with_unparseable_datetime(self):
        df = pd.DataFrame({
            "call_id": ["C001", "C002", "C003"],
            "datetime": ["2024-01-01 10:00:00", "not-a-date", "2024-01-01 12:00:00"],
            "duration_seconds": [60, 120, 90],
            "queue_name": ["billing"] * 3,
            "agent_id": ["A01"] * 3,
            "wait_time_seconds": [10] * 3,
            "abandoned": [False] * 3,
            "hangup_reason": ["Issue Resolved"] * 3,
        })

        result = parse_and_clean(df)
        assert len(result) == 2
        assert "C002" not in result["call_id"].values

    def test_logs_count_of_dropped_unparseable_datetime_rows(self, caplog):
        df = pd.DataFrame({
            "call_id": ["C001", "C002", "C003", "C004"],
            "datetime": [
                "2024-01-01 10:00:00",
                "invalid-date",
                "also-not-valid",
                "2024-01-01 13:00:00",
            ],
            "duration_seconds": [60, 120, 90, 45],
            "queue_name": ["billing"] * 4,
            "agent_id": ["A01"] * 4,
            "wait_time_seconds": [10] * 4,
            "abandoned": [False] * 4,
            "hangup_reason": ["Issue Resolved"] * 4,
        })

        with caplog.at_level(logging.WARNING):
            parse_and_clean(df)

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("2" in msg and "unparseable" in msg.lower() for msg in warning_messages)


class TestInsertToPostgresRollback:
    """insert_to_postgres rolls back entire batch on DB error."""

    def test_rolls_back_on_db_error(self):
        df = pd.DataFrame({
            "call_id": ["C001", "C002"],
            "datetime": pd.to_datetime(["2024-01-01 10:00:00", "2024-01-01 11:00:00"], utc=True),
            "duration_seconds": [60, 120],
            "queue_name": ["billing", "support"],
            "agent_id": ["A01", "A02"],
            "wait_time_seconds": [10, 20],
            "abandoned": [False, False],
            "hangup_reason": ["Issue Resolved", "Other"],
        })

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        # Simulate engine.begin() as context manager that raises on to_sql
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Make to_sql raise a non-connection error to trigger rollback
        mock_conn.execute = MagicMock(side_effect=Exception("integrity constraint violation"))

        # Patch pd.DataFrame.to_sql to raise an error simulating DB failure
        with patch("pandas.DataFrame.to_sql", side_effect=Exception("integrity constraint violation")):
            with pytest.raises(Exception, match="integrity constraint violation"):
                insert_to_postgres(df, mock_engine)

        # engine.begin() context manager handles rollback automatically
        # Verify that begin() was called (transaction was attempted)
        mock_engine.begin.assert_called()


class TestInsertToPostgresRetry:
    """insert_to_postgres retries connection 3 times with 5-second delay."""

    @patch("wemakecalls.pipelines.ingestion.nodes.time.sleep")
    def test_retries_connection_3_times_with_5_second_delay(self, mock_sleep):
        df = pd.DataFrame({
            "call_id": ["C001"],
            "datetime": pd.to_datetime(["2024-01-01 10:00:00"], utc=True),
            "duration_seconds": [60],
            "queue_name": ["billing"],
            "agent_id": ["A01"],
            "wait_time_seconds": [10],
            "abandoned": [False],
            "hangup_reason": ["Issue Resolved"],
        })

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate connection errors on all 3 attempts
        connection_error = Exception("connection refused")

        with patch("pandas.DataFrame.to_sql", side_effect=connection_error):
            with pytest.raises(Exception, match="connection refused"):
                insert_to_postgres(df, mock_engine)

        # Should have slept twice (after attempt 1 and 2, not after attempt 3)
        assert mock_sleep.call_count == 2
        # Each sleep should be 5 seconds
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 5

    @patch("wemakecalls.pipelines.ingestion.nodes.time.sleep")
    def test_succeeds_on_third_retry(self, mock_sleep):
        df = pd.DataFrame({
            "call_id": ["C001"],
            "datetime": pd.to_datetime(["2024-01-01 10:00:00"], utc=True),
            "duration_seconds": [60],
            "queue_name": ["billing"],
            "agent_id": ["A01"],
            "wait_time_seconds": [10],
            "abandoned": [False],
            "hangup_reason": ["Issue Resolved"],
        })

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Fail twice with connection error, succeed on third attempt
        connection_error = Exception("connection refused")
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise connection_error
            return None  # Success on third call

        with patch("pandas.DataFrame.to_sql", side_effect=side_effect):
            result = insert_to_postgres(df, mock_engine)

        assert result["rows_inserted"] == 1
        assert mock_sleep.call_count == 2


class TestInsertToPostgresSummaryLog:
    """Summary log contains rows read/inserted/skipped/dropped counts."""

    def test_summary_log_contains_all_counts(self, caplog):
        df = pd.DataFrame({
            "call_id": ["C001", "C002", "C003"],
            "datetime": pd.to_datetime(
                ["2024-01-01 10:00:00", "2024-01-01 11:00:00", "2024-01-01 12:00:00"],
                utc=True,
            ),
            "duration_seconds": [60, 120, 90],
            "queue_name": ["billing", "support", "sales"],
            "agent_id": ["A01", "A02", "A03"],
            "wait_time_seconds": [10, 20, 30],
            "abandoned": [False, False, False],
            "hangup_reason": ["Issue Resolved", "Other", "Issue Resolved"],
        })

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        with caplog.at_level(logging.INFO):
            with patch("pandas.DataFrame.to_sql", return_value=None):
                insert_to_postgres(df, mock_engine)

        log_messages = " ".join(r.message for r in caplog.records)
        assert "rows_read" in log_messages
        assert "rows_inserted" in log_messages
        assert "rows_skipped" in log_messages
        assert "rows_dropped" in log_messages

    def test_summary_log_for_empty_dataframe(self, caplog):
        df = pd.DataFrame(columns=[
            "call_id", "datetime", "duration_seconds", "queue_name",
            "agent_id", "wait_time_seconds", "abandoned", "hangup_reason",
        ])

        mock_engine = MagicMock()

        with caplog.at_level(logging.INFO):
            result = insert_to_postgres(df, mock_engine)

        assert result["rows_read"] == 0
        assert result["rows_inserted"] == 0
        assert result["rows_skipped"] == 0
        assert result["rows_dropped"] == 0

        log_messages = " ".join(r.message for r in caplog.records)
        assert "rows_read" in log_messages
