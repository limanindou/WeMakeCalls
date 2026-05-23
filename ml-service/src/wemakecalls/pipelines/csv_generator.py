"""
CSV Generator for WeMakeCalls ML Service.

Generates synthetic historical call log CSV files for use as training data
before live simulator data is available.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Fixed value sets per requirements
QUEUE_NAMES = ["billing", "support", "sales", "technical"]
AGENT_IDS = [f"A{i:02d}" for i in range(1, 21)]  # A01 through A20
HANGUP_REASONS = [
    "Issue Resolved",
    "Wrong Department",
    "Long Wait Time",
    "Call Dropped",
    "Other",
]
HANGUP_REASON_ABANDONED = "Call Dropped"

# Weighted hourly distribution: higher weights for business hours 08:00–18:00
# 24 weights, one per hour (0–23)
_HOUR_WEIGHTS = np.array(
    [
        1,  # 00
        1,  # 01
        1,  # 02
        1,  # 03
        1,  # 04
        1,  # 05
        2,  # 06
        3,  # 07
        8,  # 08  — business hours start
        10,  # 09
        10,  # 10
        10,  # 11
        9,  # 12
        10,  # 13
        10,  # 14
        10,  # 15
        10,  # 16
        9,  # 17
        8,  # 18  — business hours end
        5,  # 19
        4,  # 20
        3,  # 21
        2,  # 22
        1,  # 23
    ],
    dtype=float,
)
_HOUR_WEIGHTS /= _HOUR_WEIGHTS.sum()  # normalise to probabilities

# Log-normal parameters for duration_seconds (non-abandoned calls)
# Target: median ~180s, clipped to [30, 1800]
_LOGNORMAL_MEAN = 5.2  # ln(~180)
_LOGNORMAL_SIGMA = 0.8

# Abandonment rate: ~10–15% of rows
_ABANDONMENT_RATE = 0.12


def _random_datetimes(
    rng: np.random.Generator,
    start_date: date,
    end_date: date,
    row_count: int,
) -> list[datetime]:
    """
    Generate `row_count` datetime values within [start_date, end_date] using
    a weighted hourly distribution that favours business hours (08:00–18:00).
    """
    total_days = (end_date - start_date).days + 1

    # Sample random days (uniform) and random hours (weighted)
    day_offsets = rng.integers(0, total_days, size=row_count)
    hours = rng.choice(24, size=row_count, p=_HOUR_WEIGHTS)
    minutes = rng.integers(0, 60, size=row_count)
    seconds = rng.integers(0, 60, size=row_count)

    base = datetime(start_date.year, start_date.month, start_date.day)
    datetimes = [
        base + timedelta(days=int(d), hours=int(h), minutes=int(m), seconds=int(s))
        for d, h, m, s in zip(day_offsets, hours, minutes, seconds)
    ]
    return datetimes


def generate_call_logs(
    start_date: date,
    end_date: date,
    row_count: int,
    output_dir: Path | str = Path("data/01_raw"),
) -> Path:
    """
    Generate a synthetic call log CSV file.

    Parameters
    ----------
    start_date:
        Inclusive start date for generated ``datetime`` values.
    end_date:
        Inclusive end date for generated ``datetime`` values.
    row_count:
        Exact number of data rows to produce (1 ≤ row_count ≤ 10,000,000).
    output_dir:
        Directory to write the output file into.  Defaults to ``data/01_raw``.

    Returns
    -------
    Path
        Absolute path to the written CSV file.

    Raises
    ------
    ValueError
        If ``row_count`` is outside [1, 10_000_000] or ``start_date > end_date``.
    """
    if not (1 <= row_count <= 10_000_000):
        raise ValueError(
            f"row_count must be between 1 and 10,000,000; got {row_count}"
        )
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})"
        )

    output_dir = Path(output_dir)
    output_path = output_dir / f"call_history_{start_date.year}.csv"

    # Warn if the output file already exists (requirement 1.11)
    if output_path.exists():
        logger.warning(
            "Output file already exists and will be overwritten: %s", output_path
        )

    rng = np.random.default_rng()

    # --- Generate each column ---

    # call_id: unique UUID per row
    call_ids = [str(uuid.uuid4()) for _ in range(row_count)]

    # datetime: weighted hourly distribution within [start_date, end_date]
    datetimes = _random_datetimes(rng, start_date, end_date, row_count)

    # abandoned: ~10–15% abandonment rate (using _ABANDONMENT_RATE = 0.12)
    abandoned = rng.random(size=row_count) < _ABANDONMENT_RATE

    # duration_seconds:
    #   - abandoned rows → 0
    #   - non-abandoned rows → log-normal, clipped to [30, 1800]
    raw_durations = rng.lognormal(mean=_LOGNORMAL_MEAN, sigma=_LOGNORMAL_SIGMA, size=row_count)
    clipped_durations = np.clip(raw_durations, 30, 1800).astype(int)
    duration_seconds = np.where(abandoned, 0, clipped_durations)

    # queue_name: uniform from fixed set
    queue_names = rng.choice(QUEUE_NAMES, size=row_count)

    # agent_id: uniform from A01–A20
    agent_ids = rng.choice(AGENT_IDS, size=row_count)

    # wait_time_seconds: random integer 0–600
    wait_time_seconds = rng.integers(0, 601, size=row_count)

    # hangup_reason:
    #   - abandoned rows → "Call Dropped"
    #   - non-abandoned rows → uniform from full 5-value set
    non_abandoned_reasons = rng.choice(HANGUP_REASONS, size=row_count)
    hangup_reasons = np.where(abandoned, HANGUP_REASON_ABANDONED, non_abandoned_reasons)

    # --- Assemble DataFrame with exact column order (requirement 1.1) ---
    df = pd.DataFrame(
        {
            "call_id": call_ids,
            "datetime": datetimes,
            "duration_seconds": duration_seconds,
            "queue_name": queue_names,
            "agent_id": agent_ids,
            "wait_time_seconds": wait_time_seconds,
            "abandoned": abandoned,
            "hangup_reason": hangup_reasons,
        }
    )

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write UTF-8 CSV with header row (requirement 1.12)
    df.to_csv(output_path, index=False, encoding="utf-8")

    logger.info(
        "Generated %d call log rows → %s", row_count, output_path
    )

    return output_path
