# Multi-stage build for Railway deployment
# Build stage - install dependencies
FROM python:3.12-slim AS build

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (production only, no dev dependencies)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY app ./app

# Copy alembic for migrations
COPY alembic ./alembic
COPY alembic.ini ./

# Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from build stage
COPY --from=build /app/.venv /app/.venv

# Copy application code
COPY --from=build /app/app ./app

# Copy alembic migrations
COPY --from=build /app/alembic ./alembic
COPY --from=build /app/alembic.ini ./

# Set ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Railway sets PORT dynamically, default to 8000
ENV PORT=8000

# Expose port (documentation only - Railway uses PORT env var)
EXPOSE 8000

# Run deploy script (migrations + validation) then start uvicorn
CMD python -u -m app.deploy && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
