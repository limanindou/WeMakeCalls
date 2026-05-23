"""Unit tests for the CSV Generator module."""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from wemakecalls.pipelines.csv_generator import generate_call_logs


EXPECTED_COLUMNS = [
    "call_id",
    "datetime",
    "duration_seconds",
    "queue_name",
    "agent_id",
    "wait_time_seconds",
    "abandoned",
    "hangup_reason",
]


class TestColumnOrder:
    """Output CSV has correct column order."""

    def test_csv_has_correct_column_order(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=100,
            output_dir=tmp_path,
        )
        df = pd.read_csv(output)
        assert list(df.columns) == EXPECTED_COLUMNS


class TestFileNaming:
    """Output file is named call_history_YYYY.csv where YYYY matches start_date year."""

    def test_file_named_with_start_date_year(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=100,
            output_dir=tmp_path,
        )
        assert output.name == "call_history_2024.csv"

    def test_file_named_with_different_year(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2023, 6, 1),
            end_date=date(2023, 6, 30),
            row_count=100,
            output_dir=tmp_path,
        )
        assert output.name == "call_history_2023.csv"


class TestOverwriteWarning:
    """WARNING log is emitted when output file already exists; no warning for new file."""

    def test_warning_emitted_when_file_exists(self, tmp_path: Path, caplog):
        # Create the file first
        generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=100,
            output_dir=tmp_path,
        )
        # Generate again — should trigger warning
        with caplog.at_level(logging.WARNING):
            generate_call_logs(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                row_count=100,
                output_dir=tmp_path,
            )
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("already exists" in msg for msg in warning_messages)

    def test_no_warning_when_creating_new_file(self, tmp_path: Path, caplog):
        with caplog.at_level(logging.WARNING):
            generate_call_logs(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                row_count=100,
                output_dir=tmp_path,
            )
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert not any("already exists" in msg for msg in warning_messages)


class TestUtf8Encoding:
    """Output file is valid UTF-8 encoding."""

    def test_output_is_valid_utf8(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=100,
            output_dir=tmp_path,
        )
        # Reading with utf-8 should not raise
        content = output.read_text(encoding="utf-8")
        assert len(content) > 0


class TestAbandonedRows:
    """Abandoned rows have duration_seconds=0 and hangup_reason='Call Dropped'."""

    def test_abandoned_rows_have_zero_duration_and_call_dropped(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=1000,
            output_dir=tmp_path,
        )
        df = pd.read_csv(output)
        abandoned_rows = df[df["abandoned"] == True]  # noqa: E712

        if len(abandoned_rows) > 0:
            assert (abandoned_rows["duration_seconds"] == 0).all()
            assert (abandoned_rows["hangup_reason"] == "Call Dropped").all()


class TestNonAbandonedRows:
    """Non-abandoned rows have duration_seconds in [30, 1800]."""

    def test_non_abandoned_duration_in_valid_range(self, tmp_path: Path):
        output = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            row_count=1000,
            output_dir=tmp_path,
        )
        df = pd.read_csv(output)
        non_abandoned_rows = df[df["abandoned"] == False]  # noqa: E712

        if len(non_abandoned_rows) > 0:
            assert (non_abandoned_rows["duration_seconds"] >= 30).all()
            assert (non_abandoned_rows["duration_seconds"] <= 1800).all()
