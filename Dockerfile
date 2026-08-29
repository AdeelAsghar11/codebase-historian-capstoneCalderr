# Multi-stage Dockerfile for Codebase Historian
FROM python:3.12-slim AS base

# Install uv for fast, reproducible dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory and environment variables
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install git for repository analysis and GitPython operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and dependency specs
COPY pyproject.toml uv.lock ./

# Install dependencies into .venv
RUN uv sync --frozen --no-install-project

# Copy source tree and tests
COPY README.md ./
COPY docs/ ./docs/
COPY src/ ./src/
COPY tests/ ./tests/

# Install the project itself
RUN uv sync --frozen

# Expose FastAPI port
EXPOSE 8000

# Default command: run FastAPI REST API via Uvicorn
CMD ["uv", "run", "uvicorn", "codebase_historian.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
