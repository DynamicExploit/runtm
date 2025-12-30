# syntax=docker/dockerfile:1.4
# Optimized Dockerfile for Python backend service
# Uses BuildKit for parallel builds and better caching

FROM python:3.12-alpine AS builder

WORKDIR /app

# Install build dependencies (only needed for compilation)
RUN apk add --no-cache gcc musl-dev libffi-dev

# Install dependencies first (better caching)
COPY pyproject.toml .

# Use BuildKit cache mount for pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir .

# Production stage - minimal runtime image
FROM python:3.12-alpine AS runner

WORKDIR /app

# Install only runtime dependencies (curl for health checks)
RUN apk add --no-cache curl

# Create data directory for persistent storage (SQLite, uploads, etc.)
# Note: Do NOT use VOLUME directive - Fly handles volume mounts externally
RUN mkdir -p /data

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy application code last (changes most frequently)
COPY . .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
