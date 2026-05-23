"""Unit tests for the shared structured JSON logging utility."""

import json
import logging
import tempfile
from pathlib import Path

from wemakecalls.logging_config import StructuredJSONFormatter, setup_logging


class TestStructuredJSONFormatter:
    """Tests for the StructuredJSONFormatter class."""

    def test_format_produces_valid_json(self):
        """Formatted output is valid JSON."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.ingestion.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Database connection failed",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_contains_required_fields(self):
        """Output JSON contains timestamp, pipeline, level, and message."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.training.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Model training failed",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "pipeline" in parsed
        assert "level" in parsed
        assert "message" in parsed

    def test_format_timestamp_is_iso8601_utc(self):
        """Timestamp field is ISO 8601 UTC format."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.ingestion.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        # Should end with Z and be parseable
        assert parsed["timestamp"].endswith("Z")
        assert "T" in parsed["timestamp"]

    def test_format_extracts_pipeline_name_from_ingestion(self):
        """Pipeline name is extracted from wemakecalls.pipelines.ingestion.nodes."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.ingestion.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["pipeline"] == "ingestion"

    def test_format_extracts_pipeline_name_from_training(self):
        """Pipeline name is extracted from wemakecalls.pipelines.training.nodes."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.training.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["pipeline"] == "training"

    def test_format_extracts_pipeline_name_from_feature_engineering(self):
        """Pipeline name is extracted from wemakecalls.pipelines.feature_engineering.nodes."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.feature_engineering.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["pipeline"] == "feature_engineering"

    def test_format_extracts_pipeline_name_from_inference(self):
        """Pipeline name is extracted from wemakecalls.pipelines.inference.nodes."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.inference.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["pipeline"] == "inference"

    def test_format_level_field_is_error(self):
        """Level field matches the log record level name."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.ingestion.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Something went wrong",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"

    def test_format_message_field_contains_log_message(self):
        """Message field contains the actual log message."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="wemakecalls.pipelines.ingestion.nodes",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Database error during batch insert: connection refused",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Database error during batch insert: connection refused"

    def test_format_api_logger_name(self):
        """Pipeline name for entrypoints.api is 'api'."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="entrypoints.api",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["pipeline"] == "api"


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_creates_log_directory(self, tmp_path):
        """setup_logging creates the log directory if it doesn't exist."""
        log_dir = tmp_path / "new_logs"
        setup_logging(log_dir=log_dir)
        assert log_dir.exists()

    def test_creates_pipeline_log_file_on_error(self, tmp_path):
        """An ERROR log from a wemakecalls logger writes to pipeline.log."""
        log_dir = tmp_path / "logs"

        # Remove any existing JSON file handlers from prior test runs
        wmc_logger = logging.getLogger("wemakecalls")
        wmc_logger.handlers = [
            h for h in wmc_logger.handlers
            if not (isinstance(h, logging.FileHandler) and hasattr(h, "_wmc_json_handler"))
        ]

        setup_logging(log_dir=log_dir)

        # Use a unique logger name to avoid interference
        test_logger = logging.getLogger("wemakecalls.pipelines.ingestion.test_setup")
        test_logger.error("Test error message for file output")

        log_file = log_dir / "pipeline.log"
        assert log_file.exists()

        content = log_file.read_text(encoding="utf-8")
        assert content.strip()  # Not empty

        # Parse the JSON entry
        entry = json.loads(content.strip().split("\n")[-1])
        assert entry["level"] == "ERROR"
        assert entry["pipeline"] == "ingestion"
        assert "Test error message for file output" in entry["message"]

    def test_info_messages_not_written_to_file(self, tmp_path):
        """INFO-level messages are NOT written to the JSON log file."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)

        test_logger = logging.getLogger("wemakecalls.pipelines.ingestion.test_info")
        test_logger.info("This should not appear in the file")

        log_file = log_dir / "pipeline.log"
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            assert "This should not appear in the file" not in content

    def test_idempotent_setup(self, tmp_path):
        """Calling setup_logging multiple times does not add duplicate handlers."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)
        setup_logging(log_dir=log_dir)
        setup_logging(log_dir=log_dir)

        wmc_logger = logging.getLogger("wemakecalls")
        file_handlers = [
            h for h in wmc_logger.handlers
            if isinstance(h, logging.FileHandler) and hasattr(h, "_wmc_json_handler")
        ]
        # Should only have one JSON file handler despite multiple calls
        assert len(file_handlers) == 1
