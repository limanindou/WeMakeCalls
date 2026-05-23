"""Shared structured JSON logging utility for the WeMakeCalls ML Service.

Configures the ``wemakecalls`` logger hierarchy so that:
- ERROR-level messages are written to ``logs/pipeline.log`` as structured JSON
  with fields: timestamp (ISO 8601 UTC), pipeline, level, message.
- INFO+ messages are written to the console in a standard human-readable format.

Usage:
    Call ``setup_logging()`` once at application startup (e.g. in the FastAPI
    startup event or at the top of a Kedro session hook).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with the required fields.

    Output schema:
        {
            "timestamp": "<ISO 8601 UTC>",
            "pipeline": "<pipeline name>",
            "level": "ERROR",
            "message": "<error description>"
        }

    The ``pipeline`` field is derived from the logger name. For loggers under
    ``wemakecalls.pipelines.<name>.*``, the pipeline name is extracted
    automatically. For other ``wemakecalls.*`` loggers (e.g. the API), the
    second segment of the logger name is used. If the logger name has no
    segments beyond ``wemakecalls``, the pipeline defaults to ``"app"``.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        pipeline = self._extract_pipeline_name(record.name)
        # Use record.getMessage() to get the fully formatted message
        # (handles %-style formatting of args into msg)
        message = record.getMessage()
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pipeline": pipeline,
            "level": record.levelname,
            "message": message,
        }
        return json.dumps(entry, ensure_ascii=False)

    @staticmethod
    def _extract_pipeline_name(logger_name: str) -> str:
        """Derive a pipeline name from the dotted logger name.

        Examples:
            wemakecalls.pipelines.ingestion.nodes -> "ingestion"
            wemakecalls.pipelines.training.nodes  -> "training"
            wemakecalls.pipelines.csv_generator   -> "csv_generator"
            entrypoints.api                       -> "api"
            wemakecalls                           -> "app"
        """
        parts = logger_name.split(".")
        # wemakecalls.pipelines.<pipeline_name>.* pattern
        if len(parts) >= 3 and parts[0] == "wemakecalls" and parts[1] == "pipelines":
            return parts[2]
        # wemakecalls.<something> pattern
        if len(parts) >= 2 and parts[0] == "wemakecalls":
            return parts[1]
        # entrypoints.api or similar
        if len(parts) >= 2:
            return parts[-1]
        return "app"


def setup_logging(log_dir: str | Path | None = None) -> None:
    """Configure structured JSON file logging and console logging.

    Sets up the ``wemakecalls`` root logger with two handlers:
    1. A file handler writing ERROR+ messages as structured JSON to
       ``logs/pipeline.log``.
    2. A console (stderr) handler writing INFO+ messages in standard format.

    This function is idempotent — calling it multiple times will not add
    duplicate handlers.

    Args:
        log_dir: Directory for the log file. Defaults to ``logs/`` relative
            to the current working directory. The directory is created if it
            does not exist.
    """
    if log_dir is None:
        log_dir = Path("logs")
    else:
        log_dir = Path(log_dir)

    # Ensure the log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "pipeline.log"

    # Get the root logger for the wemakecalls namespace
    wmc_logger = logging.getLogger("wemakecalls")

    # Avoid adding duplicate handlers on repeated calls
    if any(
        isinstance(h, logging.FileHandler) and hasattr(h, "_wmc_json_handler")
        for h in wmc_logger.handlers
    ):
        return

    # Set the logger level to DEBUG so handlers can filter independently
    wmc_logger.setLevel(logging.DEBUG)

    # --- File handler: ERROR+ as structured JSON ---
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(StructuredJSONFormatter())
    file_handler._wmc_json_handler = True  # type: ignore[attr-defined]  # marker for idempotency
    wmc_logger.addHandler(file_handler)

    # --- Console handler: INFO+ in standard format ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    wmc_logger.addHandler(console_handler)

    # Also configure the entrypoints logger to use the same handlers
    # so that api.py errors are captured in the JSON log
    entrypoints_logger = logging.getLogger("entrypoints")
    entrypoints_logger.setLevel(logging.DEBUG)
    if not any(
        isinstance(h, logging.FileHandler) and hasattr(h, "_wmc_json_handler")
        for h in entrypoints_logger.handlers
    ):
        ep_file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        ep_file_handler.setLevel(logging.ERROR)
        ep_file_handler.setFormatter(StructuredJSONFormatter())
        ep_file_handler._wmc_json_handler = True  # type: ignore[attr-defined]
        entrypoints_logger.addHandler(ep_file_handler)

        ep_console_handler = logging.StreamHandler()
        ep_console_handler.setLevel(logging.INFO)
        ep_console_handler.setFormatter(console_formatter)
        entrypoints_logger.addHandler(ep_console_handler)
