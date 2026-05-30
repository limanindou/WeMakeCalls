# ML Service Dockerfile
# Python 3.12 slim base with uv for dependency management
FROM python:3.12-slim

# Install uv package manager
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy pyproject.toml first for Docker layer caching
COPY pyproject.toml ./

# Install all dependencies with exact versions via uv sync
RUN uv sync

# Copy the rest of the source code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# HEALTHCHECK: use Python instead of curl to avoid apt-get dependency
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# NOTE: DATABASE_URL is intentionally NOT set here.
# It MUST be injected at runtime via Docker Compose or docker run -e.

# ENTRYPOINT: run startup_check.py first (validates DATABASE_URL),
# then start Uvicorn on 0.0.0.0:8000
ENTRYPOINT ["sh", "-c", "uv run python entrypoints/startup_check.py && uv run uvicorn entrypoints.api:app --host 0.0.0.0 --port 8000"]

