"""
CLI entry point for generating synthetic call log CSV files.

Usage:
    python entrypoints/generate_csv.py --start-date 2024-01-01 --end-date 2024-12-31 --row-count 100000
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from wemakecalls.pipelines.csv_generator import generate_call_logs


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{value}'. Expected YYYY-MM-DD."
        )


def main() -> None:
    """Parse CLI arguments and invoke the CSV generator."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic call log CSV files for ML training data."
    )
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        required=True,
        help="Inclusive start date for generated datetime values (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        required=True,
        help="Inclusive end date for generated datetime values (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--row-count",
        type=int,
        required=True,
        help="Exact number of data rows to generate (1–10,000,000).",
    )

    args = parser.parse_args()

    # Configure basic logging so WARNING messages from csv_generator are visible
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    output_path = generate_call_logs(
        start_date=args.start_date,
        end_date=args.end_date,
        row_count=args.row_count,
    )

    print(f"Generated CSV: {output_path}")


if __name__ == "__main__":
    main()
