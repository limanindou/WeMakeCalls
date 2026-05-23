"""
Property-based tests for the CSV Generator.

Tests Properties 1 and 2 from the design document using Hypothesis.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from wemakecalls.pipelines.csv_generator import (
    AGENT_IDS,
    HANGUP_REASONS,
    QUEUE_NAMES,
    generate_call_logs,
)


# Strategy: generate valid date pairs where start_date <= end_date
# Constrain to a reasonable range to avoid edge cases with extremely distant dates
_date_strategy = st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31))


@st.composite
def valid_date_range(draw: st.DrawFn) -> tuple[date, date]:
    """Generate a (start_date, end_date) pair where start_date <= end_date."""
    d1 = draw(_date_strategy)
    d2 = draw(_date_strategy)
    if d1 > d2:
        d1, d2 = d2, d1
    return d1, d2


@settings(max_examples=100)
@given(
    date_range=valid_date_range(),
    row_count=st.integers(min_value=1, max_value=500),
)
def test_property_1_row_count_and_datetime_bounds(
    date_range: tuple[date, date],
    row_count: int,
) -> None:
    """
    Property 1: Row count and datetime bounds.

    For any valid start_date, end_date, row_count in [1, 10,000,000],
    the generated CSV contains exactly row_count data rows and every
    datetime falls within the inclusive date range.

    **Validates: Requirements 1.2**
    """
    start_date, end_date = date_range

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = generate_call_logs(
            start_date=start_date,
            end_date=end_date,
            row_count=row_count,
            output_dir=Path(tmp_dir),
        )

        df = pd.read_csv(output_path, parse_dates=["datetime"])

        # Exactly row_count data rows
        assert len(df) == row_count, (
            f"Expected {row_count} rows, got {len(df)}"
        )

        # Every datetime falls within [start_date, end_date] inclusive
        for dt in df["datetime"]:
            row_date = dt.date()
            assert start_date <= row_date <= end_date, (
                f"datetime {dt} has date {row_date} outside "
                f"[{start_date}, {end_date}]"
            )


@settings(max_examples=100)
@given(
    date_range=valid_date_range(),
    row_count=st.integers(min_value=1, max_value=500),
)
def test_property_2_field_domain_constraints(
    date_range: tuple[date, date],
    row_count: int,
) -> None:
    """
    Property 2: Field domain constraints.

    For any generated CSV, every row satisfies:
    - queue_name in {billing, support, sales, technical}
    - agent_id in {A01..A20}
    - hangup_reason in the 5-value set
    - abandoned rows have duration_seconds=0 and hangup_reason="Call Dropped"
    - non-abandoned rows have duration_seconds in [30, 1800]

    **Validates: Requirements 1.4, 1.6, 1.7, 1.8, 1.9**
    """
    start_date, end_date = date_range

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = generate_call_logs(
            start_date=start_date,
            end_date=end_date,
            row_count=row_count,
            output_dir=Path(tmp_dir),
        )

        df = pd.read_csv(output_path)

        # queue_name domain
        valid_queues = set(QUEUE_NAMES)
        assert set(df["queue_name"].unique()).issubset(valid_queues), (
            f"Invalid queue_name values: "
            f"{set(df['queue_name'].unique()) - valid_queues}"
        )

        # agent_id domain
        valid_agents = set(AGENT_IDS)
        assert set(df["agent_id"].unique()).issubset(valid_agents), (
            f"Invalid agent_id values: "
            f"{set(df['agent_id'].unique()) - valid_agents}"
        )

        # hangup_reason domain
        valid_reasons = set(HANGUP_REASONS)
        assert set(df["hangup_reason"].unique()).issubset(valid_reasons), (
            f"Invalid hangup_reason values: "
            f"{set(df['hangup_reason'].unique()) - valid_reasons}"
        )

        # Abandoned rows: duration_seconds=0 and hangup_reason="Call Dropped"
        abandoned_rows = df[df["abandoned"] == True]  # noqa: E712
        if len(abandoned_rows) > 0:
            assert (abandoned_rows["duration_seconds"] == 0).all(), (
                "Some abandoned rows have duration_seconds != 0"
            )
            assert (abandoned_rows["hangup_reason"] == "Call Dropped").all(), (
                "Some abandoned rows have hangup_reason != 'Call Dropped'"
            )

        # Non-abandoned rows: duration_seconds in [30, 1800]
        non_abandoned_rows = df[df["abandoned"] == False]  # noqa: E712
        if len(non_abandoned_rows) > 0:
            durations = non_abandoned_rows["duration_seconds"]
            assert (durations >= 30).all(), (
                f"Some non-abandoned rows have duration_seconds < 30: "
                f"min={durations.min()}"
            )
            assert (durations <= 1800).all(), (
                f"Some non-abandoned rows have duration_seconds > 1800: "
                f"max={durations.max()}"
            )
