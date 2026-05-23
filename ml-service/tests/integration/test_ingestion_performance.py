"""Integration test: Ingestion pipeline performance.

Verifies that ingesting a 100,000-row CSV file end-to-end against a real
PostgreSQL instance completes within 60 seconds (Requirement 2.8).
"""

import os
import tempfile
import time
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Skip the entire module if DATABASE_URL is not set
DATABASE_URL = os.environ.get("DATABASE_URL")
skip_no_db = pytest.mark.skipif(
    DATABASE_URL is None,
    reason="DATABASE_URL environment variable not set — skipping integration test",
)


@skip_no_db
def test_ingestion_100k_rows_within_60_seconds():
    """Ingest a 100,000-row CSV end-to-end and assert completion within 60 seconds."""
    from sqlalchemy import create_engine, text

    from wemakecalls.pipelines.csv_generator import generate_call_logs
    from wemakecalls.pipelines.ingestion.nodes import (
        deduplicate,
        insert_to_postgres,
        parse_and_clean,
        validate_columns,
    )

    engine = create_engine(DATABASE_URL)

    # Generate a 100,000-row CSV in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = generate_call_logs(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            row_count=100_000,
            output_dir=Path(tmpdir),
        )

        # Read the CSV
        import pandas as pd

        df = pd.read_csv(csv_path)

        # Measure end-to-end ingestion time
        start = time.time()

        df = validate_columns(df)
        df = parse_and_clean(df)
        df = deduplicate(df, engine)
        insert_to_postgres(df, engine)

        elapsed = time.time() - start

    # Clean up inserted rows
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM call_logs WHERE source = 'csv_import'"))
    except Exception:
        pass  # Best-effort cleanup

    engine.dispose()

    assert elapsed < 60, (
        f"Ingestion of 100,000 rows took {elapsed:.2f}s, exceeding the 60s threshold"
    )
