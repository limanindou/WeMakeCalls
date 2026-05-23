"""Startup check for the ML Service container.

Validates that required environment variables are set before the FastAPI
server or any Kedro pipeline is started. This module is designed to be
both importable (call check_database_url() directly) and executable as
a script (python entrypoints/startup_check.py).

Per spec: "The DATABASE_URL environment variable must never have a default value."
"""

import os
import sys


def check_database_url() -> str:
    """Validate that DATABASE_URL is set and non-empty.

    Reads DATABASE_URL from the environment. If the variable is absent or
    set to an empty string, prints a descriptive error to stderr and exits
    with status code 1.

    Returns:
        The DATABASE_URL value if present and non-empty.
    """
    database_url = os.environ.get("DATABASE_URL", "")

    if not database_url:
        print(
            "FATAL: DATABASE_URL environment variable is not set or is empty.\n"
            "The ML Service requires a PostgreSQL connection string to operate.\n"
            "Set DATABASE_URL (e.g., 'postgresql://user:pass@host:5432/dbname') "
            "via Docker Compose or 'docker run -e DATABASE_URL=...' before starting "
            "the container.",
            file=sys.stderr,
        )
        sys.exit(1)

    return database_url


if __name__ == "__main__":
    check_database_url()
